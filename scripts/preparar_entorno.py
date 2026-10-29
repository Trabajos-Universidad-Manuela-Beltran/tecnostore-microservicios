"""Crea .env con el token compartido entre servicios (aleatorio). El archivo está en .gitignore."""
import pathlib
import secrets
import sys

RUTA = pathlib.Path(__file__).resolve().parent.parent / ".env"
if RUTA.exists():
    sys.exit(".env ya existe; no se modifica.")
RUTA.write_text(f"SERVICE_TOKEN={secrets.token_urlsafe(32)}\n", encoding="utf-8")
print(f".env creado en {RUTA}")
