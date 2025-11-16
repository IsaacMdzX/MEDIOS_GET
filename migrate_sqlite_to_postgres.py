import os
import sqlite3
from pathlib import Path

# Expect DATABASE_URL to be set in environment
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL no está definido. Exporta la variable o crea un .env")

import psycopg2

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"

# Open SQLite source
src = sqlite3.connect(DB_PATH)
src.row_factory = sqlite3.Row
sc = src.cursor()
sc.execute("SELECT COUNT(*) AS cnt FROM movimientos")
sqlite_count = sc.fetchone()[0]
print(f"sqlite_count={sqlite_count}")

# Open Postgres target
pg = psycopg2.connect(DATABASE_URL)
pg.autocommit = False
pc = pg.cursor()
pc.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, tipo VARCHAR(20) NOT NULL, concepto TEXT NOT NULL, monto NUMERIC(10,2) NOT NULL, fecha DATE NOT NULL)")
pc.execute("SELECT COUNT(*) FROM movimientos")
pg_count = pc.fetchone()[0]
print(f"pg_count_before={pg_count}")

if sqlite_count == 0:
    print("No hay datos en SQLite para migrar.")
    src.close(); pg.close()
    raise SystemExit(0)

if pg_count > 0:
    print("PostgreSQL ya tiene datos; por seguridad no migro automáticamente.")
    src.close(); pg.close()
    raise SystemExit(0)

# Copy rows
sc.execute("SELECT tipo, concepto, monto, fecha FROM movimientos ORDER BY id")
rows = sc.fetchall()
insert_sql = "INSERT INTO movimientos (tipo, concepto, monto, fecha) VALUES (%s, %s, %s, %s)"
for r in rows:
    pc.execute(insert_sql, (r["tipo"], r["concepto"], float(r["monto"]), r["fecha"]))

pg.commit()
print(f"Migración completada: {len(rows)} filas copiadas.")

# Report final count
pc.execute("SELECT COUNT(*) FROM movimientos")
print(f"pg_count_after={pc.fetchone()[0]}")

sc.close(); src.close(); pc.close(); pg.close()
