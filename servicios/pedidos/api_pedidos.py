"""Microservicio de pedidos: registra pedidos y consulta su estado.

Depende de los servicios de clientes (verifica que el cliente exista) y de productos (reserva existencias).
Si una reserva falla, libera las ya hechas (compensación) para no dejar el inventario inconsistente.
"""
import os
import threading
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from resiliencia import ServicioNoDisponible, ServicioRemoto

# La documentación interactiva se activa solo para la demostración (HABILITAR_DOCS=1); por defecto está desactivada.
_DOCS = "/docs" if os.environ.get("HABILITAR_DOCS") == "1" else None
_OPENAPI = "/openapi.json" if _DOCS else None


class ItemIn(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=100)


class PedidoIn(BaseModel):
    cliente_id: int = Field(gt=0)
    items: list[ItemIn] = Field(min_length=1, max_length=20)


class ItemOut(BaseModel):
    producto_id: int
    nombre: str
    cantidad: int
    precio_unitario_cop: int


class PedidoOut(BaseModel):
    id: int
    cliente_id: int
    estado: str
    total_cop: int
    creado: datetime
    items: list[ItemOut]


class Dependencias:
    """Agrupa los clientes de los servicios vecinos (se reemplazan por dobles en las pruebas)."""

    def __init__(self, productos: ServicioRemoto, clientes: ServicioRemoto) -> None:
        self.productos, self.clientes = productos, clientes


def dependencias_desde_entorno() -> Dependencias:
    token = os.environ.get("SERVICE_TOKEN", "")
    return Dependencias(
        productos=ServicioRemoto("productos", os.environ.get("PRODUCTOS_URL", "http://productos:8000"), token),
        clientes=ServicioRemoto("clientes", os.environ.get("CLIENTES_URL", "http://clientes:8000"), token),
    )


def _reservar(dep: Dependencias, items: dict[int, int]) -> list[dict]:
    """Reserva cada producto; ante cualquier falla libera lo reservado y propaga el error."""
    hechos: list[tuple[int, int]] = []
    lineas: list[dict] = []
    try:
        for producto_id, cantidad in items.items():
            r = dep.productos.solicitar("POST", f"/productos/{producto_id}/reservar", json={"cantidad": cantidad})
            if r.status_code == 404:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"El producto {producto_id} no existe")
            if r.status_code == 409:
                raise HTTPException(status.HTTP_409_CONFLICT, f"Existencias insuficientes del producto {producto_id}")
            if r.status_code != 200:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Respuesta inesperada del servicio de productos")
            p = r.json()
            hechos.append((producto_id, cantidad))
            lineas.append({"producto_id": producto_id, "nombre": p["nombre"], "cantidad": cantidad, "precio_unitario_cop": p["precio_cop"]})
    except (HTTPException, ServicioNoDisponible):
        for producto_id, cantidad in hechos:
            try:
                dep.productos.solicitar("POST", f"/productos/{producto_id}/liberar", json={"cantidad": cantidad})
            except ServicioNoDisponible:
                pass  # si productos cayó, sus reservas parciales quedan para conciliación manual
        raise
    return lineas


def create_app(dependencias: Dependencias | None = None) -> FastAPI:
    dep = dependencias or dependencias_desde_entorno()
    pedidos: dict[int, dict] = {}
    estado = {"siguiente": 1}
    candado = threading.Lock()
    app = FastAPI(title="Microservicio de pedidos", docs_url=_DOCS, redoc_url=None, openapi_url=_OPENAPI)

    @app.exception_handler(ServicioNoDisponible)
    async def sin_servicio(request: Request, exc: ServicioNoDisponible):
        return JSONResponse({"detalle": f"El servicio de {exc.servicio} no está disponible; intente de nuevo en unos segundos"},
                            status_code=503, headers={"Retry-After": "10"})

    @app.exception_handler(Exception)
    async def error_generico(request: Request, exc: Exception):
        return JSONResponse({"detalle": "Error interno del servidor"}, status_code=500)

    @app.get("/health")
    def salud() -> dict[str, str]:
        return {"servicio": "pedidos", "estado": "ok"}

    @app.get("/health/dependencias")
    def salud_dependencias() -> list[dict[str, str]]:
        return [dep.clientes.estado(), dep.productos.estado()]

    @app.post("/pedidos", response_model=PedidoOut, status_code=status.HTTP_201_CREATED)
    def registrar(entrada: PedidoIn):
        r = dep.clientes.solicitar("GET", f"/clientes/{entrada.cliente_id}")
        if r.status_code == 404:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El cliente no existe")
        # Se agrupan los ítems repetidos y se reserva en orden de id para tener un comportamiento predecible.
        agrupados: dict[int, int] = {}
        for item in entrada.items:
            agrupados[item.producto_id] = agrupados.get(item.producto_id, 0) + item.cantidad
        lineas = _reservar(dep, dict(sorted(agrupados.items())))
        with candado:
            pedido = {
                "id": estado["siguiente"], "cliente_id": entrada.cliente_id, "estado": "confirmado",
                "total_cop": sum(x["cantidad"] * x["precio_unitario_cop"] for x in lineas),
                "creado": datetime.now(timezone.utc), "items": lineas,
            }
            pedidos[pedido["id"]] = pedido
            estado["siguiente"] += 1
        return pedido

    @app.get("/pedidos", response_model=list[PedidoOut])
    def listar(cliente_id: int | None = Query(default=None, gt=0), limite: int = Query(default=50, ge=1, le=100)):
        with candado:
            filas = [p for p in pedidos.values() if cliente_id is None or p["cliente_id"] == cliente_id]
        return filas[-limite:]

    @app.get("/pedidos/{pedido_id}", response_model=PedidoOut)
    def consultar(pedido_id: int):
        with candado:
            pedido = pedidos.get(pedido_id)
        if pedido is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
        return pedido

    return app

