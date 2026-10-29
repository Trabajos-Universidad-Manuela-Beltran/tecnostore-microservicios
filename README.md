# TecnoStore: tienda virtual con microservicios

Taller 6 de Sistemas Distribuidos (Universidad Manuela Beltrán). Tres microservicios independientes en FastAPI, cada uno en
su contenedor Docker y comunicados por HTTP (API REST):

| Servicio | Puerto | Responsabilidad |
| --- | --- | --- |
| productos | 8001 | Catálogo y existencias (reservar y liberar stock con token de servicio) |
| clientes | 8002 | Registro y consulta de clientes |
| pedidos | 8003 | Registro de pedidos y consulta de su estado; llama a clientes y productos |

Los datos viven en listas en memoria (simplificación del taller): se pierden al reiniciar un servicio.
El servicio de pedidos usa plazo máximo por llamada y disyuntor, de modo que si productos o clientes se detienen, el resto
sigue funcionando (solo falla el registro de pedidos, con un 503 claro).

## Ejecución

```bash
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe scripts/preparar_entorno.py      # crea .env con el token entre servicios (no se sube a git)
docker compose up -d --build                              # HABILITAR_DOCS=1 activa /docs (Swagger) en cada servicio
```

## Pruebas

| Qué | Comando |
| --- | --- |
| 18 pruebas automáticas (cobertura 95 %) | `.venv/Scripts/python.exe -m pytest --cov=servicios` |
| Recorrido de las API | `.venv/Scripts/python.exe scripts/demo_api.py` |
| Caída de un servicio (detiene y reinicia contenedores) | `.venv/Scripts/python.exe scripts/prueba_falla.py` |
| Avalancha sobre productos y efecto en clientes | `.venv/Scripts/python.exe scripts/prueba_aislamiento.py` |
| Capturas de pantalla (Edge) | `.venv/Scripts/python.exe scripts/capturas.py` |

Las salidas reales están en `evidencias/` y las capturas en `evidencias/capturas/`. Los scripts se ejecutan solo contra esta
simulación local.

## Limitaciones
Sin base de datos, sin autenticación de usuarios finales, sin API gateway ni TLS entre servicios y sin pago. Ver el informe.
