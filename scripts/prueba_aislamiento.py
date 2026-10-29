"""Aislamiento de carga: una avalancha de consultas de productos (temporada de descuentos) no debe frenar a clientes."""
import statistics
import threading
import time

import httpx

from comun import URL, Registro

reg = Registro()
HILOS, SEGUNDOS = 24, 8


def medir(servicio: str, ruta: str, n: int) -> list[float]:
    tiempos = []
    with httpx.Client(timeout=10) as c:
        for _ in range(n):
            t0 = time.perf_counter()
            c.get(URL[servicio] + ruta)
            tiempos.append((time.perf_counter() - t0) * 1000)
            time.sleep(0.05)
    return tiempos


def resumen(nombre: str, t: list[float]) -> str:
    t = sorted(t)
    return f"{nombre:46s} mediana {statistics.median(t):6.1f} ms | p95 {t[int(0.95 * (len(t) - 1))]:6.1f} ms | n={len(t)}"


def main() -> None:
    with httpx.Client(timeout=10) as c:
        for i in range(30):
            c.post(URL["productos"] + "/productos", json={"nombre": f"Producto {i}", "precio_cop": 10_000 + i, "stock": 10})
    reg("== Aislamiento: avalancha de consultas al catálogo mientras se consulta a clientes ==")
    antes = medir("clientes", "/clientes", 40)
    reg(resumen("clientes SIN carga sobre productos", antes))

    fin = threading.Event()
    atendidas = [0]
    tiempos_prod: list[float] = []
    candado = threading.Lock()

    def avalancha() -> None:
        with httpx.Client(timeout=15) as c:
            while not fin.is_set():
                t0 = time.perf_counter()
                c.get(URL["productos"] + "/productos?limite=50")
                with candado:
                    atendidas[0] += 1
                    tiempos_prod.append((time.perf_counter() - t0) * 1000)

    hilos = [threading.Thread(target=avalancha) for _ in range(HILOS)]
    [h.start() for h in hilos]
    time.sleep(1.5)
    inicio = time.perf_counter()
    durante = medir("clientes", "/clientes", 60)
    transcurrido = time.perf_counter() - inicio
    fin.set()
    [h.join() for h in hilos]
    reg(resumen(f"clientes CON {HILOS} conexiones saturando productos", durante))
    reg(resumen("productos bajo la avalancha", tiempos_prod))
    reg(f"productos atendió {atendidas[0]} consultas durante la prueba ({atendidas[0] / (transcurrido + 1.5):.0f} por segundo aprox.)")
    ruta = reg.guardar("prueba_aislamiento.txt")
    print(f"\nEvidencia guardada en {ruta}")


if __name__ == "__main__":
    main()
