"""Pruebas de los tres microservicios: cada módulo se importa desde su propia carpeta."""
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
for servicio in ("productos", "clientes", "pedidos"):
    sys.path.insert(0, str(RAIZ / "servicios" / servicio))
os.environ["SERVICE_TOKEN"] = "token-solo-para-pruebas-automaticas"

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import api_clientes  # noqa: E402
import api_pedidos  # noqa: E402
import api_productos  # noqa: E402
from resiliencia import Disyuntor, ServicioRemoto  # noqa: E402

TOKEN = os.environ["SERVICE_TOKEN"]
H_SERVICIO = {"X-Servicio-Token": TOKEN}


def puente(app_destino, caido: dict | None = None) -> httpx.Client:
    """Cliente httpx cuyas solicitudes se atienden directamente con otra aplicación (sin red).

    `caido["activo"] = True` simula que el servicio dejó de responder (error de conexión).
    """
    destino = TestClient(app_destino)

    def manejar(request: httpx.Request) -> httpx.Response:
        if caido and caido.get("activo"):
            raise httpx.ConnectError("servicio detenido", request=request)
        r = destino.request(request.method, request.url.raw_path.decode(), content=request.content, headers=dict(request.headers))
        return httpx.Response(r.status_code, content=r.content, headers=r.headers)

    return httpx.Client(base_url="http://servicio", transport=httpx.MockTransport(manejar))


@pytest.fixture
def productos():
    return TestClient(api_productos.create_app())


@pytest.fixture
def clientes():
    return TestClient(api_clientes.create_app())


@pytest.fixture
def entorno():
    """Los tres servicios conectados entre sí, con interruptores para simular caídas."""
    app_prod, app_cli = api_productos.create_app(), api_clientes.create_app()
    caidos = {"productos": {"activo": False}, "clientes": {"activo": False}}
    dep = api_pedidos.Dependencias(
        productos=ServicioRemoto("productos", "", TOKEN, cliente=puente(app_prod, caidos["productos"]), disyuntor=Disyuntor(umbral=2, espera=60)),
        clientes=ServicioRemoto("clientes", "", TOKEN, cliente=puente(app_cli, caidos["clientes"]), disyuntor=Disyuntor(umbral=2, espera=60)),
    )
    return {"productos": TestClient(app_prod), "clientes": TestClient(app_cli), "pedidos": TestClient(api_pedidos.create_app(dep)),
            "caidos": caidos, "dep": dep}
