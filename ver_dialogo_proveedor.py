"""Demo: ventanas para crear y para editar un proveedor.
Usa una base temporal: no toca tus datos reales."""
import tempfile
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DB_PATH = Path(_tmp.name) / "demo.db"

import customtkinter as ctk

from app.base_datos.esquema import crear_tablas
from app.interfaz import estilos as e
from app.interfaz.dialogo_proveedor import crear_proveedor_nuevo, editar_proveedor
from app.servicios import proveedores

crear_tablas()
existente = proveedores.crear_proveedor("Textiles Lima", "999111222",
                                        "Jr. Gamarra 123", "Ropa de mujer")
proveedores.crear_proveedor("Jeans Gamarra", "988777666", "", "Jeans")

e.aplicar_tema()
ventana = ctk.CTk()
ventana.geometry("900x600")
e.configurar_tabla()
ventana.update()

nuevo = crear_proveedor_nuevo(ventana)
print("NUEVO :", (nuevo.nombre, nuevo.telefono, nuevo.direccion or "—",
                  nuevo.vende or "—") if nuevo else "cancelado")

print("(ahora se abre «Editar proveedor» con Textiles Lima; "
      "prueba cambiarle datos o ponerle el teléfono de Jeans Gamarra)")
editado = editar_proveedor(ventana, existente)
print("EDITADO:", (editado.nombre, editado.telefono, editado.direccion or "—",
                   editado.vende or "—") if editado else "cancelado")
ventana.destroy()
_tmp.cleanup()