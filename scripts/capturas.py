"""Toma capturas de pantalla reales (navegador Edge sin interfaz) de las API en ejecución.

Requiere la simulación levantada con HABILITAR_DOCS=1 y datos cargados (scripts/demo_api.py).
Las capturas de la caída de un servicio se toman con el microservicio de productos realmente detenido.
"""
import pathlib
import shutil
import subprocess
import tempfile
import time

import httpx

from comun import EVIDENCIAS, URL, compose, llamar

EDGE = pathlib.Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
DESTINO = EVIDENCIAS / "capturas"


def capturar(nombre: str, url: str, alto: int, ancho: int = 1280) -> None:
    destino = DESTINO / f"{nombre}.png"
    destino.unlink(missing_ok=True)
    perfil = tempfile.mkdtemp(prefix="edge_cap_")
    try:
        proceso = subprocess.Popen(
            [str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={perfil}",
             f"--window-size={ancho},{alto}", "--virtual-time-budget=12000", f"--screenshot={destino}", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        fin = time.time() + 60
        while time.time() < fin and not (destino.exists() and destino.stat().st_size > 0):
            time.sleep(0.5)
        time.sleep(1)
        proceso.terminate()
    finally:
        shutil.rmtree(perfil, ignore_errors=True)
    print(f"{'OK ' if destino.exists() else 'FALLO'} {nombre}.png <- {url}")


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    capturar("01_swagger_productos", f"{URL['productos']}/docs", 900)
    capturar("02_swagger_clientes", f"{URL['clientes']}/docs", 800)
    capturar("03_swagger_pedidos", f"{URL['pedidos']}/docs", 850)
    capturar("04_respuesta_catalogo", f"{URL['productos']}/productos", 330)
    capturar("05_respuesta_clientes", f"{URL['clientes']}/clientes", 260)
    capturar("06_respuesta_pedido", f"{URL['pedidos']}/pedidos/1", 330)
    capturar("07_dependencias_normal", f"{URL['pedidos']}/health/dependencias", 200)

    print("Deteniendo el microservicio de productos para capturar la falla...")
    compose("stop", "productos")
    time.sleep(1)
    for _ in range(3):  # tres intentos fallidos abren el disyuntor
        llamar("pedidos", "POST", "/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 1}]})
    capturar("08_dependencias_productos_caido", f"{URL['pedidos']}/health/dependencias", 200)
    capturar("09_pedidos_siguen_funcionando", f"{URL['pedidos']}/pedidos/1", 330)
    capturar("10_clientes_siguen_funcionando", f"{URL['clientes']}/clientes/1", 200)
    capturar("11_productos_detenido", f"{URL['productos']}/productos", 420)
    compose("start", "productos")
    for _ in range(40):
        try:
            if httpx.get(f"{URL['productos']}/health", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(1)


if __name__ == "__main__":
    main()
