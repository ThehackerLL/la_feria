"""Demo: pantalla Caja y reportes (sección «Caja del día»).
Usa una base temporal: no toca tus datos reales.
Empieza con la caja de hoy SIN abrir y la de ayer SIN cerrar, y ya hay ventas
de hoy. Prueba: abrir caja, cerrar el día de ayer, vender (con el botón de abajo)
y cerrar la caja de hoy."""
import tempfile
from datetime import date, timedelta
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DB_PATH = Path(_tmp.name) / "demo.db"

import customtkinter as ctk

from app.base_datos.conexion import transaccion
from app.base_datos.esquema import crear_tablas
from app.interfaz import estilos as e
from app.interfaz.pantallas.caja import PantallaCaja
from app.servicios import caja, clientes, compras, creditos, inventario, ventas

crear_tablas()
polo = inventario.crear_producto("Polo", "Ropa", costo=10, precio_unidad=25, precio_mayor=18, stock=500)
jean = inventario.crear_producto("Jean", "Ropa", costo=40, precio_unidad=90, precio_mayor=70, stock=500)
ana = clientes.crear_cliente("Ana Pérez", "999888777")


def vender(prod, cant, pagos, **kw):
    return ventas.registrar_venta(
        [{"producto_id": prod.id, "cantidad": cant, "tipo": "unidad", "precio": prod.precio_unidad}],
        pagos, **kw)["venta_id"]


ayer = date.today() - timedelta(days=1)
caja.abrir_dia(50, hoy=ayer)
v = vender(jean, 2, [{"forma_pago": "Efectivo", "monto": 30}], cliente_id=ana.id,
           credito={"cuotas": 2, "dias": 15})
with transaccion() as con:
    con.execute("UPDATE ventas SET fecha=? || ' 10:00:00' WHERE id=?", (ayer.isoformat(), v))
    con.execute("UPDATE venta_pagos SET fecha=? || ' 10:00:00' WHERE venta_id=?", (ayer.isoformat(), v))

vender(polo, 4, [{"forma_pago": "Efectivo", "monto": 100}])
vender(polo, 2, [{"forma_pago": "Yape/Plin", "monto": 30}, {"forma_pago": "Efectivo", "monto": 20}])
vender(jean, 1, [{"forma_pago": "Tarjeta", "monto": 90}])
w = vender(jean, 1, [{"forma_pago": "Transferencia", "monto": 30}], cliente_id=ana.id,
           credito={"cuotas": 2, "dias": 10})
creditos.registrar_pago_cuota(creditos.detalle_credito(v)["cuotas"][0]["id"], 40, "Efectivo")
compras.registrar_compra([dict(codigo="", nombre="Gorra", categoria="Ropa", cantidad=10, costo=5,
                               precio_unidad=10, precio_mayor=8)],
                         pagos=[{"forma_pago": "Efectivo", "monto": 50}])

e.aplicar_tema()
ventana = ctk.CTk()
ventana.title("Demo: Caja y reportes")
ventana.geometry("1240x700")
ventana.minsize(1280, 680)
ventana.configure(fg_color=e.COLOR_FONDO)
e.configurar_tabla()
pantalla = PantallaCaja(ventana)
pantalla.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)


def vender_ahora():
    vender(polo, 1, [{"forma_pago": "Efectivo", "monto": 25}])
    pantalla.refrescar()


ctk.CTkButton(ventana, text="(demo) Vender un polo en efectivo", command=vender_ahora
              ).pack(pady=(0, 8))
ventana.mainloop()
_tmp.cleanup()