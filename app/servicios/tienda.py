"""Datos de la tienda: el nombre que se ve en la barra, el título de la ventana,
el ingreso y los Excel.

Se guarda en la base de datos (no en el programa): quien compra el programa
pone su nombre la primera vez y puede cambiarlo en Configuración.
Si todavía no hay nombre guardado se usa `config.NOMBRE_TIENDA` («LA FERIA»),
que es lo que pasa con una base creada antes de existir este dato.

La tabla se crea sola (CREATE TABLE IF NOT EXISTS).
"""
from app import config
from app.servicios.inventario import _usar

MAX_NOMBRE = 40

_TABLA = """
CREATE TABLE IF NOT EXISTS tienda_ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
)
"""


def _preparar(con):
    con.execute(_TABLA)
    return con


def validar_nombre(nombre):
    """Devuelve el nombre limpio (sin espacios de más) o falla con ValueError."""
    limpio = " ".join(str(nombre or "").split())
    if not limpio:
        raise ValueError("Escribe el nombre de la tienda.")
    if len(limpio) > MAX_NOMBRE:
        raise ValueError(f"El nombre de la tienda es muy largo "
                         f"(máximo {MAX_NOMBRE} letras).")
    return limpio


def hay_nombre(con=None):
    """True si ya se guardó un nombre de tienda."""
    with _usar(con) as c:
        _preparar(c)
        return c.execute("SELECT 1 FROM tienda_ajustes WHERE clave = 'nombre'"
                         ).fetchone() is not None


def nombre(con=None):
    """El nombre de la tienda (o «LA FERIA» si nunca se guardó uno)."""
    with _usar(con) as c:
        _preparar(c)
        fila = c.execute("SELECT valor FROM tienda_ajustes WHERE clave = 'nombre'"
                         ).fetchone()
        return fila["valor"] if fila else config.NOMBRE_TIENDA


def guardar_nombre(nuevo, con=None):
    """Guarda el nombre de la tienda y lo devuelve ya limpio."""
    limpio = validar_nombre(nuevo)
    with _usar(con) as c:
        _preparar(c)
        c.execute("INSERT INTO tienda_ajustes (clave, valor) VALUES ('nombre', ?) "
                  "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                  (limpio,))
    return limpio