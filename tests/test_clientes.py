def test_registrar_y_consultar(clientes):
    r = clientes.post("/clientes", json={"nombre": "Ana Pérez", "email": "Ana@Example.com"})
    assert r.status_code == 201 and r.json()["email"] == "ana@example.com"
    assert clientes.get("/clientes/1").json()["nombre"] == "Ana Pérez"
    assert len(clientes.get("/clientes").json()) == 1


def test_correo_duplicado_y_validaciones(clientes):
    datos = {"nombre": "Ana", "email": "ana@example.com"}
    assert clientes.post("/clientes", json=datos).status_code == 201
    assert clientes.post("/clientes", json={**datos, "email": "ANA@example.com"}).status_code == 409
    assert clientes.post("/clientes", json={"nombre": "x", "email": "no-es-correo"}).status_code == 422
    assert clientes.post("/clientes", json={"nombre": "", "email": "b@example.com"}).status_code == 422


def test_cliente_inexistente(clientes):
    assert clientes.get("/clientes/9").status_code == 404
    assert clientes.get("/health").json()["servicio"] == "clientes"
