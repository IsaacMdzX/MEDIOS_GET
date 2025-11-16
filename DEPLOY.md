# Desplegar la app para verla desde cualquier lugar

Este proyecto ya está listo para ejecutarse en la nube usando Gunicorn (+ Flask) sin cambios de código.

## 1) Opción rápida: túnel temporal (sin abrir puertos)

- Cloudflare Tunnel (recomendado):
  1. Instala `cloudflared`.
  2. Ejecuta: `cloudflared tunnel --url http://localhost:5000`
  3. Te dará una URL pública (https) para compartir.

- Ngrok:
  1. Instala `ngrok` y autentica tu cuenta.
  2. Ejecuta: `ngrok http 5000`
  3. Usa la URL pública que te muestra.

## 2) Opción estable: Render (gratis)

1. Sube este repo a GitHub.
2. Crea un servicio Web en https://render.com (New + Web Service).
3. Configura:
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --workers 2 --threads 2 --bind 0.0.0.0:$PORT`
4. Variables de entorno:
   - `DATABASE_URL`: cadena de conexión a tu Postgres (Render también ofrece Postgres administrado).
   - Opcional: `FLASK_DEBUG=0`.
5. Render expondrá una URL pública (https) permanente.

## 3) Opción estable: Railway

1. Importa el repo en https://railway.app
2. Añade plugin de Postgres y copia su `DATABASE_URL`.
3. Variables de entorno:
   - `DATABASE_URL=<la de Railway>`
4. Start Command:
   - Usa el `Procfile` incluido (`web: gunicorn app:app --bind 0.0.0.0:$PORT`).

## 4) Fly.io / Docker (opcional)

- Crea una imagen (si deseas contenedor):
  - Dockerfile sencillo (no incluido por simplicidad), luego `fly launch`.

## Notas

- `app.py` ya escucha en `0.0.0.0` (configurable por env `HOST`/`PORT`).
- Requisitos: `gunicorn` agregado en `requirements.txt`.
- Base de datos: si no defines `DATABASE_URL`, la app usa `SQLite` local; en la nube, define `DATABASE_URL` de Postgres.
- Salud: `/health` devuelve estado y motor de BD.
