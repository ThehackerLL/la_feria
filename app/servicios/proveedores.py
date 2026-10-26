"""Lógica de proveedores (a quién le compramos y cuánto le debemos).

Un proveedor se guarda con nombre Y teléfono. La dirección y lo que nos
vende son opcionales.
"""
import re

from app.modelos.proveedor import Proveedor
# Se reutilizan las ayudas de inventario (comparar sin tildes y abrir conexión).
from app.servicios.inventario import _usar, normalizar

COLUMNAS = "id, nombre, telefono, direccion, vende, activo, creado"
_MARGEN = 0.005      # para no equivocarse por céntimos al comparar


def _a_proveedor(fila):
    return Proveedor(**dict(fila)) if fila else None


def _limpiar_telefono(telefono):
    """'+51 999-111-222' -> '+51999111222'. Es obligatorio."""
    texto = re.sub(r"[\s\-().]", "", str(telefono or ""))
    if texto == "":
        raise ValueError("Escribe el teléfono del proveedor.")
    if not re.fullmatch(r"\+?\d{6,15}", texto):
        raise ValueError("Teléfono: usa solo números (de 6 a 15 dígitos), "
                         "por ejemplo 999111222.")
    return texto


def _validar(nombre, telefono, direccion, vende):
    nombre = " ".join(str(nombre or "").split())
    if not nombre:
        raise ValueError("Escribe el nombre del proveedor.")
    return (nombre, _limpiar_telefono(telefono),
            " ".join(str(direccion or "").split()),
            " ".join(str(vende or "").split()))


def _repetido(con, nombre, telefono, excepto_id=None):
    """Mismo nombre Y mismo teléfono = mismo proveedor (hay que evitar
    duplicarlo)."""
    clave = normalizar(nombre)
    for fila in con.execute(
            f"SELECT {COLUMNAS} FROM proveedores WHERE activo = 1"):
        if (normalizar(fila["nombre"]) == clave
                and fila["telefono"] == telefono and fila["id"] != excepto_id):
            return _a_proveedor(fila)
    return None


# ------------------------------------------------------------------ consultas
def obtener_proveedor(proveedor_id, con=None):
    with _usar(con) as c:
        return _a_proveedor(c.execute(
            f"SELECT {COLUMNAS} FROM proveedores WHERE id = ?",
            (proveedor_id,)).fetchone())


def buscar_proveedores(texto="", limite=None, con=None):
    """Proveedores activos. Cada palabra escrita debe estar en el nombre, el
    teléfono o lo que vende (en cualquier orden, sin importar tildes)."""
    palabras = normalizar(texto).split()
    with _usar(con) as c:
        filas = c.execute(f"SELECT {COLUMNAS} FROM proveedores WHERE activo = 1 "
                          "ORDER BY nombre COLLATE NOCASE, id").fetchall()
    resultado = []
    for fila in filas:
        p = _a_proveedor(fila)
        campos = normalizar(f"{p.nombre} {p.telefono} {p.vende}")
        if all(palabra in campos for palabra in palabras):
            resultado.append(p)
            if limite and len(resultado) >= limite:
                break
    return resultado


def deuda_proveedor(proveedor_id, con=None):
    """Lo que todavía se le debe a este proveedor (suma de sus cuotas)."""
    with _usar(con) as c:
        fila = c.execute(
            "SELECT COALESCE(SUM(q.monto - q.pagado), 0) AS debe "
            "FROM compra_cuotas q JOIN compras co ON co.id = q.compra_id "
            "WHERE co.proveedor_id = ?", (proveedor_id,)).fetchone()
    debe = round(fila["debe"], 2)
    return debe if debe > _MARGEN else 0.0


def resumen_proveedores(texto="", con=None):
    """Para la lista de la pantalla: cada proveedor con su última compra y
    cuánto se le debe.

    Devuelve [{"id", "nombre", "telefono", "direccion", "vende", "ultima",
    "debe"}]. `ultima` es la fecha de la última compra (None si nunca se le
    compró). Van ordenados por nombre, igual que la búsqueda.
    """
    encontrados = buscar_proveedores(texto, con=con)
    with _usar(con) as c:
        ultimas = {f["proveedor_id"]: f["ultima"] for f in c.execute(
            "SELECT proveedor_id, MAX(fecha) AS ultima FROM compras "
            "WHERE proveedor_id IS NOT NULL GROUP BY proveedor_id")}
        deudas = {f["proveedor_id"]: f["debe"] for f in c.execute(
            "SELECT co.proveedor_id, SUM(q.monto - q.pagado) AS debe "
            "FROM compra_cuotas q JOIN compras co ON co.id = q.compra_id "
            "WHERE co.proveedor_id IS NOT NULL GROUP BY co.proveedor_id")}
    resultado = []
    for p in encontrados:
        debe = round(deudas.get(p.id, 0) or 0, 2)
        resultado.append({
            "id": p.id, "nombre": p.nombre, "telefono": p.telefono,
            "direccion": p.direccion, "vende": p.vende,
            "ultima": ultimas.get(p.id), "debe": debe if debe > _MARGEN else 0.0})
    return resultado


# ------------------------------------------------------------------ escritura
def crear_proveedor(nombre, telefono, direccion="", vende="", con=None):
    nombre, telefono, direccion, vende = _validar(nombre, telefono, direccion,
                                                  vende)
    with _usar(con) as c:
        existente = _repetido(c, nombre, telefono)
        if existente:
            raise ValueError(f"Ya existe el proveedor «{existente.nombre}» "
                             f"con el teléfono {telefono}.")
        cur = c.execute(
            "INSERT INTO proveedores (nombre, telefono, direccion, vende) "
            "VALUES (?, ?, ?, ?)", (nombre, telefono, direccion, vende))
        return obtener_proveedor(cur.lastrowid, con=c)


def actualizar_proveedor(proveedor_id, nombre, telefono, direccion="",
                         vende=""):
    nombre, telefono, direccion, vende = _validar(nombre, telefono, direccion,
                                                  vende)
    with _usar(None) as c:
        if obtener_proveedor(proveedor_id, con=c) is None:
            raise ValueError("El proveedor ya no existe.")
        if _repetido(c, nombre, telefono, excepto_id=proveedor_id):
            raise ValueError("Ya existe otro proveedor con ese nombre y "
                             "teléfono.")
        c.execute("UPDATE proveedores SET nombre = ?, telefono = ?, "
                  "direccion = ?, vende = ? WHERE id = ?",
                  (nombre, telefono, direccion, vende, proveedor_id))
        return obtener_proveedor(proveedor_id, con=c)


def desactivar_proveedor(proveedor_id):
    """Lo oculta de las búsquedas; sus compras y deudas se conservan."""
    with _usar(None) as c:
        c.execute("UPDATE proveedores SET activo = 0 WHERE id = ?",
                  (proveedor_id,))