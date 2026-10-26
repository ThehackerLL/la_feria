"""Demo: sección Reportes (hoy, semana, mes, año).
Usa una base temporal con ventas de varios días: no toca tus datos reales."""
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
from app.interfaz.pantallas.reportes import PantallaReportes
from app.servicios import clientes, compras, creditos, inventario, ventas

crear_tablas()
polo = inventario.crear_producto("Polo", "Ropa", costo=10, precio_unidad=25, precio_mayor=18, stock=900)
jean = inventario.crear_producto("Jean", "Ropa", costo=40, precio_unidad=90, precio_mayor=70, stock=900)
ana = clientes.crear_cliente("Ana Pérez", "999888777")
hoy = date.today()


def vender(dias_atras, prod, cant, forma, **kw):
    pagos = kw.pop("pagos", [{"forma_pago": forma, "monto": cant * prod.precio_unidad}])
    r = ventas.registrar_venta(
        [{"producto_id": prod.id, "cantidad": cant, "tipo": "unidad", "precio": prod.precio_unidad}],
        pagos, **kw)
    f = (hoy - timedelta(days=dias_atras)).isoformat() + " 11:00:00"
    with transaccion() as con:
        con.execute("UPDATE ventas SET fecha=? WHERE id=?", (f, r["venta_id"]))
        con.execute("UPDATE venta_pagos SET fecha=? WHERE venta_id=?", (f, r["venta_id"]))
    return r["venta_id"]


for dias, prod, cant, forma in [(0, polo, 4, "Efectivo"), (0, jean, 1, "Yape/Plin"),
                                (2, polo, 2, "Tarjeta"), (3, jean, 1, "Efectivo"),
                                (9, polo, 3, "Efectivo"), (10, jean, 2, "Transferencia"),
                                (35, polo, 5, "Efectivo"), (40, jean, 1, "Efectivo"),
                                (80, polo, 6, "Yape/Plin"), (200, jean, 2, "Efectivo"),
                                (400, jean, 3, "Efectivo")]:
    vender(dias, prod, cant, forma)
j = vender(20, jean, 1, None, cliente_id=ana.id, credito={"cuotas": 2, "dias": 10},
           pagos=[{"forma_pago": "Efectivo", "monto": 30}])
creditos.registrar_pago_cuota(creditos.detalle_credito(j)["cuotas"][0]["id"], 30, "Efectivo")
compras.registrar_compra([dict(codigo="", nombre="Gorra", categoria="Ropa", cantidad=10, costo=5,
                               precio_unidad=10, precio_mayor=8)],
                         pagos=[{"forma_pago": "Efectivo", "monto": 50}])

e.aplicar_tema()
ventana = ctk.CTk()
ventana.title("Demo: Reportes")
ventana.geometry("1240x700")
ventana.minsize(1280, 680)
ventana.configure(fg_color=e.COLOR_FONDO)
e.configurar_tabla()
PantallaReportes(ventana).pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
ventana.mainloop()
_tmp.cleanup()