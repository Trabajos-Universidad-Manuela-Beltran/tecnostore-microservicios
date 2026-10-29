from conftest import H_SERVICIO


def nuevo(c, nombre="Portátil", precio=2_500_000, stock=5):
    r = c.post("/productos", json={"nombre": nombre, "precio_cop": precio, "stock": stock})
    assert r.status_code == 201
    return r.json()


def test_registrar_y_consultar(productos):
    p = nuevo(productos)
    assert p["id"] == 1 and p["stock"] == 5
    assert productos.get(f"/productos/{p['id']}").json()["nombre"] == "Portátil"
    assert [x["id"] for x in productos.get("/productos").json()] == [1]


def test_producto_inexistente(productos):
    assert productos.get("/productos/99").status_code == 404


def test_validacion_de_entradas(productos):
    assert productos.post("/productos", json={"nombre": " ", "precio_cop": 100}).status_code == 422
    assert productos.post("/productos", json={"nombre": "x", "precio_cop": 0}).status_code == 422
    assert productos.post("/productos", json={"nombre": "x", "precio_cop": 100, "stock": -1}).status_code == 422
    assert productos.get("/productos?limite=1000").status_code == 422
    assert productos.get("/productos/abc").status_code == 422


def test_operaciones_internas_exigen_token(productos):
    p = nuevo(productos)
    ruta = f"/productos/{p['id']}/reservar"
    assert productos.post(ruta, json={"cantidad": 1}).status_code == 401
    assert productos.post(ruta, json={"cantidad": 1}, headers={"X-Servicio-Token": "otro"}).status_code == 401
    assert productos.post(ruta, json={"cantidad": 1}, headers=H_SERVICIO).status_code == 200


def test_reservar_y_liberar_stock(productos):
    p = nuevo(productos, stock=3)
    assert productos.post(f"/productos/{p['id']}/reservar", json={"cantidad": 2}, headers=H_SERVICIO).json()["stock"] == 1
    assert productos.post(f"/productos/{p['id']}/reservar", json={"cantidad": 2}, headers=H_SERVICIO).status_code == 409
    assert productos.post(f"/productos/{p['id']}/liberar", json={"cantidad": 2}, headers=H_SERVICIO).json()["stock"] == 3
    assert productos.post("/productos/99/reservar", json={"cantidad": 1}, headers=H_SERVICIO).status_code == 404
    assert productos.post("/productos/99/liberar", json={"cantidad": 1}, headers=H_SERVICIO).status_code == 404


def test_documentacion_interactiva_desactivada(productos):
    assert productos.get("/docs").status_code == 404
    assert productos.get("/health").json()["estado"] == "ok"
