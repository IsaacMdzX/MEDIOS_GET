from flask import Flask, render_template, request, redirect, jsonify
import os
import sqlite3
from urllib.parse import urlparse
from pathlib import Path
import time
import logging
import traceback
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Create Flask app early so Gunicorn can import `app`
app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"
if load_dotenv:
    load_dotenv()  # Load variables from a .env file if present
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

def _is_postgres(url: str) -> bool:
    return url.startswith("postgres://") or url.startswith("postgresql://")

IS_POSTGRES = bool(DATABASE_URL and _is_postgres(DATABASE_URL))






def get_db():
    """Return a DB connection to Postgres if DATABASE_URL is set, otherwise SQLite."""
    if IS_POSTGRES:
        # Lazy import to avoid hard dependency when using SQLite
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    # Default to SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_cursor(conn):
    """Return a cursor that yields mapping rows for both engines."""
    if IS_POSTGRES:
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def init_db():
    conn = get_db()
    cur = get_cursor(conn)
    if IS_POSTGRES:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS movimientos (
                id SERIAL PRIMARY KEY,
                tipo VARCHAR(20) NOT NULL,
                concepto TEXT NOT NULL,
                monto NUMERIC(10,2) NOT NULL,
                fecha DATE NOT NULL
            )
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                concepto TEXT NOT NULL,
                monto REAL NOT NULL,
                fecha TEXT NOT NULL
            )
            """
        )
    conn.commit()
    cur.close()
    conn.close()


def _wait_for_postgres(retries: int = 8, delay: float = 2.0):
    """Try to connect to Postgres a few times before giving up.

    This helps when DB provisioning is slightly delayed in hosted environments.
    """
    if not IS_POSTGRES:
        return True

    try:
        import psycopg2
    except Exception:
        logger.exception("psycopg2 not available when waiting for Postgres")
        return False

    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.close()
            logger.info("Connected to Postgres on attempt %d", attempt)
            return True
        except Exception as e:
            logger.warning("Postgres not ready (attempt %d/%d): %s", attempt, retries, e)
            time.sleep(delay)
            delay = min(delay * 1.5, 10)

    logger.error("Could not connect to Postgres after %d attempts", retries)
    return False

# Ensure DB schema exists on startup; attempt to wait for Postgres if needed
try:
    if IS_POSTGRES:
        # Wait a bit for the remote Postgres service to be ready before creating the schema
        _wait_for_postgres()
    init_db()
except Exception:
    # Best-effort init; any DB errors will surface later but we avoid crashing the process
    logger.exception("init_db() failed at import time; continuing without blocking startup")

@app.route("/")
def index():
    try:
        conn = get_db()
        cur = get_cursor(conn)

        # Use a uniform alias and access by key
        cur.execute("SELECT COALESCE(SUM(monto), 0) AS total FROM movimientos WHERE tipo='ingreso'")
        ingresos_row = cur.fetchone()
        ingresos = (ingresos_row["total"] if isinstance(ingresos_row, dict) or hasattr(ingresos_row, 'keys') else ingresos_row[0]) or 0

        cur.execute("SELECT COALESCE(SUM(monto), 0) AS total FROM movimientos WHERE tipo='gasto'")
        gastos_row = cur.fetchone()
        gastos = (gastos_row["total"] if isinstance(gastos_row, dict) or hasattr(gastos_row, 'keys') else gastos_row[0]) or 0

        saldo = ingresos - gastos

        # Últimos 5 movimientos
        cur.execute("SELECT * FROM movimientos ORDER BY fecha DESC LIMIT 5")
        recientes = cur.fetchall()

        cur.close()
        conn.close()

        return render_template("index.html", ingresos=ingresos, gastos=gastos, saldo=saldo, recientes=recientes)
    except Exception:
        # Log full exception to stdout (captured by Render)
        tb = traceback.format_exc()
        logger.exception("Error while rendering index; DB may be unavailable")
        # If the environment requests debug output, expose the traceback on the error page
        show_debug = os.getenv("SHOW_DEBUG_ERRORS", "0").lower() in ("1", "true", "yes")
        return render_template(
            "error.html",
            message="No se pudo acceder a la base de datos. Revisa /health y los logs.",
            traceback=tb if show_debug else None,
        ), 500

def _build_filters(args):
    conditions = []
    params = []
    ph = "%s" if IS_POSTGRES else "?"

    tipo = args.get("tipo", "").strip()
    if tipo in ("ingreso", "gasto"):
        conditions.append(f"tipo = {ph}")
        params.append(tipo)

    desde = args.get("desde", "").strip()
    if desde:
        conditions.append(f"fecha >= {ph}")
        params.append(desde)

    hasta = args.get("hasta", "").strip()
    if hasta:
        conditions.append(f"fecha <= {ph}")
        params.append(hasta)

    concepto = args.get("concepto", "").strip()
    if concepto:
        # Case-insensitive match
        if IS_POSTGRES:
            conditions.append(f"LOWER(concepto) LIKE {ph}")
            params.append(f"%{concepto.lower()}%")
        else:
            conditions.append(f"LOWER(concepto) LIKE {ph}")
            params.append(f"%{concepto.lower()}%")

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


@app.route("/movimientos")
def movimientos():
    try:
        conn = get_db()
        cur = get_cursor(conn)

        where, params = _build_filters(request.args)
        sql = "SELECT * FROM movimientos" + where + " ORDER BY fecha DESC"
        cur.execute(sql, params)
        movs = cur.fetchall()

        cur.close()
        conn.close()

        return render_template("movimientos.html", movs=movs, filtros={
            'tipo': request.args.get('tipo', ''),
            'desde': request.args.get('desde', ''),
            'hasta': request.args.get('hasta', ''),
            'concepto': request.args.get('concepto', ''),
        })
    except Exception:
        tb = traceback.format_exc()
        logger.exception("Error while listing movimientos; DB may be unavailable")
        show_debug = os.getenv("SHOW_DEBUG_ERRORS", "0").lower() in ("1", "true", "yes")
        return render_template(
            "error.html",
            message="No se pudo acceder a la base de datos. Revisa /health y los logs.",
            traceback=tb if show_debug else None,
        ), 500

@app.post("/movimientos/<int:mov_id>/eliminar")
def eliminar_movimiento(mov_id: int):
    conn = get_db()
    cur = get_cursor(conn)
    if IS_POSTGRES:
        cur.execute("DELETE FROM movimientos WHERE id = %s", (mov_id,))
    else:
        cur.execute("DELETE FROM movimientos WHERE id = ?", (mov_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/movimientos")


@app.route("/movimientos/<int:mov_id>/editar", methods=["GET", "POST"])
def editar_movimiento(mov_id: int):
    conn = get_db()
    cur = get_cursor(conn)
    # Leer registro actual
    if IS_POSTGRES:
        cur.execute("SELECT * FROM movimientos WHERE id = %s", (mov_id,))
    else:
        cur.execute("SELECT * FROM movimientos WHERE id = ?", (mov_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return redirect("/movimientos")

    # Normalizar acceso tanto dict (PG) como tuple (SQLite)
    def get_val(r, key, idx):
        return r[key] if hasattr(r, 'keys') else r[idx]

    if request.method == "POST":
        tipo = request.form.get("tipo", get_val(row, 'tipo', 1))
        concepto = request.form.get("concepto", get_val(row, 'concepto', 2))
        monto = float(request.form.get("monto", get_val(row, 'monto', 3) or 0))
        fecha = request.form.get("fecha", get_val(row, 'fecha', 4))

        if IS_POSTGRES:
            cur.execute(
                "UPDATE movimientos SET tipo=%s, concepto=%s, monto=%s, fecha=%s WHERE id=%s",
                (tipo, concepto, monto, fecha, mov_id)
            )
        else:
            cur.execute(
                "UPDATE movimientos SET tipo=?, concepto=?, monto=?, fecha=? WHERE id=?",
                (tipo, concepto, monto, fecha, mov_id)
            )
        conn.commit()
        cur.close(); conn.close()
        return redirect("/movimientos")

    # GET: renderizar formulario con valores actuales
    movimiento = {
        'id': mov_id,
        'tipo': get_val(row, 'tipo', 1),
        'concepto': get_val(row, 'concepto', 2),
        'monto': float(get_val(row, 'monto', 3) or 0),
        'fecha': str(get_val(row, 'fecha', 4)),
    }
    cur.close(); conn.close()
    return render_template("editar_movimiento.html", mov=movimiento)

@app.route("/nuevo_ingreso", methods=["GET", "POST"])
def nuevo_ingreso():
    if request.method == "POST":
        concepto = request.form["concepto"]
        monto = float(request.form["monto"])
        fecha = request.form["fecha"]

        conn = get_db()
        cur = get_cursor(conn)
        if IS_POSTGRES:
            cur.execute(
                "INSERT INTO movimientos (tipo, concepto, monto, fecha) VALUES ('ingreso', %s, %s, %s)",
                (concepto, monto, fecha)
            )
        else:
            cur.execute(
                "INSERT INTO movimientos (tipo, concepto, monto, fecha) VALUES ('ingreso', ?, ?, ?)",
                (concepto, monto, fecha)
            )
        conn.commit()
        cur.close()
        conn.close()

        return redirect("/")

    return render_template("nuevo_ingreso.html")

@app.route("/nuevo_gasto", methods=["GET", "POST"])
def nuevo_gasto():
    if request.method == "POST":
        concepto = request.form["concepto"]
        monto = float(request.form["monto"])
        fecha = request.form["fecha"]

        conn = get_db()
        cur = get_cursor(conn)
        if IS_POSTGRES:
            cur.execute(
                "INSERT INTO movimientos (tipo, concepto, monto, fecha) VALUES ('gasto', %s, %s, %s)",
                (concepto, monto, fecha)
            )
        else:
            cur.execute(
                "INSERT INTO movimientos (tipo, concepto, monto, fecha) VALUES ('gasto', ?, ?, ?)",
                (concepto, monto, fecha)
            )
        conn.commit()
        cur.close()
        conn.close()

        return redirect("/")

    return render_template("nuevo_gasto.html")

@app.route("/health")
def health():
    try:
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute("SELECT 1")
        cur.fetchone()
        engine = "postgres" if IS_POSTGRES else "sqlite"
        info = {"status": "ok", "engine": engine}
        if IS_POSTGRES and DATABASE_URL:
            try:
                    parsed = urlparse(DATABASE_URL)
                    info.update({
                        "db_host": parsed.hostname,
                        "db_port": parsed.port,
                        "db_name": parsed.path.lstrip('/') if parsed.path else None
                    })
            except Exception:
                pass
        conn.close()
        return jsonify(info), 200
    except Exception as e:
        engine = "postgres" if IS_POSTGRES else "sqlite"
        return jsonify({"status": "error", "engine": engine, "detail": str(e)}), 500

if __name__ == "__main__":
    init_db()
    # Make host/port configurable to allow access from other devices
    host = os.getenv("HOST", "0.0.0.0")  # listen on all interfaces by default
    port = int(os.getenv("PORT", "5000"))
    debug_flag = os.getenv("FLASK_DEBUG", "1") in ("1", "true", "True")
    app.run(host=host, port=port, debug=debug_flag)
