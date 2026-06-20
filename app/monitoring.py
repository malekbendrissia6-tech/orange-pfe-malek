"""
=============================================================
  FICHIER : app/monitoring.py
  ROLE   : Interface de monitoring qualite - Data Engineer
  PROJET : PFE Orange Tunisie
=============================================================

Pages :
    1. Vue d'ensemble  : KPIs qualite globaux
    2. Detail par table: Analyse par table
    3. Alertes qualite : Problemes critiques
    4. Explorateur     : Fichiers data/error/
    5. Historique      : Logs des executions
    6. Notifications   : Rapports email Gmail
=============================================================
"""

import smtplib
import streamlit as st
import pandas as pd
import plotly.express as px
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from datetime import datetime

# ==================================================================
# CONFIGURATION
# ==================================================================
PROJECT_ROOT = Path(__file__).parent.parent
ERROR_DIR    = PROJECT_ROOT / "data" / "error"
INPUT_DIR    = PROJECT_ROOT / "data" / "input"
OUTPUT_DIR   = PROJECT_ROOT / "data" / "output"
LOGS_DIR     = PROJECT_ROOT / "logs"

TABLES = [
    "ventes_contrats", "offres", "vendeurs", "boutiques",
    "groupes", "articles", "ref_objectifs", "objectifs",
]

st.set_page_config(
    page_title="Data Quality Monitoring - Orange Tunisie",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================================================================
# CSS PREMIUM - Charte Orange Tunisie
# ==================================================================
st.markdown("""
<style>
/* IMPORT GOOGLE FONTS - Inter + Material Symbols */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');

/* === FORCER LES ICONES MATERIAL A S'AFFICHER COMME ICONES === */
.material-symbols-outlined,
.material-symbols-rounded,
.material-icons,
.material-icons-outlined,
[class*="material-symbols"],
[data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Outlined', 'Material Icons' !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 20px !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    display: inline-block !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: 'liga' !important;
    -webkit-font-smoothing: antialiased !important;
    text-rendering: optimizeLegibility !important;
    font-feature-settings: 'liga' !important;
}

/* Cache les elements Streamlit non necessaires */
[data-testid="stDeployButton"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }

/* Force la sidebar a etre visible */
section[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    min-width: 250px !important;
    transform: none !important;
}

[data-testid="collapsedControl"] {
    display: block !important;
    visibility: visible !important;
}

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
    max-width: 95% !important;
}

/* TYPOGRAPHIE INTER */
html, body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

p, span, div, label {
    font-family: 'Inter', sans-serif !important;
}

h1 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 32px !important;
    color: #1A1A1A !important;
}

h2 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 24px !important;
    color: #1A1A1A !important;
    border-bottom: 3px solid #FF6600 !important;
    padding-bottom: 8px !important;
}

h3 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    color: #595959 !important;
}

/* METRIQUES */
[data-testid="stMetricValue"] {
    font-weight: 700 !important;
    font-size: 36px !important;
    color: #FF6600 !important;
}

/* BOUTONS */
.stButton > button {
    background: linear-gradient(135deg, #FF6600 0%, #FF9933 100%);
    color: white !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    border: none !important;
    padding: 10px 22px !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(255,102,0,0.3) !important;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(255,102,0,0.4) !important;
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FAFAFA 0%, #F0F0F0 100%);
    border-right: 1px solid #E0E0E0;
}

section[data-testid="stSidebar"] * { color: #333; }
section[data-testid="stSidebar"] h3 { color: #FF6600 !important; }
section[data-testid="stSidebar"] strong { color: #FF6600 !important; }

/* EXPANDERS - Style propre */
[data-testid="stExpander"] {
    background: white;
    border-radius: 8px;
    border-left: 3px solid #FF6600;
    margin: 10px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

[data-testid="stExpander"] summary {
    padding: 12px 16px !important;
    cursor: pointer !important;
    font-weight: 600 !important;
    color: #1A1A1A !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stExpander"] summary:hover {
    background: #FFF3E0 !important;
}

/* FOOTER */
.footer-pro {
    background: #1A1A1A;
    color: #888;
    padding: 20px 30px;
    border-radius: 10px;
    margin-top: 30px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
}

.footer-pro .brand {
    color: #FF6600 !important;
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 2px;
}
</style>
""", unsafe_allow_html=True)


# ==================================================================
# FONCTIONS HELPERS UI
# ==================================================================

def kpi_card(label: str, value: str, sublabel: str = "", color: str = "#FF6600") -> str:
    return f"""
    <div style="background: white;
                padding: 24px 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06);
                border-left: 4px solid {color};
                height: 100%;
                min-height: 140px;
                margin-bottom: 12px;"
         translate="no">
        <p style="font-size: 11px;
                  font-family: 'Inter', sans-serif;
                  font-weight: 600;
                  letter-spacing: 1.5px;
                  text-transform: uppercase;
                  color: #888;
                  margin: 0 0 12px 0;
                  white-space: nowrap;">{label}</p>
        <p style="font-size: 32px;
                  font-family: 'Inter', sans-serif;
                  font-weight: 700;
                  color: {color};
                  margin: 0;
                  line-height: 1;
                  letter-spacing: -1px;
                  white-space: nowrap;">{value}</p>
        <p style="font-size: 12px;
                  font-family: 'Inter', sans-serif;
                  color: #595959;
                  margin: 8px 0 0 0;
                  font-weight: 500;">{sublabel}</p>
    </div>
    """


def section_title(title: str, subtitle: str = "") -> str:
    sub = (
        f'<p style="color:#888; font-size:13px; margin:4px 0 0 0; '
        f'font-family:\'Inter\',sans-serif; font-weight:400;">{subtitle}</p>'
    ) if subtitle else ""
    return f"""
    <div style="border-left: 4px solid #FF6600;
                padding: 4px 0 4px 16px;
                margin: 24px 0 12px 0;"
         translate="no">
        <p style="font-size: 18px;
                  font-weight: 700;
                  color: #1A1A1A;
                  margin: 0;
                  font-family: 'Inter', sans-serif;
                  letter-spacing: -0.3px;">{title}</p>
        {sub}
    </div>
    """


def alert_box(message: str, level: str = "info", title: str = "") -> str:
    configs = {
        "danger":  {"bg": "#FFEBEE", "border": "#C62828", "label": "CRITIQUE"},
        "warning": {"bg": "#FFF3E0", "border": "#EF6C00", "label": "ATTENTION"},
        "success": {"bg": "#E8F5E9", "border": "#2E7D32", "label": "SUCCES"},
        "info":    {"bg": "#E3F2FD", "border": "#1565C0", "label": "INFORMATION"},
    }
    cfg = configs.get(level, configs["info"])
    label = title.upper() if title else cfg["label"]
    return f"""
    <div style="background: {cfg['bg']};
                border-left: 4px solid {cfg['border']};
                padding: 14px 18px;
                border-radius: 6px;
                margin: 10px 0;">
        <p style="font-size: 11px;
                  font-family: 'Inter', sans-serif;
                  font-weight: 700;
                  letter-spacing: 1.5px;
                  color: {cfg['border']};
                  margin: 0 0 4px 0;
                  text-transform: uppercase;">{label}</p>
        <p style="margin: 0;
                  font-family: 'Inter', sans-serif;
                  color: #1A1A1A;
                  font-size: 14px;
                  font-weight: 500;">{message}</p>
    </div>
    """


# ==================================================================
# FONCTIONS UTILITAIRES
# ==================================================================

def list_error_files() -> list:
    if not ERROR_DIR.exists():
        return []
    return sorted(ERROR_DIR.glob("*.xlsx"))


def parse_error_filename(filepath: Path) -> dict:
    stem = filepath.stem
    for table in TABLES:
        if stem.startswith(table + "_"):
            return {"table": table, "type": stem[len(table) + 1:], "file": filepath}
    return {"table": "unknown", "type": stem, "file": filepath}


@st.cache_data
def load_error_stats() -> pd.DataFrame:
    stats = []
    for fp in list_error_files():
        info = parse_error_filename(fp)
        try:
            df = pd.read_excel(fp)
            info["rows"]     = len(df)
            info["size_kb"]  = round(fp.stat().st_size / 1024, 1)
            info["modified"] = datetime.fromtimestamp(fp.stat().st_mtime)
        except Exception:
            info["rows"] = info["size_kb"] = 0
            info["modified"] = None
        stats.append(info)
    return pd.DataFrame(stats)


def count_log_files() -> int:
    return len(list(LOGS_DIR.glob("*.log"))) if LOGS_DIR.exists() else 0


def get_severity(error_type: str) -> str:
    if "rows_dropped" in error_type or "duplicates" in error_type:
        return "CRITIQUE"
    if "missing" in error_type:
        return "ATTENTION"
    return "INFO"


def send_email(expediteur: str, mot_de_passe: str, destinataire: str,
               sujet: str, corps_html: str, pieces_jointes: list = None):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"]    = expediteur
        msg["To"]      = destinataire
        msg.attach(MIMEText(corps_html, "html"))
        if pieces_jointes:
            for filepath in pieces_jointes:
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


def generate_quality_report_html(error_stats_df: pd.DataFrame) -> str:
    total_errors = int(error_stats_df["rows"].sum()) if not error_stats_df.empty else 0
    rows_html = ""
    if not error_stats_df.empty:
        for _, row in error_stats_df.iterrows():
            rows_html += f"""
            <tr>
                <td>{row['table']}</td>
                <td>{row['type']}</td>
                <td><b>{int(row['rows']):,}</b></td>
            </tr>"""
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
    <div class="hdr">
        <h1>ORANGE TUNISIE</h1>
        <p style="margin:6px 0 0 0;">Rapport Qualite des Donnees</p>
    </div>
    <div class="stat">
        <h3 style="margin:0;color:#CC5200;">Synthese</h3>
        <p><b>Total erreurs detectees :</b> {total_errors:,} lignes</p>
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
    </div>
    </body></html>"""


# ==================================================================
# SIDEBAR
# ==================================================================
with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 24px 0;
                border-bottom: 2px solid #FF6600;
                margin-bottom: 24px;">
        <p style="font-size: 11px;
                  letter-spacing: 2px;
                  color: #FF6600;
                  font-family: 'Inter', sans-serif;
                  font-weight: 700;
                  margin: 0;">ORANGE TUNISIE</p>
        <p style="font-size: 14px;
                  color: #1A1A1A;
                  font-family: 'Inter', sans-serif;
                  font-weight: 600;
                  margin: 4px 0 0 0;">Monitoring Platform</p>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        [
            "Vue d'ensemble",
            "Detail par table",
            "Alertes qualite",
            "Explorateur d'erreurs",
            "Historique executions",
            "Notifications email",
            "Execution pipeline",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### A propos")
    st.markdown("""
    **Projet PFE**
    Plateforme de Pilotage de la Qualite des Donnees - Orange Tunisie

    **Etudiant(e)** : Malek
    **Ecole** : ESB
    **Annee** : 2026
    """)

    st.markdown("---")
    if st.button("Rafraichir les donnees"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Mis a jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# ==================================================================
# PAGE 1 : VUE D'ENSEMBLE
# ==================================================================
if page == "Vue d'ensemble":
    st.markdown("""
    <div style="background: linear-gradient(135deg, #FF6600 0%, #FF9933 100%);
                padding: 32px 40px;
                border-radius: 12px;
                margin-bottom: 32px;
                box-shadow: 0 8px 24px rgba(255,102,0,0.15);"
         translate="no">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <p style="color: rgba(255,255,255,0.85);
                          font-family: 'Inter', sans-serif;
                          font-size: 13px;
                          letter-spacing: 3px;
                          margin: 0;
                          font-weight: 500;
                          text-transform: uppercase;">ORANGE TUNISIE</p>
                <h1 style="color: white !important;
                           font-size: 32px !important;
                           margin: 8px 0 0 0 !important;
                           font-weight: 700 !important;">Data Quality Monitoring</h1>
                <p style="color: rgba(255,255,255,0.9);
                          font-family: 'Inter', sans-serif;
                          margin: 8px 0 0 0;
                          font-size: 15px;">Plateforme de supervision des donnees</p>
            </div>
            <div style="text-align: right; color: white;">
                <p style="margin: 0; font-size: 12px; opacity: 0.85; letter-spacing: 1px;
                          font-family: 'Inter', sans-serif; font-weight: 500;">EN LIGNE</p>
                <p style="margin: 4px 0 0 0; font-size: 14px; font-weight: 600;
                          font-family: 'Inter', sans-serif;">""" + datetime.now().strftime("%d %b %Y, %H:%M") + """</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    error_df = load_error_stats()

    total_errors    = int(error_df["rows"].sum()) if not error_df.empty else 0
    total_files     = len(error_df)
    tables_with_err = error_df["table"].nunique() if not error_df.empty else 0
    total_logs      = count_log_files()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(kpi_card("TOTAL ERREURS", f"{total_errors:,}", "lignes detectees"),
                    unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_card("FICHIERS", f"{total_files}", "rapports d'erreurs"),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_card("TABLES", f"{tables_with_err}/{len(TABLES)}", "tables concernees"),
                    unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_card("LOGS", f"{total_logs}", "executions enregistrees"),
                    unsafe_allow_html=True)

    st.markdown("---")

    if error_df.empty:
        st.markdown(
            alert_box(
                "Aucune erreur detectee. Lance le pipeline avec <code>python main.py</code>.",
                level="info",
            ),
            unsafe_allow_html=True,
        )
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(section_title("Erreurs par table"), unsafe_allow_html=True)
            by_table = error_df.groupby("table")["rows"].sum().reset_index()
            by_table.columns = ["Table", "Nombre d'erreurs"]
            fig = px.bar(by_table, x="Table", y="Nombre d'erreurs",
                         color_discrete_sequence=["#FF6600"], text="Nombre d'erreurs")
            fig.update_traces(textposition="outside")
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", font_color="#1A1A1A")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown(section_title("Types d'erreurs detectes"), unsafe_allow_html=True)
            by_type = error_df.groupby("type")["rows"].sum().reset_index()
            by_type.columns = ["Type", "Nombre"]
            by_type = by_type.sort_values("Nombre", ascending=True)
            fig = px.bar(by_type, x="Nombre", y="Type", orientation="h",
                         color_discrete_sequence=["#FF9933"])
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", font_color="#1A1A1A")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown(section_title("Detail des fichiers d'erreurs"), unsafe_allow_html=True)
        display_df = error_df[["table", "type", "rows", "size_kb", "modified"]].copy()
        display_df.columns = ["Table", "Type d'erreur", "Lignes", "Taille (Ko)", "Modifie le"]
        display_df = display_df.sort_values("Lignes", ascending=False)
        st.dataframe(display_df, hide_index=True, use_container_width=True)


# ==================================================================
# PAGE 2 : DETAIL PAR TABLE
# ==================================================================
elif page == "Detail par table":
    st.markdown("""
    <div style="background: linear-gradient(135deg, #FF6600 0%, #FF9933 100%);
                padding: 24px 32px; border-radius: 12px; margin-bottom: 24px;
                box-shadow: 0 8px 24px rgba(255,102,0,0.15);" translate="no">
        <p style="color: rgba(255,255,255,0.85); font-size: 12px; letter-spacing: 2px;
                  margin: 0; font-weight: 500; text-transform: uppercase;">ORANGE TUNISIE</p>
        <h1 style="color: white !important; font-size: 26px !important;
                   margin: 4px 0 0 0 !important; font-weight: 700 !important;">Detail par Table</h1>
        <p style="color: rgba(255,255,255,0.85); font-size: 13px;
                  margin: 6px 0 0 0; font-weight: 400;">Analyse detaillee de la qualite pour chaque table</p>
    </div>
    """, unsafe_allow_html=True)

    table_choisie = st.selectbox("Selectionne une table", TABLES)
    error_df = load_error_stats()

    if error_df.empty:
        st.warning("Aucun fichier d'erreur trouve. Lance d'abord le pipeline.")
    else:
        table_errors = error_df[error_df["table"] == table_choisie]

        if table_errors.empty:
            st.markdown(
                alert_box(f"Aucune erreur pour la table <b>{table_choisie}</b>. Cette table est parfaitement propre.",
                          level="success"),
                unsafe_allow_html=True,
            )
        else:
            total = int(table_errors["rows"].sum())
            source_file = INPUT_DIR / f"{table_choisie}.xlsx"
            dataset_size = "N/A"
            error_rate = "N/A"
            if source_file.exists():
                try:
                    df_source = pd.read_excel(source_file)
                    dataset_size = f"{len(df_source):,}"
                    error_rate = f"{(total / len(df_source)) * 100:.1f}%"
                except Exception:
                    pass

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(kpi_card("TOTAL ERREURS", f"{total:,}", "lignes problematiques"),
                            unsafe_allow_html=True)
            with c2:
                st.markdown(kpi_card("TAILLE DATASET", dataset_size, "lignes source"),
                            unsafe_allow_html=True)
            with c3:
                st.markdown(kpi_card("TAUX D'ERREUR", error_rate, "du dataset"),
                            unsafe_allow_html=True)

            st.markdown("---")
            st.markdown(section_title(f"Types d'erreurs dans {table_choisie}"), unsafe_allow_html=True)

            for _, row in table_errors.sort_values("rows", ascending=False).iterrows():
                sev = get_severity(row["type"])
                level_map = {"CRITIQUE": "danger", "ATTENTION": "warning", "INFO": "info"}
                st.markdown(
                    alert_box(
                        f"<b>{row['type']}</b> &mdash; "
                        f"Lignes : <b>{int(row['rows']):,}</b> &nbsp;|&nbsp; "
                        f"Taille : {row['size_kb']} Ko &nbsp;|&nbsp; "
                        f"Modifie : {row['modified']}",
                        level=level_map.get(sev, "info"), title=sev,
                    ),
                    unsafe_allow_html=True,
                )


# ==================================================================
# PAGE 3 : ALERTES QUALITE
# ==================================================================
elif page == "Alertes qualite":
    st.markdown("""
    <div style="background: linear-gradient(135deg, #FF6600 0%, #FF9933 100%);
                padding: 24px 32px; border-radius: 12px; margin-bottom: 24px;
                box-shadow: 0 8px 24px rgba(255,102,0,0.15);" translate="no">
        <p style="color: rgba(255,255,255,0.85); font-size: 12px; letter-spacing: 2px;
                  margin: 0; font-weight: 500; text-transform: uppercase;">ORANGE TUNISIE</p>
        <h1 style="color: white !important; font-size: 26px !important;
                   margin: 4px 0 0 0 !important; font-weight: 700 !important;">Alertes Qualite</h1>
        <p style="color: rgba(255,255,255,0.85); font-size: 13px;
                  margin: 6px 0 0 0; font-weight: 400;">Problemes critiques necessitant une action immediate</p>
    </div>
    """, unsafe_allow_html=True)

    error_df = load_error_stats()

    if error_df.empty:
        st.info("Aucune alerte - lance le pipeline d'abord.")
    else:
        error_df["severity"] = error_df["type"].apply(get_severity)
        critiques = error_df[error_df["severity"] == "CRITIQUE"].sort_values("rows", ascending=False)
        warnings  = error_df[error_df["severity"] == "ATTENTION"].sort_values("rows", ascending=False)
        infos     = error_df[error_df["severity"] == "INFO"]

        crit_rows = int(critiques["rows"].sum()) if not critiques.empty else 0
        warn_rows = int(warnings["rows"].sum())  if not warnings.empty  else 0

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(kpi_card("CRITIQUES", str(len(critiques)), f"{crit_rows:,} lignes", color="#C62828"),
                        unsafe_allow_html=True)
        with c2:
            st.markdown(kpi_card("ATTENTION", str(len(warnings)), f"{warn_rows:,} lignes", color="#EF6C00"),
                        unsafe_allow_html=True)
        with c3:
            st.markdown(kpi_card("INFO", str(len(infos)), "alertes informatives", color="#1565C0"),
                        unsafe_allow_html=True)

        st.markdown("---")

        if not critiques.empty:
            st.markdown(section_title("Alertes CRITIQUES"), unsafe_allow_html=True)
            for _, row in critiques.iterrows():
                st.markdown(
                    alert_box(
                        f"<b>{row['table']} &mdash; {row['type']}</b><br>"
                        f"<b>{int(row['rows']):,} lignes</b> problematiques detectees.<br>"
                        f"<i style='color:#888'>Action : verifier le fichier source et corriger les donnees.</i>",
                        level="danger",
                    ),
                    unsafe_allow_html=True,
                )

        if not warnings.empty:
            st.markdown(section_title("Alertes ATTENTION"), unsafe_allow_html=True)
            for _, row in warnings.iterrows():
                st.markdown(
                    alert_box(
                        f"<b>{row['table']} &mdash; {row['type']}</b><br>"
                        f"<b>{int(row['rows']):,} lignes</b> avec valeurs manquantes.<br>"
                        f"<i style='color:#888'>Action : enrichir les donnees sources si possible.</i>",
                        level="warning",
                    ),
                    unsafe_allow_html=True,
                )


# ==================================================================
# PAGE 4 : EXPLORATEUR D'ERREURS
# ==================================================================
elif page == "Explorateur d'erreurs":
    st.markdown("""
    <div style="background: linear-gradient(135deg, #FF6600 0%, #FF9933 100%);
                padding: 24px 32px; border-radius: 12px; margin-bottom: 24px;
                box-shadow: 0 8px 24px rgba(255,102,0,0.15);" translate="no">
        <p style="color: rgba(255,255,255,0.85); font-size: 12px; letter-spacing: 2px;
                  margin: 0; font-weight: 500; text-transform: uppercase;">ORANGE TUNISIE</p>
        <h1 style="color: white !important; font-size: 26px !important;
                   margin: 4px 0 0 0 !important; font-weight: 700 !important;">Explorateur d'Erreurs</h1>
        <p style="color: rgba(255,255,255,0.85); font-size: 13px;
                  margin: 6px 0 0 0; font-weight: 400;">Visualisation directe des fichiers data/error/</p>
    </div>
    """, unsafe_allow_html=True)

    error_files = list_error_files()

    if not error_files:
        st.warning("Aucun fichier d'erreur. Lance le pipeline d'abord.")
    else:
        file_choisi = st.selectbox("Selectionne un fichier", [f.name for f in error_files])
        file_path   = ERROR_DIR / file_choisi

        try:
            df = pd.read_excel(file_path)
            size_kb = round(file_path.stat().st_size / 1024, 1)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(kpi_card("LIGNES", f"{len(df):,}", "enregistrements"),
                            unsafe_allow_html=True)
            with c2:
                st.markdown(kpi_card("COLONNES", str(len(df.columns)), "champs disponibles"),
                            unsafe_allow_html=True)
            with c3:
                st.markdown(kpi_card("TAILLE", f"{size_kb} Ko", "fichier Excel"),
                            unsafe_allow_html=True)

            st.markdown("---")

            search = st.text_input("Rechercher dans le fichier (optionnel)")
            if search:
                mask = df.astype(str).apply(
                    lambda x: x.str.contains(search, case=False, na=False)
                ).any(axis=1)
                df_filtered = df[mask]
                st.markdown(
                    alert_box(f"<b>{len(df_filtered)} lignes</b> correspondent a votre recherche.",
                              level="info"),
                    unsafe_allow_html=True,
                )
            else:
                df_filtered = df

            st.markdown(section_title("Apercu des donnees"), unsafe_allow_html=True)
            st.dataframe(df_filtered.head(100), use_container_width=True)

            if len(df_filtered) > 100:
                st.caption(f"Affichage de 100/{len(df_filtered):,} lignes. Telechargez pour tout voir.")

            with open(file_path, "rb") as f:
                st.download_button(
                    label=f"Telecharger {file_choisi}",
                    data=f,
                    file_name=file_choisi,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

        except Exception as e:
            st.error(f"Erreur de lecture : {e}")


# ==================================================================
# PAGE 5 : HISTORIQUE EXECUTIONS
# ==================================================================
elif page == "Historique executions":
    st.markdown("""
    <div style="background: linear-gradient(135deg, #FF6600 0%, #FF9933 100%);
                padding: 24px 32px; border-radius: 12px; margin-bottom: 24px;
                box-shadow: 0 8px 24px rgba(255,102,0,0.15);" translate="no">
        <p style="color: rgba(255,255,255,0.85); font-size: 12px; letter-spacing: 2px;
                  margin: 0; font-weight: 500; text-transform: uppercase;">ORANGE TUNISIE</p>
        <h1 style="color: white !important; font-size: 26px !important;
                   margin: 4px 0 0 0 !important; font-weight: 700 !important;">Historique des Executions</h1>
        <p style="color: rgba(255,255,255,0.85); font-size: 13px;
                  margin: 6px 0 0 0; font-weight: 400;">Logs horodates des executions du pipeline ETL</p>
    </div>
    """, unsafe_allow_html=True)

    if not LOGS_DIR.exists():
        st.warning("Aucun dossier logs trouve.")
    else:
        log_files = sorted(LOGS_DIR.glob("*.log"), reverse=True)

        if not log_files:
            st.info("Aucun fichier log. Lance le pipeline d'abord.")
        else:
            st.markdown(
                kpi_card("TOTAL EXECUTIONS", str(len(log_files)), "fichiers logs enregistres"),
                unsafe_allow_html=True,
            )

            st.markdown("---")

            table_filter = st.selectbox("Filtrer par table", ["Toutes"] + TABLES)
            filtered_logs = (
                [f for f in log_files if table_filter in f.name]
                if table_filter != "Toutes" else log_files
            )

            st.markdown(section_title(f"{len(filtered_logs)} fichiers logs trouves"), unsafe_allow_html=True)

            for log_file in filtered_logs[:20]:
                ts = datetime.fromtimestamp(log_file.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
                with st.expander(f"{log_file.name}  ({ts})"):
                    try:
                        with open(log_file, "r", encoding="utf-8") as f:
                            st.code(f.read(), language="text")
                    except Exception as e:
                        st.error(f"Erreur de lecture : {e}")


# ==================================================================
# PAGE 6 : NOTIFICATIONS EMAIL
# ==================================================================
elif page == "Notifications email":
    st.markdown("""
    <div style="background: linear-gradient(135deg, #FF6600 0%, #FF9933 100%);
                padding: 24px 32px; border-radius: 12px; margin-bottom: 24px;
                box-shadow: 0 8px 24px rgba(255,102,0,0.15);" translate="no">
        <p style="color: rgba(255,255,255,0.85); font-size: 12px; letter-spacing: 2px;
                  margin: 0; font-weight: 500; text-transform: uppercase;">ORANGE TUNISIE</p>
        <h1 style="color: white !important; font-size: 26px !important;
                   margin: 4px 0 0 0 !important; font-weight: 700 !important;">Notifications Email</h1>
        <p style="color: rgba(255,255,255,0.85); font-size: 13px;
                  margin: 6px 0 0 0; font-weight: 400;">Envoi de rapports qualite via Gmail SMTP</p>
    </div>
    """, unsafe_allow_html=True)

    for key, default in [
        ("email_exp", ""), ("email_pwd", ""),
        ("email_dest", ""), ("email_history", []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ---- SECTION 1 : CONFIGURATION ----
    st.markdown(section_title("Configuration Gmail", "Parametres de connexion Gmail SMTP"), unsafe_allow_html=True)
    st.markdown(
        alert_box(
            "1. Activez la <b>validation en 2 etapes</b> sur votre compte Google<br>"
            "2. Creez un <b>mot de passe d'application</b> : "
            "<a href='https://myaccount.google.com/apppasswords' target='_blank' "
            "style='color:#1565C0'>myaccount.google.com/apppasswords</a><br>"
            "3. Utilisez ce code (16 caracteres) - <b>pas votre mot de passe Google</b>",
            level="info", title="Pre-requis Gmail",
        ),
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.session_state["email_exp"] = st.text_input(
            "Email expediteur (Gmail)",
            value=st.session_state["email_exp"],
            placeholder="monitoring.orange@gmail.com",
        )
        st.session_state["email_dest"] = st.text_input(
            "Email destinataire par defaut",
            value=st.session_state["email_dest"],
            placeholder="data.engineer@orange.tn",
        )
    with col2:
        st.session_state["email_pwd"] = st.text_input(
            "Mot de passe d'application Gmail",
            value=st.session_state["email_pwd"],
            type="password",
            placeholder="xxxx xxxx xxxx xxxx",
        )
        st.write("")
        st.write("")
        if st.button("Tester la connexion"):
            if not all([st.session_state["email_exp"],
                        st.session_state["email_pwd"],
                        st.session_state["email_dest"]]):
                st.warning("Remplis tous les champs avant de tester.")
            else:
                ok, err = send_email(
                    st.session_state["email_exp"],
                    st.session_state["email_pwd"],
                    st.session_state["email_dest"],
                    "Test connexion - Orange Tunisie Monitoring",
                    "<h2>Connexion Gmail OK !</h2><p>Le systeme de notification est operationnel.</p>",
                )
                if ok:
                    st.success("Connexion Gmail reussie ! Email de test envoye.")
                else:
                    st.error(f"Echec de connexion : {err}")
                    if "Username and Password not accepted" in err or "535" in err:
                        st.warning(
                            "Mot de passe refuse par Gmail. Verifiez que :\n"
                            "1. La validation en 2 etapes est ACTIVEE sur votre compte Google\n"
                            "2. Vous utilisez un MOT DE PASSE D'APPLICATION (16 caracteres sans espaces),\n"
                            "   pas votre mot de passe Google habituel.\n"
                            "   Creez-en un sur : https://myaccount.google.com/apppasswords"
                        )
                    elif "Connection refused" in err or "timed out" in err.lower():
                        st.warning("Connexion reseau echouee. Verifiez votre connexion internet.")
                    elif "ssl" in err.lower() or "certificate" in err.lower():
                        st.warning("Erreur SSL. Essayez depuis un autre reseau (evitez les proxys).")

    st.markdown("---")

    # ---- SECTION 2 : ENVOYER UN RAPPORT ----
    st.markdown(section_title("Envoyer un rapport", "Composez et envoyez un rapport qualite"), unsafe_allow_html=True)

    error_df = load_error_stats()

    col1, col2 = st.columns([2, 1])
    with col1:
        tables_selectionnees = st.multiselect(
            "Tables a inclure dans le rapport",
            TABLES, default=TABLES,
        )
    with col2:
        type_rapport = st.selectbox(
            "Type de rapport",
            ["Quotidien", "Alerte erreurs", "Personnalise"],
        )

    note_perso = ""
    if type_rapport == "Personnalise":
        note_perso = st.text_area("Note personnalisee (optionnel)", height=80)

    destinataire_envoi = st.text_input(
        "Destinataire (laisser vide pour utiliser celui par defaut)",
        value=st.session_state["email_dest"],
    )

    with st.expander("Apercu du rapport HTML"):
        if not error_df.empty:
            df_filtered = error_df[error_df["table"].isin(tables_selectionnees)]
        else:
            df_filtered = error_df
        preview_html = generate_quality_report_html(df_filtered)
        st.components.v1.html(preview_html, height=420, scrolling=True)

    if st.button("Envoyer le rapport maintenant", type="primary"):
        if not all([st.session_state["email_exp"], st.session_state["email_pwd"]]):
            st.error("Configure d'abord l'email expediteur et le mot de passe.")
        elif not destinataire_envoi:
            st.error("Renseigne un email destinataire.")
        else:
            sujet = {
                "Quotidien":      f"[Orange Tunisie] Rapport qualite quotidien - {datetime.now().strftime('%d/%m/%Y')}",
                "Alerte erreurs": f"[Orange Tunisie] ALERTE : Erreurs detectees - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                "Personnalise":   f"[Orange Tunisie] Rapport personnalise - {datetime.now().strftime('%d/%m/%Y')}",
            }[type_rapport]

            corps = generate_quality_report_html(df_filtered)
            if note_perso:
                corps = corps.replace("</body>", f"<p><i>{note_perso}</i></p></body>")

            with st.spinner("Envoi en cours..."):
                ok, err = send_email(
                    st.session_state["email_exp"],
                    st.session_state["email_pwd"],
                    destinataire_envoi, sujet, corps,
                )

            if ok:
                st.success(f"Rapport envoye avec succes a {destinataire_envoi} !")
                st.session_state["email_history"].append({
                    "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "destinataire": destinataire_envoi,
                    "type": type_rapport,
                    "statut": "OK",
                })
            else:
                st.error(f"Echec de l'envoi : {err}")
                st.session_state["email_history"].append({
                    "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "destinataire": destinataire_envoi,
                    "type": type_rapport,
                    "statut": f"ERREUR : {err[:60]}",
                })

    st.markdown("---")

    # ---- SECTION 3 : ALERTES AUTOMATIQUES ----
    st.markdown(section_title("Alertes automatiques", "Declenchement selon un seuil d'erreurs critiques"), unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        seuil = st.slider(
            "Seuil d'alerte (nombre d'erreurs critiques)",
            min_value=0, max_value=5000, value=100, step=50,
        )
    with col2:
        alertes_actives = st.checkbox("Activer les alertes automatiques", value=False)

    if alertes_actives and not error_df.empty:
        critiques_df = error_df[error_df["type"].apply(
            lambda t: "rows_dropped" in t or "duplicates" in t
        )]
        total_crit = int(critiques_df["rows"].sum()) if not critiques_df.empty else 0
        if total_crit >= seuil:
            st.markdown(
                alert_box(
                    f"Seuil depasse : {total_crit:,} erreurs critiques "
                    f"&gt;= seuil de {seuil}. Envoie une alerte via le bouton ci-dessus.",
                    level="danger", title="Seuil depasse",
                ),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                alert_box(
                    f"{total_crit:,} erreurs critiques &lt; seuil de {seuil}. Tout est normal.",
                    level="success", title="Sous le seuil",
                ),
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ---- SECTION 4 : HISTORIQUE ----
    st.markdown(section_title("Historique des envois", "Emails envoyes dans cette session"), unsafe_allow_html=True)
    if st.session_state["email_history"]:
        hist_df = pd.DataFrame(st.session_state["email_history"])
        st.dataframe(hist_df, hide_index=True, use_container_width=True)
    else:
        st.caption("Aucun email envoye dans cette session.")


# ==================================================================
# PAGE 7 : EXECUTION PIPELINE (lancer pipeline et tests sans terminal)
# ==================================================================
elif page == "Execution pipeline":
    import subprocess
    import sys

    st.markdown("""
    <div style="background: linear-gradient(135deg, #FF6600 0%, #FF9933 100%);
                padding: 24px 32px;
                border-radius: 12px;
                margin-bottom: 24px;
                box-shadow: 0 8px 24px rgba(255,102,0,0.15);"
         translate="no">
        <p style="color: rgba(255,255,255,0.85);
                  font-size: 12px;
                  letter-spacing: 2px;
                  margin: 0;
                  font-weight: 500;
                  text-transform: uppercase;">
            ORANGE TUNISIE
        </p>
        <h1 style="color: white !important;
                   font-size: 26px !important;
                   margin: 4px 0 0 0 !important;
                   font-weight: 700 !important;">
            Execution Pipeline
        </h1>
        <p style="color: rgba(255,255,255,0.85);
                  font-size: 13px;
                  margin: 6px 0 0 0;
                  font-weight: 400;">
            Lancement du pipeline ETL et des tests unitaires
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Initialiser session state pour les sorties
    if "pipeline_output" not in st.session_state:
        st.session_state["pipeline_output"] = ""
    if "tests_output" not in st.session_state:
        st.session_state["tests_output"] = ""

    # ==== SECTION 1 : LANCER LE PIPELINE ====
    st.markdown(section_title("Lancement du Pipeline ETL",
                              "Traite les 8 tables et genere les fichiers nettoyes"),
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        mode_execution = st.selectbox(
            "Mode d'execution",
            ["Pipeline complet (8 tables)", "Table specifique"],
        )

        table_choisie = None
        if mode_execution == "Table specifique":
            table_choisie = st.selectbox("Choisir la table", TABLES)

    with col2:
        st.write("")
        st.write("")
        if st.button("LANCER LE PIPELINE", key="btn_run_pipeline"):
            cmd = [sys.executable, "main.py"]
            if table_choisie:
                cmd.append(table_choisie)

            with st.spinner("Pipeline en cours d'execution... (peut prendre 1-2 minutes)"):
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=str(PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                    if result.returncode == 0:
                        st.session_state["pipeline_output"] = result.stdout
                        st.success("Pipeline execute avec succes !")
                        st.cache_data.clear()
                    else:
                        st.session_state["pipeline_output"] = result.stdout + "\n\nERREUR:\n" + result.stderr
                        st.error(f"Echec du pipeline (code {result.returncode})")
                except subprocess.TimeoutExpired:
                    st.error("Pipeline trop long (timeout 5 min)")
                except Exception as e:
                    st.error(f"Erreur : {e}")

    if st.session_state["pipeline_output"]:
        with st.expander("Voir la sortie du pipeline", expanded=False):
            st.code(st.session_state["pipeline_output"], language="text")

    st.markdown("---")

    # ==== SECTION 2 : LANCER LES TESTS ====
    st.markdown(section_title("Lancement des Tests Unitaires",
                              "Execute les 21 tests pytest"),
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        with_coverage = st.checkbox("Inclure la couverture de code", value=False)

    with col2:
        st.write("")
        st.write("")
        if st.button("LANCER LES TESTS", key="btn_run_tests"):
            cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
            if with_coverage:
                cmd.extend(["--cov=src", "--cov-report=term-missing"])

            with st.spinner("Tests en cours d'execution..."):
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=str(PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                    st.session_state["tests_output"] = result.stdout + result.stderr

                    if result.returncode == 0:
                        st.success("Tous les tests passent !")
                    else:
                        st.warning(f"Certains tests ont echoue (code {result.returncode})")
                except subprocess.TimeoutExpired:
                    st.error("Tests trop longs (timeout 5 min)")
                except Exception as e:
                    st.error(f"Erreur : {e}")

    if st.session_state["tests_output"]:
        output = st.session_state["tests_output"]
        if "passed" in output:
            import re
            match = re.search(r"(\d+) passed", output)
            nb_passed = match.group(1) if match else "?"

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(kpi_card("TESTS PASSES", nb_passed, "tests reussis"),
                            unsafe_allow_html=True)
            with c2:
                cov_match = re.search(r"TOTAL.*?(\d+)%", output)
                if cov_match:
                    st.markdown(kpi_card("COUVERTURE", f"{cov_match.group(1)}%", "code testee"),
                                unsafe_allow_html=True)
            with c3:
                time_match = re.search(r"in ([\d.]+)s", output)
                if time_match:
                    st.markdown(kpi_card("DUREE", f"{time_match.group(1)}s", "execution totale"),
                                unsafe_allow_html=True)

        with st.expander("Voir la sortie complete des tests", expanded=False):
            st.code(st.session_state["tests_output"], language="text")

    st.markdown("---")

    # ==== SECTION 3 : ETAT DU SYSTEME ====
    st.markdown(section_title("Etat du systeme", "Statut des fichiers et dossiers"),
                unsafe_allow_html=True)

    nb_input  = len(list(INPUT_DIR.glob("*.xlsx")))  if INPUT_DIR.exists()  else 0
    nb_output = len(list(OUTPUT_DIR.glob("*.xlsx"))) if OUTPUT_DIR.exists() else 0
    nb_error  = len(list(ERROR_DIR.glob("*.xlsx")))  if ERROR_DIR.exists()  else 0
    nb_logs   = count_log_files()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(kpi_card("FICHIERS INPUT",  f"{nb_input}/8",  "tables sources"),
                    unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_card("FICHIERS OUTPUT", f"{nb_output}/8", "tables nettoyees"),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_card("FICHIERS ERROR",  f"{nb_error}",    "rapports d'erreurs"),
                    unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_card("FICHIERS LOGS",   f"{nb_logs}",     "executions"),
                    unsafe_allow_html=True)


# ==================================================================
# FOOTER
# ==================================================================
st.markdown("""
<div class="footer-pro">
    <div>
        <div class="brand">ORANGE TUNISIE</div>
        <div style="color:#666; margin-top:4px; font-family:'Inter',sans-serif;">
            Plateforme de Pilotage de la Qualite des Donnees
        </div>
    </div>
    <div style="color:#555; text-align:right; font-family:'Inter',sans-serif;">
        PFE 2026 &nbsp;&middot;&nbsp; Malek &nbsp;&middot;&nbsp; ESB<br>
        <span style="font-size:11px;">&copy; 2026 Orange Tunisie. Tous droits reserves.</span>
    </div>
</div>
""", unsafe_allow_html=True)
