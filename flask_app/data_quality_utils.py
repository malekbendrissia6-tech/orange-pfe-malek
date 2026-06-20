"""
Utilitaires Data Quality - Orange Tunisie PFE 2026
Migré depuis app/monitoring.py (Streamlit → Flask)
"""

import smtplib
import os
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

PROJECT_ROOT = Path(__file__).parent.parent

ERROR_DIR  = PROJECT_ROOT / "data" / "error"
INPUT_DIR  = PROJECT_ROOT / "data" / "input"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
LOGS_DIR   = PROJECT_ROOT / "logs"

TABLES = [
    "ventes_contrats", "offres", "vendeurs", "boutiques",
    "groupes", "articles", "ref_objectifs", "objectifs",
]


def list_error_files() -> list:
    if not ERROR_DIR.exists():
        return []
    return sorted(ERROR_DIR.glob("*.xlsx"))


def parse_error_filename(filepath: Path) -> dict:
    stem = filepath.stem
    for table in TABLES:
        if stem.startswith(table + "_"):
            return {"table": table, "type": stem[len(table) + 1:], "file": str(filepath)}
    return {"table": "unknown", "type": stem, "file": str(filepath)}


def load_error_stats() -> list:
    """Retourne une liste de dicts avec les stats des fichiers d'erreurs."""
    stats = []
    for fp in list_error_files():
        info = parse_error_filename(fp)
        try:
            import pandas as pd
            df = pd.read_excel(fp)
            info["rows"]     = len(df)
            info["size_kb"]  = round(fp.stat().st_size / 1024, 1)
            info["modified"] = datetime.fromtimestamp(fp.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        except Exception:
            info["rows"]     = 0
            info["size_kb"]  = 0
            info["modified"] = None
        stats.append(info)
    return stats


def count_log_files() -> int:
    return len(list(LOGS_DIR.glob("*.log"))) if LOGS_DIR.exists() else 0


def get_severity(error_type: str) -> str:
    if "rows_dropped" in error_type or "duplicates" in error_type:
        return "CRITIQUE"
    if "missing" in error_type:
        return "ATTENTION"
    return "INFO"


def get_stats_by_table(error_stats: list) -> list:
    """Agrégation des erreurs par table pour Chart.js."""
    agg = {}
    for r in error_stats:
        t = r["table"]
        agg[t] = agg.get(t, 0) + r["rows"]
    return sorted(
        [{"table": k, "nb": v} for k, v in agg.items()],
        key=lambda x: x["nb"],
        reverse=True,
    )


def get_stats_by_type(error_stats: list) -> list:
    """Agrégation des erreurs par type pour Chart.js."""
    agg = {}
    for r in error_stats:
        tp = r["type"]
        agg[tp] = agg.get(tp, 0) + r["rows"]
    return sorted(
        [{"type": k, "nb": v} for k, v in agg.items()],
        key=lambda x: x["nb"],
    )


def send_quality_email(expediteur: str, mot_de_passe: str, destinataire: str,
                       sujet: str, corps_html: str, pieces_jointes: list = None):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"]    = expediteur
        msg["To"]      = destinataire
        msg.attach(MIMEText(corps_html, "html"))
        if pieces_jointes:
            for filepath in (pieces_jointes or []):
                fp = Path(filepath)
                if fp.exists():
                    with open(fp, "rb") as f:
                        part = MIMEApplication(f.read(), Name=fp.name)
                    part["Content-Disposition"] = f'attachment; filename="{fp.name}"'
                    msg.attach(part)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(expediteur, mot_de_passe)
            server.sendmail(expediteur, destinataire, msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)


def generate_quality_report_html(error_stats: list) -> str:
    total_errors = sum(r["rows"] for r in error_stats)
    rows_html = "".join(
        f"<tr><td>{r['table']}</td><td>{r['type']}</td><td><b>{r['rows']:,}</b></td></tr>"
        for r in error_stats
    )
    return f"""
    <html><head><style>
        body {{ font-family: Arial, sans-serif; color: #333; margin: 0; padding: 20px; }}
        .hdr {{ background: linear-gradient(90deg,#FF6600,#FF9933);
                color:white; padding:20px; border-radius:8px; }}
        .hdr h1 {{ margin:0; font-size:22px; letter-spacing:2px; }}
        .stat {{ background:#FFF3E0; padding:15px; margin:15px 0;
                 border-left:4px solid #FF6600; border-radius:4px; }}
        table {{ border-collapse:collapse; width:100%; margin:15px 0; }}
        th {{ background:#FF6600; color:white; padding:11px 14px; text-align:left; }}
        td {{ padding:9px 14px; border-bottom:1px solid #eee; }}
        tr:nth-child(even) {{ background:#fafafa; }}
        .ftr {{ color:#888; font-size:12px; margin-top:30px; text-align:center;
                padding-top:15px; border-top:1px solid #eee; }}
    </style></head><body>
    <div class="hdr"><h1>ORANGE TUNISIE</h1>
        <p style="margin:6px 0 0 0;">Rapport Qualite des Donnees</p></div>
    <div class="stat">
        <h3 style="margin:0;color:#CC5200;">Synthese</h3>
        <p><b>Total erreurs :</b> {total_errors:,} lignes</p>
        <p><b>Tables analysees :</b> {len(TABLES)}</p>
        <p><b>Date :</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    </div>
    <h2>Detail par type d'erreur</h2>
    <table>
        <thead><tr><th>Table</th><th>Type d'erreur</th><th>Lignes</th></tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    <div class="ftr">
        <p>Plateforme de Pilotage de la Qualite des Donnees - Orange Tunisie</p>
        <p>PFE 2026 - Malek - ESB</p>
    </div></body></html>"""
