"""Demo: sección Productos (más vendidos y productos parados).
Usa una base temporal: no toca tus datos reales."""
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
from app.interfaz.pantallas.movimiento import PantallaMovimiento
from app.servicios import inventario, ventas

crear_tablas()
hoy = date.today()
nombres = [("Polo básico", 10, 25, 300), ("Jean clásico", 40, 90, 80), ("Short deportivo", 4, 10, 200),
           ("Chaleco de lana", 20, 50, 40), ("Medias x3", 3, 6, 120), ("Casaca", 60, 140, 25),
           ("Gorra", 5, 12, 60), ("Cinturón", 8, 20, 35), ("Bufanda", 7, 18, 50),
           ("Blusa", 15, 35, 90), ("Falda", 18, 45, 45), ("Pantalón de vestir", 35, 80, 30),
           ("Camisa", 20, 50, 70), ("Polera", 25, 60, 20)]
prod = {}
for n, costo, precio, stock in nombres:
    prod[n] = inventario.crear_producto(n, "Ropa", costo=costo, precio_unidad=precio,
                                        precio_mayor=precio * 0.8, stock=stock * 3)
with transaccion() as con:     # los productos ya existían desde hace meses
    con.execute("UPDATE productos SET creado = ?", ((hoy - timedelta(days=300)).isoformat() + " 08:00:00",))

ventas_demo = [("Polo básico", 30, 3), ("Polo básico", 25, 12), ("Jean clásico", 12, 2), ("Jean clásico", 6, 20),
               ("Short deportivo", 3, 1), ("Medias x3", 9, 4), ("Blusa", 14, 1), ("Camisa", 10, 6),
               ("Gorra", 5, 8), ("Falda", 2, 20), ("Pantalón de vestir", 1, 40), ("Polera", 1, 100),
               ("Polo básico", 20, 0), ("Blusa", 8, 0), ("Camisa", 7, 1), ("Cinturón", 4, 2)]
for nombre, cant, dias_atras in ventas_demo:
    p = prod[nombre]
    r = ventas.registrar_venta([{"producto_id": p.id, "cantidad": cant, "tipo": "unidad",
                                 "precio": p.precio_unidad}],
                               [{"forma_pago": "Efectivo", "monto": cant * p.precio_unidad}])
    f = (hoy - timedelta(days=dias_atras)).isoformat() + " 11:00:00"
    with transaccion() as con:
        con.execute("UPDATE ventas SET fecha=? WHERE id=?", (f, r["venta_id"]))
        con.execute("UPDATE venta_pagos SET fecha=? WHERE venta_id=?", (f, r["venta_id"]))

e.aplicar_tema()
ventana = ctk.CTk()
ventana.title("Demo: Productos")
ventana.geometry("1240x700")
ventana.minsize(1280, 680)
ventana.configure(fg_color=e.COLOR_FONDO)
e.configurar_tabla()
PantallaMovimiento(ventana).pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
ventana.mainloop()
_tmp.cleanup()