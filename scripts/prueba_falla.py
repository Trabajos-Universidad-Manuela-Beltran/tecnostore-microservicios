"""Tolerancia a fallos: se detiene un microservicio y se comprueba qué sigue funcionando.

Escenario 1: se detiene productos. Escenario 2: se detiene clientes. Luego se recuperan.
"""
import time

import httpx

from comun import Registro, compose, llamar

reg = Registro()
PEDIDO = {"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 1}]}


def intento(titulo: str, servicio: str, metodo: str, ruta: str, **kw) -> int:
    r, ms = llamar(servicio, metodo, ruta, **kw)
    detalle = ""
    try:
        cuerpo = r.json()
        detalle = cuerpo.get("detalle", "") if isinstance(cuerpo, dict) else f"{len(cuerpo)} elemento(s)"
    except ValueError:
        pass
    reg(f"  {metodo:4s} {servicio}{ruta:16s} -> {r.status_code} en {ms:6.0f} ms  {titulo}" + (f" | {detalle}" if detalle else ""))
    return r.status_code


def esperar_servicio(servicio: str, segundos: int = 40) -> None:
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            if llamar(servicio, "GET", "/health")[0].status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise TimeoutError(servicio)


def preparar() -> None:
    llamar("clientes", "POST", "/clientes", json={"nombre": "Cliente Demo", "email": f"demo{int(time.time())}@example.com"})
    llamar("productos", "POST", "/productos", json={"nombre": "Producto Demo", "precio_cop": 100_000, "stock": 50})


def main() -> None:
    compose("up", "-d")
    for s in ("productos", "clientes", "pedidos"):
        esperar_servicio(s)
    preparar()
    reg("== Estado normal ==")
    intento("crear pedido", "pedidos", "POST", "/pedidos", json=PEDIDO)

    reg("\n== Escenario 1: se DETIENE el microservicio de productos (docker compose stop productos) ==")
    compose("stop", "productos")
    time.sleep(1)
    intento("consultar clientes", "clientes", "GET", "/clientes")
    intento("registrar un cliente", "clientes", "POST", "/clientes", json={"nombre": "Cliente Nuevo", "email": f"nuevo{int(time.time())}@example.com"})
    intento("consultar pedidos existentes", "pedidos", "GET", "/pedidos")
    intento("consultar un pedido", "pedidos", "GET", "/pedidos/1")
    reg("  -- se intenta crear pedidos mientras productos está caído (el disyuntor abre tras 3 fallos) --")
    for n in range(1, 6):
        intento(f"crear pedido, intento {n}", "pedidos", "POST", "/pedidos", json=PEDIDO)
    r, _ = llamar("pedidos", "GET", "/health/dependencias")
    reg(f"  estado de dependencias visto por pedidos: {r.json()}")

    reg("\n== Recuperación: se REINICIA productos (sus datos en memoria se pierden, se vuelve a cargar el catálogo) ==")
    compose("start", "productos")
    esperar_servicio("productos")
    llamar("productos", "POST", "/productos", json={"nombre": "Producto Demo", "precio_cop": 100_000, "stock": 50})
    reg("  esperando a que el disyuntor pase a semiabierto (10 s)...")
    time.sleep(11)
    intento("crear pedido tras la recuperación", "pedidos", "POST", "/pedidos", json=PEDIDO)

    reg("\n== Escenario 2: se DETIENE el microservicio de clientes (docker compose stop clientes) ==")
    compose("stop", "clientes")
    time.sleep(1)
    intento("consultar productos", "productos", "GET", "/productos")
    intento("registrar un producto", "productos", "POST", "/productos", json={"nombre": "Otro producto", "precio_cop": 50_000, "stock": 5})
    intento("consultar pedidos existentes", "pedidos", "GET", "/pedidos")
    intento("crear pedido (necesita validar al cliente)", "pedidos", "POST", "/pedidos", json=PEDIDO)
    compose("start", "clientes")
    esperar_servicio("clientes")
    reg("\n  clientes reiniciado; los tres servicios vuelven a responder a /health.")
    ruta = reg.guardar("prueba_falla.txt")
    print(f"\nEvidencia guardada en {ruta}")


if __name__ == "__main__":
    main()
