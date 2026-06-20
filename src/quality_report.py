"""
=============================================================
  MODULE : quality_report.py
  RÔLE  : Génération de rapports qualité automatiques
  PROJET: PFE Orange Tunisie - Pipeline de nettoyage
=============================================================

Génère 2 types de rapports après chaque nettoyage :
    1. Rapport HTML visuel (avec barres de progression colorées)
    2. Rapport Excel (3 feuilles - pour annexes PFE)

Ces rapports permettent de prouver la qualité du nettoyage
et sont idéaux pour le mémoire et la soutenance.
=============================================================
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


# Template HTML professionnel (couleurs Orange Tunisie)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Rapport Qualité - {table_name}</title>
<style>
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    margin: 0; padding: 30px; background: #f4f6f8; color: #222;
  }}
  h1 {{ color: #ff6600; border-bottom: 3px solid #ff6600; padding-bottom: 10px; }}
  h2 {{ color: #333; margin-top: 30px; }}
  .card {{
    background: #fff; padding: 20px; border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08); margin-bottom: 20px;
  }}
  .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
  .metric {{
    background: linear-gradient(135deg, #ff6600 0%, #ff9933 100%);
    color: #fff; padding: 20px; border-radius: 8px; text-align: center;
  }}
  .metric .value {{ font-size: 28px; font-weight: bold; }}
  .metric .label {{ font-size: 13px; opacity: 0.9; margin-top: 5px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  th {{ background: #333; color: #fff; padding: 10px; text-align: left; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #eee; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .bar-container {{
    background: #e0e0e0; border-radius: 4px; height: 20px; overflow: hidden;
    position: relative; min-width: 150px;
  }}
  .bar {{
    height: 100%;
    background: linear-gradient(90deg, #4caf50, #8bc34a);
  }}
  .bar.warn {{ background: linear-gradient(90deg, #ff9800, #ffc107); }}
  .bar.bad {{ background: linear-gradient(90deg, #f44336, #e57373); }}
  .footer {{ margin-top: 40px; text-align: center; color: #888; font-size: 12px; }}
</style>
</head>
<body>

<h1>Rapport Qualité — {table_name}</h1>
<p>Généré le {generated_at}</p>

<div class="card">
  <h2>Résumé global</h2>
  <div class="metrics">
    <div class="metric">
      <div class="value">{initial_rows:,}</div>
      <div class="label">Lignes initiales</div>
    </div>
    <div class="metric">
      <div class="value">{final_rows:,}</div>
      <div class="label">Lignes finales</div>
    </div>
    <div class="metric">
      <div class="value">{rows_removed:,}</div>
      <div class="label">Lignes supprimées</div>
    </div>
    <div class="metric">
      <div class="value">{retention_pct:.1f}%</div>
      <div class="label">Taux de rétention</div>
    </div>
  </div>
</div>

<div class="card">
  <h2>Complétude par colonne (après nettoyage)</h2>
  <table>
    <thead>
      <tr><th>Colonne</th><th>Type</th><th>Non-null</th><th>NaN</th><th>% Complétude</th></tr>
    </thead>
    <tbody>
      {completeness_rows}
    </tbody>
  </table>
</div>

<div class="card">
  <h2>Transformations appliquées ({n_transformations})</h2>
  <table>
    <thead>
      <tr><th>#</th><th>Étape</th><th>Détails</th></tr>
    </thead>
    <tbody>
      {transformations_rows}
    </tbody>
  </table>
</div>

<div class="footer">
  Pipeline de nettoyage — Projet PFE Orange Tunisie
</div>

</body>
</html>
"""


def _bar(pct: float) -> str:
    """Génère une barre de progression colorée selon le pourcentage."""
    cls = "" if pct >= 95 else ("warn" if pct >= 80 else "bad")
    return (
        f'<div class="bar-container">'
        f'<div class="bar {cls}" style="width:{pct:.1f}%"></div>'
        f'</div>'
    )


def generate_report(
    df_clean: pd.DataFrame,
    summary: Dict[str, Any],
    table_name: str,
    output_dir: str = "data/reports",
) -> str:
    """
    Génère un rapport HTML et un rapport Excel associé.

    Args:
        df_clean: DataFrame nettoyé
        summary: dictionnaire des métriques de nettoyage
        table_name: nom de la table (ex: 'ventes_contrats')
        output_dir: dossier où sauvegarder les rapports

    Returns:
        Chemin du fichier HTML généré.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # ==================================================
    # Partie 1 : Calcul de la complétude par colonne
    # ==================================================
    rows_html = []
    for col in df_clean.columns:
        nn = int(df_clean[col].notna().sum())
        nans = int(df_clean[col].isna().sum())
        pct = (nn / len(df_clean) * 100) if len(df_clean) else 0
        rows_html.append(
            f"<tr><td><b>{col}</b></td><td>{df_clean[col].dtype}</td>"
            f"<td>{nn:,}</td><td>{nans:,}</td>"
            f"<td>{_bar(pct)} {pct:.1f}%</td></tr>"
        )
    completeness_rows = "\n".join(rows_html)

    # ==================================================
    # Partie 2 : Liste des transformations
    # ==================================================
    trans_html = []
    for i, t in enumerate(summary.get("transformations", []), 1):
        t_copy = dict(t)  # copie pour ne pas modifier l'original
        step = t_copy.pop("step", "?")
        details = ", ".join(f"<b>{k}</b>: {v}" for k, v in t_copy.items())
        trans_html.append(f"<tr><td>{i}</td><td>{step}</td><td>{details}</td></tr>")
    transformations_rows = "\n".join(trans_html)

    # ==================================================
    # Partie 3 : Génération du HTML
    # ==================================================
    retention = (summary["final_rows"] / summary["initial_rows"] * 100) if summary["initial_rows"] else 0
    html = HTML_TEMPLATE.format(
        table_name=table_name,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        initial_rows=summary["initial_rows"],
        final_rows=summary["final_rows"],
        rows_removed=summary["rows_removed"],
        retention_pct=retention,
        completeness_rows=completeness_rows,
        transformations_rows=transformations_rows,
        n_transformations=len(summary.get("transformations", [])),
    )

    html_path = Path(output_dir) / f"rapport_{table_name}.html"
    html_path.write_text(html, encoding="utf-8")

    # ==================================================
    # Partie 4 : Génération du rapport Excel (3 feuilles)
    # ==================================================
    excel_path = Path(output_dir) / f"rapport_{table_name}.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:

        # Feuille 1 : Résumé global
        summary_df = pd.DataFrame([{
            "Table": table_name,
            "Lignes initiales": summary["initial_rows"],
            "Lignes finales": summary["final_rows"],
            "Lignes supprimées": summary["rows_removed"],
            "Taux rétention %": round(retention, 2),
            "NaN initiaux": summary["initial_nulls"],
            "NaN finaux": summary["final_nulls"],
        }])
        summary_df.to_excel(writer, sheet_name="Résumé", index=False)

        # Feuille 2 : Complétude par colonne
        comp_data = []
        for col in df_clean.columns:
            nn = int(df_clean[col].notna().sum())
            comp_data.append({
                "Colonne": col,
                "Type": str(df_clean[col].dtype),
                "Non-null": nn,
                "NaN": int(df_clean[col].isna().sum()),
                "Complétude %": round(nn / len(df_clean) * 100, 2) if len(df_clean) else 0,
            })
        pd.DataFrame(comp_data).to_excel(writer, sheet_name="Complétude", index=False)

        # Feuille 3 : Liste des transformations
        if summary.get("transformations"):
            pd.DataFrame(summary["transformations"]).to_excel(
                writer, sheet_name="Transformations", index=False
            )

    return str(html_path)