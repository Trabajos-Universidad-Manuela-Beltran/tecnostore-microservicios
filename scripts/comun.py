"""Utilidades de los scripts de demostración (se ejecutan solo contra la simulación local)."""
import json
import pathlib
import subprocess
import time

import httpx

RAIZ = pathlib.Path(__file__).resolve().parent.parent
EVIDENCIAS = RAIZ / "evidencias"
URL = {"productos": "http://127.0.0.1:8001", "clientes": "http://127.0.0.1:8002", "pedidos": "http://127.0.0.1:8003"}


def leer_token() -> str:
    for linea in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
        if linea.startswith("SERVICE_TOKEN="):
            return linea.split("=", 1)[1].strip()
    raise RuntimeError("Falta SERVICE_TOKEN en .env")


class Registro:
    """Imprime y acumula las líneas de evidencia."""

    def __init__(self) -> None:
        self.lineas: list[str] = []

    def __call__(self, texto: str = "") -> None:
        print(texto)
        self.lineas.append(texto)

    def guardar(self, nombre: str) -> pathlib.Path:
        EVIDENCIAS.mkdir(exist_ok=True)
        ruta = EVIDENCIAS / nombre
        ruta.write_text("\n".join(self.lineas) + "\n", encoding="utf-8")
        return ruta


def llamar(servicio: str, metodo: str, ruta: str, esperado: int | None = None, **kw) -> tuple[httpx.Response, float]:
    """Hace la solicitud y devuelve (respuesta, milisegundos)."""
    t0 = time.perf_counter()
    r = httpx.request(metodo, URL[servicio] + ruta, timeout=10, **kw)
    ms = (time.perf_counter() - t0) * 1000
    if esperado is not None and r.status_code != esperado:
        raise AssertionError(f"{metodo} {ruta}: se esperaba {esperado} y llegó {r.status_code}: {r.text[:200]}")
    return r, ms


def compacto(r: httpx.Response, limite: int = 150) -> str:
    texto = json.dumps(r.json(), ensure_ascii=False, separators=(",", ":"))
    return texto if len(texto) <= limite else texto[:limite] + "…"


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=RAIZ, check=True, capture_output=True)
