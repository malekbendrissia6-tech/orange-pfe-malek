from src.database import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    print("=== fact_ventes ===")
    r = conn.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='fact_ventes' ORDER BY ordinal_position"
    ))
    for row in r:
        print(" ", row[0], "-", row[1])

    print("=== fact_objectifs ===")
    r2 = conn.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='fact_objectifs' ORDER BY ordinal_position"
    ))
    for row in r2:
        print(" ", row[0], "-", row[1])
