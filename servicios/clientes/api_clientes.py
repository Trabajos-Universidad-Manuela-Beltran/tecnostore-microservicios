"""Microservicio de clientes: registra y consulta clientes (lista en memoria, simplificación del taller)."""
import os
import threading
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, StringConstraints

Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

# La documentación interactiva se activa solo para la demostración (HABILITAR_DOCS=1); por defecto está desactivada.
_DOCS = "/docs" if os.environ.get("HABILITAR_DOCS") == "1" else None
_OPENAPI = "/openapi.json" if _DOCS else None


class ClienteIn(BaseModel):
    nombre: Nombre
    email: EmailStr


class ClienteOut(BaseModel):
    id: int
    nombre: str
    email: EmailStr


class Registro:
    def __init__(self) -> None:
        self._clientes: dict[int, dict] = {}
        self._siguiente = 1
        self._candado = threading.Lock()

    def crear(self, entrada: ClienteIn) -> dict | None:
        """Devuelve None si el correo ya está registrado."""
        correo = entrada.email.lower()
        with self._candado:
            if any(c["email"] == correo for c in self._clientes.values()):
                return None
            cliente = {"id": self._siguiente, "nombre": entrada.nombre, "email": correo}
            self._clientes[cliente["id"]] = cliente
            self._siguiente += 1
            return dict(cliente)

    def listar(self, desde: int, limite: int) -> list[dict]:
        with self._candado:
            return [dict(c) for c in list(self._clientes.values())[desde:desde + limite]]

    def obtener(self, cliente_id: int) -> dict | None:
        with self._candado:
            c = self._clientes.get(cliente_id)
            return dict(c) if c else None


def create_app(registro: Registro | None = None) -> FastAPI:
    datos = registro or Registro()
    app = FastAPI(title="Microservicio de clientes", docs_url=_DOCS, redoc_url=None, openapi_url=_OPENAPI)

    @app.exception_handler(Exception)
    async def error_generico(request: Request, exc: Exception):
        return JSONResponse({"detalle": "Error interno del servidor"}, status_code=500)

    @app.get("/health")
    def salud() -> dict[str, str]:
        return {"servicio": "clientes", "estado": "ok"}

    @app.get("/clientes", response_model=list[ClienteOut])
    def listar(desde: int = Query(default=0, ge=0), limite: int = Query(default=50, ge=1, le=100)):
        return datos.listar(desde, limite)

    @app.get("/clientes/{cliente_id}", response_model=ClienteOut)
    def obtener(cliente_id: int):
        cliente = datos.obtener(cliente_id)
        if cliente is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")
        return cliente

    @app.post("/clientes", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
    def registrar(entrada: ClienteIn):
        cliente = datos.crear(entrada)
        if cliente is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "El correo ya está registrado")
        return cliente

    return app


app = create_app()
