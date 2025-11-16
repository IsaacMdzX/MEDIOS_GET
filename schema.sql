-- SQLite-compatible schema for local development
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    concepto TEXT NOT NULL,
    monto REAL NOT NULL,
    fecha TEXT NOT NULL
);
