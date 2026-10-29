"""Diagrama de la arquitectura de microservicios de TecnoStore (figura del informe)."""
import pathlib
import sys

sys.path.insert(0, r"C:\Users\cuent\Documents\Universidad\Katherin\2026-02\Sistemas Transaccionales\herramientas_doc\build")
from dibujo import *  # noqa: E402,F403

SALIDA = pathlib.Path(__file__).parent / "arquitectura_microservicios.png"
W, H = 1300, 980
c = Lienzo(W, H)


def caja(x0, y0, x1, y1, titulo, sub="", relleno=CLARO, tam_t=22, tam_s=17, borde=AZUL):
    c.rect(x0, y0, x1, y1, relleno=relleno, borde=borde, grosor=2.5, radio=8)
    if sub:
        c.texto_caja(x0, y0 + 6, x1, y0 + (y1 - y0) * 0.42, titulo, "b", tam_t, NEGRO, margen=6)
        c.texto_caja(x0, y0 + (y1 - y0) * 0.40, x1, y1, sub, "n", tam_s, GRIS_O, interlinea=1.15, margen=8, valign="t")
    else:
        c.texto_caja(x0, y0, x1, y1, titulo, "b", tam_t, NEGRO)


def flecha(pts, doble=False, guiones=False):
    c.linea(pts, NEGRO, 3, guiones=guiones)
    c.punta_abierta(pts[-1], unitario(pts[-2], pts[-1]), NEGRO, 3, 20, 10)
    if doble:
        c.punta_abierta(pts[0], unitario(pts[1], pts[0]), NEGRO, 3, 20, 10)


def etiqueta(x, y, texto, ancho=None):
    ancho = ancho or c.medir(texto, "n", 16) + 16
    c.rect(x - ancho / 2, y - 14, x + ancho / 2, y + 14, relleno=BLANCO, borde=BLANCO, grosor=1)
    c.texto(x, y, texto, "n", 16, GRIS_O, "mm")


def numero(cx, cy, n):
    c.d.ellipse([(cx - 16) * ESCALA, (cy - 16) * ESCALA, (cx + 16) * ESCALA, (cy + 16) * ESCALA], fill=AZUL, outline=BLANCO, width=2 * ESCALA)
    c.texto(cx, cy, str(n), "b", 19, BLANCO, "mm")


# Usuario y aplicación cliente
caja(80, 30, 480, 120, "Usuario", "comprador o administrador de la tienda")
caja(820, 30, 1220, 120, "Aplicación cliente", "navegador, Swagger UI o curl")
flecha([(480, 75), (820, 75)], doble=True)

# Banda de servicios
c.rect(40, 215, 1260, 725, relleno=(250, 251, 253), borde=AZUL, grosor=3)
c.texto(1240, 703, "Red interna de Docker: un contenedor por microservicio", "bi", 17, AZUL, "ra")

caja(70, 310, 380, 470, "Servicio de clientes", "puerto 8002 (anfitrión)\nPOST /clientes\nGET /clientes y /clientes/{id}")
caja(495, 310, 805, 540, "Servicio de pedidos", "puerto 8003 (anfitrión)\nPOST /pedidos\nGET /pedidos y /pedidos/{id}\n\nDisyuntor + plazo de 2,5 s\npor cada servicio vecino", relleno=CLARO2)
caja(920, 310, 1230, 470, "Servicio de productos", "puerto 8001 (anfitrión)\nPOST y GET /productos\nPOST /reservar y /liberar\n(exigen token de servicio)")
caja(70, 580, 380, 660, "Lista en memoria", "clientes", relleno=GRIS)
caja(495, 580, 805, 660, "Lista en memoria", "pedidos", relleno=GRIS)
caja(920, 580, 1230, 660, "Lista en memoria", "catálogo y existencias", relleno=GRIS)
for x in (225, 650, 1075):
    c.linea([(x, 470 if x != 650 else 540), (x, 580)], NEGRO, 2.5)
    c.punta_abierta((x, 580), (0, 1), NEGRO, 2.5, 16, 8)

# Llamadas entre servicios
flecha([(495, 390), (380, 390)])
etiqueta(437, 360, "GET /clientes/{id}", 140)
flecha([(805, 390), (920, 390)])
etiqueta(862, 360, "reservar / liberar", 130)
numero(437, 420, 2)
numero(862, 420, 3)

# Cliente -> servicios (líneas desde la aplicación cliente hacia cada servicio)
c.linea([(1020, 120), (1020, 195)], NEGRO, 3)
c.linea([(1020, 195), (225, 195), (225, 310)], NEGRO, 3)
c.punta_abierta((225, 310), (0, 1), NEGRO, 3, 20, 10)
c.linea([(1020, 195), (650, 195), (650, 310)], NEGRO, 3)
c.punta_abierta((650, 310), (0, 1), NEGRO, 3, 20, 10)
c.linea([(1020, 195), (1075, 195), (1075, 310)], NEGRO, 3)
c.punta_abierta((1075, 310), (0, 1), NEGRO, 3, 20, 10)
numero(1020, 158, 1)

# Pie: independencia y resiliencia
caja(70, 765, 630, 945, "Independencia", "Cada servicio tiene su imagen, su puerto y su ciclo de vida: se detiene, actualiza o escala sin tocar a los demás.", relleno=BLANCO, tam_t=21, tam_s=17)
caja(670, 765, 1230, 945, "Tolerancia a fallos", "Si productos o clientes caen, pedidos responde 503 con un mensaje claro; consultar pedidos y usar el otro servicio sigue funcionando.", relleno=BLANCO, tam_t=21, tam_s=17)

c.guardar(str(SALIDA), dpi=200)
print("ok", SALIDA)
