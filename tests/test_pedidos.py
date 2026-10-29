from resiliencia import Disyuntor

PEDIDO = {"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 1}]}


def preparar(e, stock=5):
    e["clientes"].post("/clientes", json={"nombre": "Ana", "email": "ana@example.com"})
    e["productos"].post("/productos", json={"nombre": "Portátil", "precio_cop": 2_000_000, "stock": stock})
    e["productos"].post("/productos", json={"nombre": "Ratón", "precio_cop": 50_000, "stock": 10})


def stock(e, producto_id):
    return e["productos"].get(f"/productos/{producto_id}").json()["stock"]


def test_pedido_exitoso_reserva_stock_y_calcula_total(entorno):
    preparar(entorno)
    r = entorno["pedidos"].post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 2}, {"producto_id": 2, "cantidad": 3}]})
    assert r.status_code == 201
    pedido = r.json()
    assert pedido["estado"] == "confirmado" and pedido["total_cop"] == 2 * 2_000_000 + 3 * 50_000
    assert stock(entorno, 1) == 3 and stock(entorno, 2) == 7
    assert entorno["pedidos"].get(f"/pedidos/{pedido['id']}").json()["estado"] == "confirmado"
    assert len(entorno["pedidos"].get("/pedidos?cliente_id=1").json()) == 1


def test_items_repetidos_se_agrupan(entorno):
    preparar(entorno)
    r = entorno["pedidos"].post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 2, "cantidad": 1}, {"producto_id": 2, "cantidad": 2}]})
    assert r.status_code == 201 and r.json()["items"][0]["cantidad"] == 3 and stock(entorno, 2) == 7


def test_cliente_o_producto_inexistente(entorno):
    preparar(entorno)
    assert entorno["pedidos"].post("/pedidos", json={"cliente_id": 9, "items": [{"producto_id": 1, "cantidad": 1}]}).status_code == 404
    assert entorno["pedidos"].post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 9, "cantidad": 1}]}).status_code == 404


def test_stock_insuficiente_libera_las_reservas_previas(entorno):
    preparar(entorno, stock=1)
    r = entorno["pedidos"].post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 2, "cantidad": 4}, {"producto_id": 1, "cantidad": 2}]})
    assert r.status_code == 409
    assert stock(entorno, 2) == 10 and stock(entorno, 1) == 1  # la reserva del producto 2 se compensó
    assert entorno["pedidos"].get("/pedidos").json() == []


def test_validacion_de_entradas(entorno):
    p = entorno["pedidos"]
    assert p.post("/pedidos", json={"cliente_id": 1, "items": []}).status_code == 422
    assert p.post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 0}]}).status_code == 422
    assert p.post("/pedidos", json={"cliente_id": 0, "items": [{"producto_id": 1, "cantidad": 1}]}).status_code == 422
    assert p.get("/pedidos/77").status_code == 404


def test_si_productos_cae_los_pedidos_se_rechazan_pero_el_resto_sigue(entorno):
    preparar(entorno)
    entorno["caidos"]["productos"]["activo"] = True
    r = entorno["pedidos"].post("/pedidos", json=PEDIDO)
    assert r.status_code == 503 and "productos" in r.json()["detalle"] and r.headers["retry-after"] == "10"
    assert entorno["pedidos"].get("/pedidos").status_code == 200  # consultar pedidos sigue funcionando
    assert entorno["clientes"].post("/clientes", json={"nombre": "Luis", "email": "luis@example.com"}).status_code == 201
    assert [d["responde"] for d in entorno["pedidos"].get("/health/dependencias").json()] == ["sí", "no"]


def test_si_clientes_cae_no_se_puede_crear_pedido(entorno):
    preparar(entorno)
    entorno["caidos"]["clientes"]["activo"] = True
    r = entorno["pedidos"].post("/pedidos", json=PEDIDO)
    assert r.status_code == 503 and "clientes" in r.json()["detalle"] and stock(entorno, 1) == 5


def test_disyuntor_abre_falla_rapido_y_se_recupera(entorno):
    preparar(entorno)
    entorno["caidos"]["productos"]["activo"] = True
    for _ in range(2):
        assert entorno["pedidos"].post("/pedidos", json=PEDIDO).status_code == 503
    assert entorno["dep"].productos.disyuntor.estado == "abierto"
    entorno["caidos"]["productos"]["activo"] = False  # el servicio vuelve, pero el disyuntor aún está abierto
    assert entorno["pedidos"].post("/pedidos", json=PEDIDO).status_code == 503
    entorno["dep"].productos.disyuntor.espera = 0  # termina la espera: pasa a semiabierto y deja una llamada de prueba
    assert entorno["pedidos"].post("/pedidos", json=PEDIDO).status_code == 201
    assert entorno["dep"].productos.disyuntor.estado == "cerrado"


def test_disyuntor_con_reloj_simulado():
    t = [0.0]
    d = Disyuntor(umbral=2, espera=10, reloj=lambda: t[0])
    d.fallo()
    assert d.estado == "cerrado"
    d.fallo()
    assert d.estado == "abierto" and not d.permitir()
    t[0] = 10
    assert d.estado == "semiabierto" and d.permitir()
    d.fallo()
    assert d.estado == "abierto"  # la llamada de prueba falló: se vuelve a abrir
    t[0] = 25
    d.exito()
    assert d.estado == "cerrado"
