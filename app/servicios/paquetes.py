"""Cuántas unidades trae el paquete de cada producto.

Se anota una vez en Compras («paquete de medias = 4 unidades») y el programa
lo recuerda para proponerlo otra vez, también en Ventas. Las docenas siempre
son 12 y no se guardan. Usa su propia tabla (se crea sola), sin tocar la de
productos.
"""
from app.servicios.inventario import _usar

_TABLA = """
CREATE TABLE IF NOT EXISTS producto_paquete (
    producto_id INTEGER PRIMARY KEY REFERENCES productos(id),
    unidades    INTEGER NOT NULL CHECK (unidades >= 1)
)
"""


def obtener(producto_id, con=None):
    """Unidades por paquete guardadas para el producto, o None si no hay."""
    with _usar(con) as c:
        c.execute(_TABLA)
        fila = c.execute("SELECT unidades FROM producto_paquete "
                         "WHERE producto_id = ?", (producto_id,)).fetchone()
    return int(fila["unidades"]) if fila else None


def guardar(producto_id, unidades, con=None):
    """Guarda (o cambia) las unidades por paquete del producto."""
    unidades = int(unidades)
    if unidades < 1:
        raise ValueError("Unidades por paquete: debe ser al menos 1.")
    with _usar(con) as c:
        c.execute(_TABLA)
        c.execute("INSERT INTO producto_paquete (producto_id, unidades) "
                  "VALUES (?, ?) ON CONFLICT(producto_id) "
                  "DO UPDATE SET unidades = excluded.unidades",
                  (producto_id, unidades))


def guardar_si_falta(producto_id, unidades, con=None):
    """Guarda solo si el producto todavía no tenía paquete anotado."""
    if obtener(producto_id, con) is None:
        guardar(producto_id, unidades, con)