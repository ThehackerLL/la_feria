"""Demo: la franja de 4 indicadores del día (la que irá arriba de Ventas).
Usa una base temporal con ventas de hoy y la caja SIN abrir: pulsa «Abrir caja»
en la tarjeta Efectivo y prueba «Mostrar» en Ganancia."""
import tempfile
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DB_PATH = Path(_tmp.name) / "demo.db"

import customtkinter as ctk

from app.base_datos.esquema import crear_tablas
from app.interfaz import estilos as e
from app.interfaz.indicadores_dia import FranjaIndicadores
from app.servicios import inventario, ventas

crear_tablas()
polo = inventario.crear_producto("Polo", "Ropa", costo=10, precio_unidad=25, precio_mayor=18, stock=500)
jean = inventario.crear_producto("Jean", "Ropa", costo=40, precio_unidad=90, precio_mayor=70, stock=500)
for prod, cant, forma in [(polo, 4, "Efectivo"), (jean, 1, "Yape/Plin"), (polo, 2, "Tarjeta")]:
    ventas.registrar_venta(
        [{"producto_id": prod.id, "cantidad": cant, "tipo": "unidad", "precio": prod.precio_unidad}],
        [{"forma_pago": forma, "monto": cant * prod.precio_unidad}])

e.aplicar_tema()
ventana = ctk.CTk()
ventana.title("Demo: indicadores del día")
ventana.geometry("1240x300")
ventana.minsize(1000, 200)
ventana.configure(fg_color=e.COLOR_FONDO)
e.configurar_tabla()
FranjaIndicadores(ventana).pack(fill="x", padx=e.MARGEN, pady=e.MARGEN)
ventana.mainloop()
_tmp.cleanup()