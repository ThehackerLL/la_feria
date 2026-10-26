"""Demo: pantalla Compras con proveedor, forma de pago y compra a crédito.
Usa una base temporal (con 2 proveedores y 1 producto de ejemplo): no toca
tus datos reales. Al cerrar la ventana imprime las compras, pagos y cuotas."""
import tempfile
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DB_PATH = Path(_tmp.name) / "demo.db"

import customtkinter as ctk

from app.base_datos.conexion import conectar
from app.base_datos.esquema import crear_tablas
from app.interfaz import estilos as e
from app.interfaz.pantallas.compras import PantallaCompras
from app.servicios import inventario, proveedores

crear_tablas()
proveedores.crear_proveedor("Textiles Lima", "999111222", vende="Ropa de mujer")
proveedores.crear_proveedor("Jeans Gamarra", "988777666", "Jr. Gamarra 123",
                            "Jeans y pantalones")
inventario.crear_producto("Camisa polo", "Camisas", 18, 30, 25, 10)

e.aplicar_tema()
ventana = ctk.CTk()
ventana.title("Demo - Compras")
ventana.geometry("1280x760")
ventana.minsize(1280, 680)      # igual que el programa real
e.configurar_tabla()
pantalla = PantallaCompras(ventana)
pantalla.pack(fill="both", expand=True, padx=16, pady=12)
pantalla.refrescar()
ventana.mainloop()

con = conectar()
print("COMPRAS:")
for f in con.execute("SELECT id, proveedor, total FROM compras"):
    print("  ", tuple(f))
print("PAGOS:")
for f in con.execute("SELECT compra_id, forma_pago, monto FROM compra_pagos"):
    print("  ", tuple(f))
print("CUOTAS:")
for f in con.execute("SELECT compra_id, numero, vence, monto FROM compra_cuotas"):
    print("  ", tuple(f))
con.close()
_tmp.cleanup()