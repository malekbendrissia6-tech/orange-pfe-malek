"""
Blueprint Data Quality - Orange Tunisie PFE 2026
Migré depuis app/monitoring.py (Streamlit abandonné).
Accessible : data_engineer + admin
"""

import os
import re
import json
import subprocess
import sys
from functools import wraps
from datetime import datetime
from pathlib import Path

from flask import (Blueprint, render_template, request, jsonify,
                   send_file, session, redirect, url_for, flash)

from flask_app.data_quality_utils import (
    load_error_stats, list_error_files, count_log_files,
    get_severity, get_stats_by_table, get_stats_by_type,
    generate_quality_report_html, send_quality_email,
    TABLES, ERROR_DIR, INPUT_DIR, OUTPUT_DIR, LOGS_DIR,
)

dq_bp = Blueprint("data_quality", __name__, url_prefix="/data-quality")

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------
# DÉCORATEUR rôle
# ---------------------------------------------------------------
def dq_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "data_engineer":
            flash("Accès réservé aux Data Engineers.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------
# PAGE ACCUEIL DATA ENGINEER
# ---------------------------------------------------------------
@dq_bp.route("/accueil")
@dq_required
def accueil():
    error_stats     = load_error_stats()
    total_errors    = sum(r["rows"] for r in error_stats)
    total_files     = len(error_stats)
    tables_with_err = len({r["table"] for r in error_stats})
    total_logs      = count_log_files()
    return render_template(
        "data_quality/accueil.html",
        total_errors    = total_errors,
        total_files     = total_files,
        tables_with_err = tables_with_err,
        total_tables    = len(TABLES),
        total_logs      = total_logs,
        now             = datetime.now().strftime("%d %b %Y, %H:%M"),
    )


# ---------------------------------------------------------------
# API : STATS FILTRÉES (table, type, periode)
# ---------------------------------------------------------------
@dq_bp.route("/api/stats")
@dq_required
def api_stats():
    from datetime import timedelta
    table_f  = request.args.get('table')  or None
    type_f   = request.args.get('type')   or None
    periode_f = request.args.get('periode') or None

    stats = load_error_stats()

    if table_f:
        stats = [r for r in stats if r['table'] == table_f]
    if type_f:
        stats = [r for r in stats if r['type'] == type_f]
    if periode_f and periode_f != 'tout':
        cutoff = {
            'jour':    datetime.now() - timedelta(days=1),
            'semaine': datetime.now() - timedelta(days=7),
            'mois':    datetime.now() - timedelta(days=30),
        }.get(periode_f)
        if cutoff:
            def _within(r):
                try:
                    return datetime.strptime(r['modified'], '%d/%m/%Y %H:%M') >= cutoff
                except Exception:
                    return True
            stats = [r for r in stats if _within(r)]

    return jsonify({
        'total_errors':    sum(r['rows'] for r in stats),
        'total_files':     len(stats),
        'tables_with_err': len({r['table'] for r in stats}),
        'by_table':        get_stats_by_table(stats),
        'by_type':         get_stats_by_type(stats),
        'error_stats':     sorted(stats, key=lambda r: r['rows'], reverse=True),
    })


@dq_bp.route("/api/filter-options")
@dq_required
def api_filter_options():
    stats = load_error_stats()
    return jsonify({
        'tables': sorted({r['table'] for r in stats}),
        'types':  sorted({r['type']  for r in stats}),
    })


# ---------------------------------------------------------------
# PAGE 1 : VUE D'ENSEMBLE
# ---------------------------------------------------------------
@dq_bp.route("/")
@dq_required
def vue_ensemble():
    error_stats      = load_error_stats()
    total_errors     = sum(r["rows"] for r in error_stats)
    total_files      = len(error_stats)
    tables_with_err  = len({r["table"] for r in error_stats})
    total_logs       = count_log_files()
    by_table         = get_stats_by_table(error_stats)
    by_type          = get_stats_by_type(error_stats)
    return render_template(
        "data_quality/vue_ensemble.html",
        total_errors    = total_errors,
        total_files     = total_files,
        tables_with_err = tables_with_err,
        total_tables    = len(TABLES),
        total_logs      = total_logs,
        error_stats     = error_stats,
        by_table        = by_table,
        by_type         = by_type,
        now             = datetime.now().strftime("%d %b %Y, %H:%M"),
    )


# ---------------------------------------------------------------
# PAGE 2 : DÉTAIL PAR TABLE
# ---------------------------------------------------------------
@dq_bp.route("/tableau")
@dq_required
def tableau():
    table_choisie = request.args.get("table", TABLES[0])
    error_stats   = load_error_stats()
    table_errors  = [r for r in error_stats if r["table"] == table_choisie]

    total_table = sum(r["rows"] for r in table_errors)
    dataset_size = "N/A"
    error_rate   = "N/A"

    source_file = INPUT_DIR / f"{table_choisie}.xlsx"
    if source_file.exists():
        try:
            import pandas as pd
            df_src = pd.read_excel(source_file)
            dataset_size = f"{len(df_src):,}"
            if total_table > 0 and len(df_src) > 0:
                error_rate = f"{(total_table / len(df_src)) * 100:.1f}%"
            else:
                error_rate = "0%"
        except Exception:
            pass

    for r in table_errors:
        r["severity"] = get_severity(r["type"])

    return render_template(
        "data_quality/tableau.html",
        tables        = TABLES,
        table_choisie = table_choisie,
        table_errors  = sorted(table_errors, key=lambda r: r["rows"], reverse=True),
        total_table   = total_table,
        dataset_size  = dataset_size,
        error_rate    = error_rate,
    )


# ---------------------------------------------------------------
# PAGE 3 : ALERTES QUALITÉ
# ---------------------------------------------------------------
@dq_bp.route("/alertes")
@dq_required
def alertes():
    error_stats = load_error_stats()
    for r in error_stats:
        r["severity"] = get_severity(r["type"])

    critiques = sorted(
        [r for r in error_stats if r["severity"] == "CRITIQUE"],
        key=lambda r: r["rows"], reverse=True,
    )
    warnings = sorted(
        [r for r in error_stats if r["severity"] == "ATTENTION"],
        key=lambda r: r["rows"], reverse=True,
    )
    infos = [r for r in error_stats if r["severity"] == "INFO"]

    return render_template(
        "data_quality/alertes.html",
        critiques   = critiques,
        warnings    = warnings,
        infos       = infos,
        nb_crit     = len(critiques),
        nb_warn     = len(warnings),
        nb_info     = len(infos),
        rows_crit   = sum(r["rows"] for r in critiques),
        rows_warn   = sum(r["rows"] for r in warnings),
    )


# ---------------------------------------------------------------
# PAGE 4 : EXPLORATEUR D'ERREURS
# ---------------------------------------------------------------
@dq_bp.route("/explorateur")
@dq_required
def explorateur():
    error_files  = list_error_files()
    file_names   = [f.name for f in error_files]
    file_choisi  = request.args.get("file", file_names[0] if file_names else None)
    search_term  = request.args.get("q", "")
    rows_data    = []
    columns      = []
    row_count    = 0
    col_count    = 0
    size_kb      = 0

    if file_choisi:
        fp = ERROR_DIR / file_choisi
        if fp.exists():
            try:
                import pandas as pd
                df = pd.read_excel(fp)
                size_kb   = round(fp.stat().st_size / 1024, 1)
                row_count = len(df)
                col_count = len(df.columns)
                columns   = df.columns.tolist()
                if search_term:
                    mask = df.astype(str).apply(
                        lambda x: x.str.contains(search_term, case=False, na=False)
                    ).any(axis=1)
                    df = df[mask]
                rows_data = df.head(100).fillna("").astype(str).values.tolist()
            except Exception:
                pass

    return render_template(
        "data_quality/explorateur.html",
        file_names   = file_names,
        file_choisi  = file_choisi,
        search_term  = search_term,
        rows_data    = rows_data,
        columns      = columns,
        row_count    = row_count,
        col_count    = col_count,
        size_kb      = size_kb,
    )


@dq_bp.route("/download/<path:filename>")
@dq_required
def download_file(filename):
    safe = Path(filename).name
    fp   = ERROR_DIR / safe
    if not fp.exists():
        return "Fichier non trouvé.", 404
    return send_file(
        str(fp),
        as_attachment=True,
        download_name=safe,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------
# PAGE 5 : HISTORIQUE EXÉCUTIONS
# ---------------------------------------------------------------
@dq_bp.route("/executions")
@dq_required
def executions():
    table_filter = request.args.get("table", "Toutes")
    log_files    = []

    if LOGS_DIR.exists():
        all_logs = sorted(LOGS_DIR.glob("*.log"), reverse=True)
        log_files = (
            [f for f in all_logs if table_filter in f.name]
            if table_filter != "Toutes"
            else all_logs
        )

    entries = []
    for lf in log_files[:30]:
        ts = datetime.fromtimestamp(lf.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
        try:
            with open(lf, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            content = "(erreur de lecture)"
        entries.append({"name": lf.name, "ts": ts, "content": content})

    return render_template(
        "data_quality/executions.html",
        tables       = TABLES,
        table_filter = table_filter,
        entries      = entries,
        total_logs   = count_log_files(),
    )


# ---------------------------------------------------------------
# PAGE 6 : NOTIFICATIONS EMAIL
# ---------------------------------------------------------------
@dq_bp.route("/notifications")
@dq_required
def notifications():
    error_stats = load_error_stats()
    mail_user   = os.getenv("MAIL_USERNAME", "")
    return render_template(
        "data_quality/notifications.html",
        error_stats = error_stats,
        tables      = TABLES,
        mail_user   = mail_user,
    )


@dq_bp.route("/api/send-email", methods=["POST"])
@dq_required
def api_send_email():
    data         = request.get_json(force=True)
    expediteur   = data.get("expediteur", "")
    mot_de_passe = data.get("mot_de_passe", "")
    destinataire = data.get("destinataire", "")
    sujet        = data.get("sujet", "Rapport Qualite - Orange Tunisie")
    tables_sel   = data.get("tables", TABLES)

    if not all([expediteur, mot_de_passe, destinataire]):
        return jsonify({"ok": False, "error": "Champs manquants"}), 400

    error_stats = [r for r in load_error_stats() if r["table"] in tables_sel]
    corps       = generate_quality_report_html(error_stats)
    note        = data.get("note", "")
    if note:
        corps = corps.replace("</body>", f"<p><i>{note}</i></p></body>")

    ok, err = send_quality_email(expediteur, mot_de_passe, destinataire, sujet, corps)
    return jsonify({"ok": ok, "error": err})


# ---------------------------------------------------------------
# PAGE 7 : EXÉCUTION PIPELINE
# ---------------------------------------------------------------
@dq_bp.route("/pipeline")
@dq_required
def pipeline():
    nb_input  = len(list(INPUT_DIR.glob("*.xlsx")))  if INPUT_DIR.exists()  else 0
    nb_output = len(list(OUTPUT_DIR.glob("*.xlsx"))) if OUTPUT_DIR.exists() else 0
    nb_error  = len(list(ERROR_DIR.glob("*.xlsx")))  if ERROR_DIR.exists()  else 0
    nb_logs   = count_log_files()
    return render_template(
        "data_quality/pipeline.html",
        tables    = TABLES,
        nb_input  = nb_input,
        nb_output = nb_output,
        nb_error  = nb_error,
        nb_logs   = nb_logs,
    )


@dq_bp.route("/api/run-pipeline", methods=["POST"])
@dq_required
def api_run_pipeline():
    data  = request.get_json(force=True) or {}
    table = data.get("table")
    cmd   = [sys.executable, "main.py"]
    if table:
        cmd.append(table)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        return jsonify({
            "ok":         result.returncode == 0,
            "output":     result.stdout,
            "error_out":  result.stderr,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error_out": "Timeout (5 min)"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error_out": str(e)}), 200


@dq_bp.route("/api/run-tests", methods=["POST"])
@dq_required
def api_run_tests():
    data     = request.get_json(force=True) or {}
    coverage = data.get("coverage", False)
    cmd      = [sys.executable, "-m", "pytest", "tests/", "-v"]
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing"])
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        output  = result.stdout + result.stderr
        passed  = re.search(r"(\d+) passed", output)
        cov     = re.search(r"TOTAL.*?(\d+)%", output)
        elapsed = re.search(r"in ([\d.]+)s", output)
        return jsonify({
            "ok":       result.returncode == 0,
            "output":   output,
            "passed":   int(passed.group(1)) if passed else None,
            "coverage": int(cov.group(1)) if cov else None,
            "elapsed":  elapsed.group(1) if elapsed else None,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "output": "Timeout (5 min)"}), 200
    except Exception as e:
        return jsonify({"ok": False, "output": str(e)}), 200


# ---------------------------------------------------------------
