"""Prueba rápida de clientes con una base temporal. Se puede borrar."""
import tempfile
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DATOS_DIR = Path(_tmp.name)
config.DB_PATH = Path(_tmp.name) / "prueba.db"

from app.base_datos.esquema import crear_tablas
from app.servicios import clientes

crear_tablas()


def intentar(texto, funcion, *args):
    try:
        print(texto, "->", funcion(*args))
    except ValueError as error:
        print(texto, "-> AVISO:", error)


intentar("Crear Juan", clientes.crear_cliente, "  juan   pérez ", "+51 999-111-222")
intentar("Otro Juan, otro teléfono", clientes.crear_cliente, "Juan Pérez", "988777666")
intentar("Juan repetido", clientes.crear_cliente, "JUAN PEREZ", "+51999111222")
intentar("Teléfono con letras", clientes.crear_cliente, "Ana", "abc123")
intentar("Sin nombre", clientes.crear_cliente, "  ", "999111222")
print("Buscar 'perez':", [(c.nombre, c.telefono) for c in clientes.buscar_clientes("perez")])
print("Buscar '9887':", [c.nombre for c in clientes.buscar_clientes("9887")])

_tmp.cleanup()   # esta línea debe quedar SIEMPRE al final