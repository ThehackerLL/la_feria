"""Lógica de clientes (para ventas, crédito y envíos).

Una venta sin cliente es "Público general": se guarda con cliente_id = NULL,
no hace falta crear un cliente para eso.
"""
import re

from app.modelos.cliente import Cliente
# Se reutilizan las ayudas de inventario (comparar sin tildes y abrir conexión).
from app.servicios.inventario import _usar, normalizar

PUBLICO_GENERAL = "Público general"
COLUMNAS = "id, nombre, telefono, activo, creado, dni, direccion"


def _a_cliente(fila):
    return Cliente(**dict(fila)) if fila else None


def _limpiar_telefono(telefono):
    """'+51 999-111-222' -> '+51999111222'. Vacío es válido."""
    texto = re.sub(r"[\s\-().]", "", str(telefono or ""))
    if texto == "":
        return ""
    if not re.fullmatch(r"\+?\d{6,15}", texto):
        raise ValueError("Teléfono: usa solo números (de 6 a 15 dígitos), "
                         "por ejemplo 999111222.")
    return texto


def _limpiar_dni(dni):
    """'12 345 678' -> '12345678'. Vacío es válido (es opcional)."""
    texto = re.sub(r"[\s\-.]", "", str(dni or ""))
    if texto and not re.fullmatch(r"\d{8}", texto):
        raise ValueError("DNI: debe tener 8 números (o déjalo vacío).")
    return texto


def _validar(nombre, telefono, dni="", direccion=""):
    nombre = " ".join(str(nombre or "").split())
    if not nombre:
        raise ValueError("Escribe el nombre del cliente.")
    if normalizar(nombre) == normalizar(PUBLICO_GENERAL):
        raise ValueError("«Público general» ya existe: se usa cuando la venta "
                         "no tiene cliente.")
    return (nombre, _limpiar_telefono(telefono), _limpiar_dni(dni),
            " ".join(str(direccion or "").split()))


def _repetido(con, nombre, telefono, excepto_id=None):
    """Mismo nombre Y mismo teléfono = mismo cliente (hay que evitar duplicarlo).
    Dos personas con el mismo nombre pero distinto teléfono sí se permiten."""
    clave = normalizar(nombre)
    for fila in con.execute(
            f"SELECT {COLUMNAS} FROM clientes WHERE activo = 1"):
        if (normalizar(fila["nombre"]) == clave
                and fila["telefono"] == telefono and fila["id"] != excepto_id):
            return _a_cliente(fila)
    return None


# ------------------------------------------------------------------ consultas
def obtener_cliente(cliente_id, con=None):
    with _usar(con) as c:
        return _a_cliente(c.execute(
            f"SELECT {COLUMNAS} FROM clientes WHERE id = ?",
            (cliente_id,)).fetchone())


def buscar_clientes(texto="", limite=None, con=None):
    """Clientes activos. Cada palabra escrita debe estar en el nombre o en el
    teléfono, DNI o dirección (en cualquier orden, sin importar tildes ni
    mayúsculas)."""
    palabras = normalizar(texto).split()
    with _usar(con) as c:
        filas = c.execute(f"SELECT {COLUMNAS} FROM clientes WHERE activo = 1 "
                          "ORDER BY nombre COLLATE NOCASE, id").fetchall()
    resultado = []
    for fila in filas:
        cliente = _a_cliente(fila)
        campos = normalizar(f"{cliente.nombre} {cliente.telefono} "
                           f"{cliente.dni} {cliente.direccion}")
        if all(p in campos for p in palabras):
            resultado.append(cliente)
            if limite and len(resultado) >= limite:
                break
    return resultado


# ------------------------------------------------------------------ escritura
def crear_cliente(nombre, telefono="", dni="", direccion="", con=None):
    nombre, telefono, dni, direccion = _validar(nombre, telefono, dni, direccion)
    with _usar(con) as c:
        existente = _repetido(c, nombre, telefono)
        if existente:
            raise ValueError(f"Ya existe el cliente «{existente.nombre}»"
                             + (f" con el teléfono {telefono}." if telefono
                                else " (sin teléfono). Si es otra persona, "
                                     "agrega su teléfono."))
        cur = c.execute("INSERT INTO clientes (nombre, telefono, dni, direccion) "
                        "VALUES (?, ?, ?, ?)", (nombre, telefono, dni, direccion))
        return obtener_cliente(cur.lastrowid, con=c)


def actualizar_cliente(cliente_id, nombre, telefono="", dni="", direccion=""):
    nombre, telefono, dni, direccion = _validar(nombre, telefono, dni, direccion)
    with _usar(None) as c:
        if obtener_cliente(cliente_id, con=c) is None:
            raise ValueError("El cliente ya no existe.")
        if _repetido(c, nombre, telefono, excepto_id=cliente_id):
            raise ValueError("Ya existe otro cliente con ese nombre y teléfono.")
        c.execute("UPDATE clientes SET nombre = ?, telefono = ?, dni = ?, "
                  "direccion = ? WHERE id = ?",
                  (nombre, telefono, dni, direccion, cliente_id))
        return obtener_cliente(cliente_id, con=c)


def desactivar_cliente(cliente_id):
    """Lo oculta de las búsquedas; sus ventas anteriores se conservan."""
    with _usar(None) as c:
        c.execute("UPDATE clientes SET activo = 0 WHERE id = ?", (cliente_id,))