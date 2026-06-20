from src.database import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    # Check ALL columns of fact_objectifs
    r = conn.execute(text("SELECT * FROM fact_objectifs LIMIT 3"))
    print("=== fact_objectifs sample ===")
    keys = r.keys()
    print("Columns:", list(keys))
    for row in r:
        print(" ", dict(zip(keys, row)))

    # Check ventes by month for real
    r2 = conn.execute(text(
        "SELECT TO_CHAR(date_vente,'YYYY-MM') as m, "
        "ROUND(SUM(first_month_bill)::numeric,0) as realise, COUNT(*) as n "
        "FROM fact_ventes GROUP BY TO_CHAR(date_vente,'YYYY-MM') ORDER BY m"
    ))
    print("=== ventes par mois ===")
    for row in r2:
        print(" ", row[0], "| realise:", row[1], "| ventes:", row[2])
