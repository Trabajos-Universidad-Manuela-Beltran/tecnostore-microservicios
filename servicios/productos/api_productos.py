"""Microservicio de productos: administra el catálogo y las existencias.

Los datos viven en una lista en memoria (simplificación pedida por el taller). En un sistema real el servicio
tendría su propia base de datos.
"""
import hmac
import os
import threading
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints

Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

# La documentación interactiva se activa solo para la demostración (HABILITAR_DOCS=1); por defecto está desactivada.
_DOCS = "/docs" if os.environ.get("HABILITAR_DOCS") == "1" else None
_OPENAPI = "/openapi.json" if _DOCS else None


class ProductoIn(BaseModel):
    nombre: Nombre
    precio_cop: int = Field(gt=0, le=100_000_000)
    stock: int = Field(default=0, ge=0, le=1_000_000)


class ProductoOut(BaseModel):
    id: int
    nombre: str
    precio_cop: int
    stock: int


class CantidadIn(BaseModel):
    cantidad: int = Field(gt=0, le=100)


class Almacen:
    """Catálogo en memoria con un candado: las reservas de stock deben ser atómicas."""

    def __init__(self) -> None:
        self._productos: dict[int, dict] = {}
        self._siguiente = 1
        self._candado = threading.Lock()

    def crear(self, datos: ProductoIn) -> dict:
        with self._candado:
            producto = {"id": self._siguiente, **datos.model_dump()}
            self._productos[producto["id"]] = producto
            self._siguiente += 1
            return dict(producto)

    def listar(self, desde: int, limite: int) -> list[dict]:
        with self._candado:
            return [dict(p) for p in list(self._productos.values())[desde:desde + limite]]

    def obtener(self, producto_id: int) -> dict | None:
        with self._candado:
            p = self._productos.get(producto_id)
            return dict(p) if p else None

    def ajustar_stock(self, producto_id: int, delta: int) -> dict | None:
        """Suma `delta` al stock; devuelve None si no existe y lanza ValueError si quedaría negativo."""
        with self._candado:
            p = self._productos.get(producto_id)
            if p is None:
                return None
            if p["stock"] + delta < 0:
                raise ValueError("stock insuficiente")
            p["stock"] += delta
            return dict(p)


def token_de_servicio(x_servicio_token: str | None = Header(default=None)) -> None:
    """Las operaciones internas (reservar y liberar) exigen el token compartido entre servicios."""
    esperado = os.environ.get("SERVICE_TOKEN", "")
    if not esperado or x_servicio_token is None or not hmac.compare_digest(x_servicio_token, esperado):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de servicio inválido")


def create_app(almacen: Almacen | None = None) -> FastAPI:
    datos = almacen or Almacen()
    app = FastAPI(title="Microservicio de productos", docs_url=_DOCS, redoc_url=None, openapi_url=_OPENAPI)

    @app.exception_handler(Exception)
    async def error_generico(request: Request, exc: Exception):
        return JSONResponse({"detalle": "Error interno del servidor"}, status_code=500)

    @app.get("/health")
    def salud() -> dict[str, str]:
        return {"servicio": "productos", "estado": "ok"}

    @app.get("/productos", response_model=list[ProductoOut])
    def listar(desde: int = Query(default=0, ge=0), limite: int = Query(default=50, ge=1, le=100)):
        return datos.listar(desde, limite)

    @app.get("/productos/{producto_id}", response_model=ProductoOut)
    def obtener(producto_id: int):
        producto = datos.obtener(producto_id)
        if producto is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
        return producto

    @app.post("/productos", response_model=ProductoOut, status_code=status.HTTP_201_CREATED)
    def registrar(entrada: ProductoIn):
        return datos.crear(entrada)

    @app.post("/productos/{producto_id}/reservar", response_model=ProductoOut, dependencies=[Depends(token_de_servicio)])
    def reservar(producto_id: int, entrada: CantidadIn):
        try:
            producto = datos.ajustar_stock(producto_id, -entrada.cantidad)
        except ValueError:
            raise HTTPException(status.HTTP_409_CONFLICT, "Existencias insuficientes") from None
        if producto is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
        return producto

    @app.post("/productos/{producto_id}/liberar", response_model=ProductoOut, dependencies=[Depends(token_de_servicio)])
    def liberar(producto_id: int, entrada: CantidadIn):
        producto = datos.ajustar_stock(producto_id, entrada.cantidad)
        if producto is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
        return producto

    return app


app = create_app()
