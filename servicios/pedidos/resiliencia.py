"""Comunicación entre servicios con tiempo límite, reintentos de conexión y disyuntor (circuit breaker)."""
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as PlazoVencido

import httpx


# Hilos auxiliares para imponer un plazo máximo a cada llamada: la resolución DNS de un servicio detenido puede
# tardar varios segundos y no la cubre el tiempo límite de conexión de httpx.
_EJECUTOR = ThreadPoolExecutor(max_workers=16, thread_name_prefix="remoto")


class ServicioNoDisponible(Exception):
    """El servicio remoto no responde o su disyuntor está abierto."""

    def __init__(self, servicio: str) -> None:
        super().__init__(servicio)
        self.servicio = servicio


class Disyuntor:
    """Tras `umbral` fallos seguidos se abre y rechaza llamadas durante `espera` segundos (falla rápido).

    Pasado ese tiempo queda semiabierto: deja pasar una llamada de prueba; si funciona, se cierra.
    """

    def __init__(self, umbral: int = 3, espera: float = 10.0, reloj: Callable[[], float] = time.monotonic) -> None:
        self.umbral, self.espera, self._reloj = umbral, espera, reloj
        self._fallos = 0
        self._abierto_desde: float | None = None

    @property
    def estado(self) -> str:
        if self._abierto_desde is None:
            return "cerrado"
        return "semiabierto" if self._reloj() - self._abierto_desde >= self.espera else "abierto"

    def permitir(self) -> bool:
        return self.estado != "abierto"

    def exito(self) -> None:
        self._fallos, self._abierto_desde = 0, None

    def fallo(self) -> None:
        self._fallos += 1
        if self._fallos >= self.umbral or self._abierto_desde is not None:
            self._abierto_desde = self._reloj()


class ServicioRemoto:
    """Cliente HTTP de un microservicio vecino."""

    def __init__(self, nombre: str, url_base: str, token: str | None = None, timeout: float = 2.0, disyuntor: Disyuntor | None = None,
                 cliente: httpx.Client | None = None, plazo: float = 2.5) -> None:
        self.nombre, self.plazo = nombre, plazo
        self.disyuntor = disyuntor or Disyuntor()
        self._http = cliente or httpx.Client(base_url=url_base, timeout=timeout, transport=httpx.HTTPTransport(retries=1))
        self._cabeceras = {"X-Servicio-Token": token} if token else {}

    def solicitar(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        """Devuelve la respuesta (incluidos los 4xx, que son errores del negocio); lanza ServicioNoDisponible ante fallas."""
        if not self.disyuntor.permitir():
            raise ServicioNoDisponible(self.nombre)
        try:
            r = _EJECUTOR.submit(self._http.request, metodo, ruta, headers=self._cabeceras, **kw).result(timeout=self.plazo)
        except (httpx.HTTPError, PlazoVencido):
            self.disyuntor.fallo()
            raise ServicioNoDisponible(self.nombre) from None
        if r.status_code >= 500:
            self.disyuntor.fallo()
            raise ServicioNoDisponible(self.nombre)
        self.disyuntor.exito()
        return r

    def estado(self) -> dict[str, str]:
        """Estado para el monitoreo; no altera el disyuntor."""
        try:
            ok = self._http.get("/health", timeout=1.0).status_code == 200
        except httpx.HTTPError:
            ok = False
        return {"servicio": self.nombre, "responde": "sí" if ok else "no", "disyuntor": self.disyuntor.estado}
