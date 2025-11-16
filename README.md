# MEDIOS GET

App Flask para gestionar ingresos y gastos con soporte para SQLite/Postgres y despliegue simple.

## Ejecutar localmente

```bash
# (opcional) activar tu venv
# pip install -r requirements.txt
"./.venv/bin/python" app.py
# Abre http://127.0.0.1:5000 (o http://TU_IP_LOCAL:5000 en tu red)
```

## Obtener URL pública temporal (túnel)

```bash
chmod +x scripts/run_public.sh
./scripts/run_public.sh
```
- Si tienes `cloudflared`, verás una URL pública HTTPS.
- Si no, el script intenta usar `ngrok` si está instalado.

## Desplegar en Render (URL pública permanente)

Opción 1: Botón de despliegue (sustituye TU_REPO_URL por la URL HTTPS de tu repo)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=TU_REPO_URL)

Opción 2: Blueprint
- Render detectará `render.yaml` y creará un servicio web + BD Postgres.
- Variables de entorno:
  - `DATABASE_URL` (Render la inyecta desde la BD creada).
  - `FLASK_DEBUG=0`.

## Variables de entorno

Copia `.env.example` a `.env` y ajusta:
- `DATABASE_URL` para usar Postgres.
- `HOST`, `PORT`, `FLASK_DEBUG` (opcional).

## Salud de la app

- `GET /health` devuelve estado y motor de base de datos.

## Notas

- En local, si no defines `DATABASE_URL`, se usa SQLite (`data.db`).
- En producción, define `DATABASE_URL` a tu Postgres.

## Docker (cualquier nube o VPS)

Construir y ejecutar en el puerto 8000:

```bash
docker build -t medios-get .
docker run -p 8000:8000 -e FLASK_DEBUG=0 medios-get
```

Con docker-compose (usa tu `DATABASE_URL` si aplica):

```bash
docker compose up --build
```

Luego abre http://localhost:8000 (o mapea a 80/443 detrás de Nginx en un VPS).
