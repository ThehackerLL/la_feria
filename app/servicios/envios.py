"""Envíos: paquetes que se mandan a los clientes por Olva, Shalom o a domicilio.

El envío lo paga siempre el cliente, así que aquí no hay dinero: solo se anota
a quién, adónde, con qué servicio y la guía. Un envío se liga a la venta de
la que salió (así se ve qué productos lleva); también puede crearse suelto.

La tabla se crea sola (CREATE TABLE IF NOT EXISTS).
"""
from datetime import datetime

from app.servicios import clientes
from app.servicios.inventario import _usar, normalizar

SERVICIOS = ("Olva", "Shalom", "Domicilio")

_TABLA = """
CREATE TABLE IF NOT EXISTS envios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha      TEXT NOT NULL,
    cliente_id INTEGER REFERENCES clientes(id),
    nombre     TEXT NOT NULL,
    telefono   TEXT NOT NULL DEFAULT '',
    dni        TEXT NOT NULL DEFAULT '',
    servicio   TEXT NOT NULL,
    destino    TEXT NOT NULL,
    guia       TEXT NOT NULL DEFAULT '',
    venta_id   INTEGER REFERENCES ventas(id),
    nota       TEXT NOT NULL DEFAULT '',
    estado     TEXT NOT NULL DEFAULT 'Pendiente',   -- ya no se usa
    enviado_en TEXT,                                -- ya no se usa
    entregado_en TEXT                               -- ya no se usa
);
CREATE INDEX IF NOT EXISTS idx_envios_venta ON envios(venta_id);
"""


def _preparar(con):
    con.executescript(_TABLA)
    return con


def _ahora(ahora):
    return (ahora or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def _texto(valor):
    return " ".join(str(valor or "").split())


def _numero_venta(texto):
    """'V-000012', 'v12' o '12' -> 12. Vacío -> None."""
    limpio = _texto(texto).upper().replace("V-", "").replace("V", "").lstrip("0")
    if not _texto(texto):
        return None
    if not limpio.isdigit():
        raise ValueError("Venta: escribe el número, por ejemplo V-000012.")
    return int(limpio)


def _validar(con, datos):
    nombre = _texto(datos.get("nombre"))
    if not nombre:
        raise ValueError("Escribe el nombre de quien recibe.")
    servicio = datos.get("servicio")
    if servicio not in SERVICIOS:
        raise ValueError("Elige el servicio: Olva, Shalom o Domicilio.")
    destino = _texto(datos.get("destino"))
    if not destino:
        raise ValueError("Escribe el destino (ciudad y agencia, o la dirección).")
    venta_id = _numero_venta(datos.get("venta"))
    if venta_id is not None and con.execute(
            "SELECT 1 FROM ventas WHERE id = ?", (venta_id,)).fetchone() is None:
        raise ValueError("Esa venta no existe.")
    cliente_id = datos.get("cliente_id")
    return {"cliente_id": cliente_id or None, "nombre": nombre,
            "telefono": clientes._limpiar_telefono(datos.get("telefono")),
            "dni": clientes._limpiar_dni(datos.get("dni")),
            "servicio": servicio, "destino": destino,
            "guia": _texto(datos.get("guia")), "venta_id": venta_id,
            "nota": _texto(datos.get("nota"))}


def _a_dict(fila):
    d = dict(fila)
    d["venta"] = f"V-{d['venta_id']:06d}" if d.get("venta_id") else ""
    return d


# ---------------------------------------------------------------- consultas
def listar(texto="", con=None):
    """Envíos del más nuevo al más viejo.

    texto: busca en nombre, teléfono, destino, guía, servicio y número de venta.
    """
    palabras = normalizar(texto).split()
    with _usar(con) as c:
        _preparar(c)
        filas = [_a_dict(f) for f in c.execute(
            "SELECT * FROM envios ORDER BY id DESC")]
    if not palabras:
        return filas
    resultado = []
    for f in filas:
        campos = normalizar(f"{f['nombre']} {f['telefono']} {f['destino']} "
                            f"{f['guia']} {f['venta']} {f['servicio']}")
        if all(p in campos for p in palabras):
            resultado.append(f)
    return resultado


def obtener(envio_id, con=None):
    with _usar(con) as c:
        _preparar(c)
        fila = c.execute("SELECT * FROM envios WHERE id = ?",
                         (envio_id,)).fetchone()
        return _a_dict(fila) if fila else None


def contar(con=None):
    """Cuántos envíos hay registrados."""
    with _usar(con) as c:
        _preparar(c)
        return c.execute("SELECT COUNT(*) FROM envios").fetchone()[0]


def validar(datos, con=None):
    """Revisa los datos de un envío sin guardar nada. Falla con ValueError."""
    with _usar(con) as c:
        _preparar(c)
        _validar(c, datos)


# -------------------------------------------------------------- escritura
def crear(datos, ahora=None, con=None):
    """Registra un envío nuevo (queda Pendiente). Devuelve su id.

    datos: nombre, servicio, destino y, opcionales, cliente_id, telefono, dni,
    guia, venta (número de venta) y nota.
    """
    with _usar(con) as c:
        _preparar(c)
        v = _validar(c, datos)
        return c.execute(
            "INSERT INTO envios (fecha, cliente_id, nombre, telefono, dni, "
            "servicio, destino, guia, venta_id, nota) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_ahora(ahora), v["cliente_id"], v["nombre"], v["telefono"],
             v["dni"], v["servicio"], v["destino"], v["guia"], v["venta_id"],
             v["nota"])).lastrowid


def actualizar(envio_id, datos, con=None):
    """Corrige los datos de un envío (no cambia su estado)."""
    with _usar(con) as c:
        _preparar(c)
        if c.execute("SELECT 1 FROM envios WHERE id = ?",
                     (envio_id,)).fetchone() is None:
            raise ValueError("Ese envío ya no existe.")
        v = _validar(c, datos)
        c.execute(
            "UPDATE envios SET cliente_id = ?, nombre = ?, telefono = ?, "
            "dni = ?, servicio = ?, destino = ?, guia = ?, venta_id = ?, "
            "nota = ? WHERE id = ?",
            (v["cliente_id"], v["nombre"], v["telefono"], v["dni"],
             v["servicio"], v["destino"], v["guia"], v["venta_id"], v["nota"],
             envio_id))


def quitar(envio_id, con=None):
    """Borra un envío (por ejemplo, uno registrado por error)."""
    with _usar(con) as c:
        _preparar(c)
        if c.execute("DELETE FROM envios WHERE id = ?",
                     (envio_id,)).rowcount != 1:
            raise ValueError("Ese envío ya no existe.")