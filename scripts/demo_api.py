"""Recorrido de las tres API: registrar, consultar, comprar y provocar errores controlados."""
from comun import Registro, compacto, leer_token, llamar

reg = Registro()


def paso(titulo: str, servicio: str, metodo: str, ruta: str, esperado: int, **kw) -> dict:
    r, ms = llamar(servicio, metodo, ruta, **kw)
    marca = "OK   " if r.status_code == esperado else "FALLO"
    reg(f"[{marca}] {metodo:4s} {servicio}{ruta} -> {r.status_code} ({ms:.0f} ms) {titulo}")
    reg(f"        {compacto(r)}")
    if r.status_code != esperado:
        raise SystemExit("La demostración no coincide con lo esperado")
    return r.json()


def main() -> None:
    reg("== Demostración de las API de TecnoStore (microservicios en Docker) ==")
    for s in ("productos", "clientes", "pedidos"):
        paso(f"salud de {s}", s, "GET", "/health", 200)

    reg("\n-- Servicio de productos --")
    p1 = paso("registrar producto", "productos", "POST", "/productos", 201, json={"nombre": "Portátil Pro 14", "precio_cop": 3_200_000, "stock": 5})
    p2 = paso("registrar producto", "productos", "POST", "/productos", 201, json={"nombre": "Auriculares inalámbricos", "precio_cop": 249_900, "stock": 20})
    paso("consultar catálogo", "productos", "GET", "/productos", 200)
    paso("consultar un producto", "productos", "GET", f"/productos/{p1['id']}", 200)

    reg("\n-- Servicio de clientes --")
    c1 = paso("registrar cliente", "clientes", "POST", "/clientes", 201, json={"nombre": "Ana Pérez", "email": "ana.perez@example.com"})
    paso("registrar cliente", "clientes", "POST", "/clientes", 201, json={"nombre": "Luis Gómez", "email": "luis.gomez@example.com"})
    paso("consultar un cliente", "clientes", "GET", f"/clientes/{c1['id']}", 200)

    reg("\n-- Servicio de pedidos (consulta a clientes y productos por HTTP) --")
    pedido = paso("registrar pedido de 1 portátil y 2 auriculares", "pedidos", "POST", "/pedidos", 201,
                  json={"cliente_id": c1["id"], "items": [{"producto_id": p1["id"], "cantidad": 1}, {"producto_id": p2["id"], "cantidad": 2}]})
    paso("consultar el estado del pedido", "pedidos", "GET", f"/pedidos/{pedido['id']}", 200)
    reg(f"        total esperado: {3_200_000 + 2 * 249_900:,} COP | total recibido: {pedido['total_cop']:,} COP".replace(",", "."))
    paso("el stock del portátil bajó de 5 a 4", "productos", "GET", f"/productos/{p1['id']}", 200)

    reg("\n-- Errores controlados --")
    paso("cliente inexistente", "pedidos", "POST", "/pedidos", 404, json={"cliente_id": 99, "items": [{"producto_id": 1, "cantidad": 1}]})
    paso("existencias insuficientes", "pedidos", "POST", "/pedidos", 409, json={"cliente_id": c1["id"], "items": [{"producto_id": p1["id"], "cantidad": 50}]})
    paso("entrada inválida (cantidad 0)", "pedidos", "POST", "/pedidos", 422, json={"cliente_id": c1["id"], "items": [{"producto_id": 1, "cantidad": 0}]})
    paso("correo duplicado", "clientes", "POST", "/clientes", 409, json={"nombre": "Otra Ana", "email": "ANA.PEREZ@example.com"})
    paso("reservar stock sin token de servicio", "productos", "POST", f"/productos/{p1['id']}/reservar", 401, json={"cantidad": 1})
    paso("reservar stock con el token de servicio", "productos", "POST", f"/productos/{p2['id']}/reservar", 200, json={"cantidad": 1}, headers={"X-Servicio-Token": leer_token()})
    ruta = reg.guardar("demo_api.txt")
    print(f"\nEvidencia guardada en {ruta}")


if __name__ == "__main__":
    main()
