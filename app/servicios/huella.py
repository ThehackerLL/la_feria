"""Huella digital: el registro de cada producto vendido, que NO se puede borrar
ni cambiar.

Cada producto de cada venta (y de cada cambio de producto) queda anotado aquí
con lo que valía en ese momento: cliente, código, nombre, costo, precio,
descuento, vendedor, forma de pago y tipo de venta (unidad o por mayor).
Aunque después se cambie el nombre o el costo del producto, la huella conserva
lo de ese día.

Cómo se protege:
- La base de datos rechaza cualquier UPDATE o DELETE sobre esta tabla.
- Cada línea lleva un «sello» que depende de la anterior. Si alguien edita la
  base por fuera, el sello ya no coincide y `verificar()` lo detecta.
- «Estado» no se guarda: se calcula con las anulaciones, devoluciones y
  cambios, que también se conservan. Una venta anulada o devuelta sigue
  apareciendo, con «Anulada» (rojo); un producto cambiado, con «Cambio»
  (amarillo); si nada ocurrió, muestra «-».
- Un cambio de producto NO añade una fila a la lista: la fila original solo
  cambia de estado. (El producto nuevo sí queda anotado en la huella, con forma
  de pago de la diferencia, o «Cambio»), pero la lista no lo muestra.)

La tabla se crea sola (CREATE TABLE IF NOT EXISTS). Al crearla se copian las
ventas que ya existían (con vendedor vacío).
"""
import hashlib
from datetime import date, timedelta

from app.servicios.inventario import _usar

PERIODOS = ("hoy", "7 días", "este mes", "todas")
LIMITE = 5000

_TABLA = """
CREATE TABLE IF NOT EXISTS huella (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT    NOT NULL,
    venta_id    INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    cliente     TEXT    NOT NULL,
    codigo      TEXT    NOT NULL,
    producto    TEXT    NOT NULL,
    cantidad    INTEGER NOT NULL,
    costo       REAL    NOT NULL,
    precio      REAL    NOT NULL,
    descuento   REAL    NOT NULL,
    vendedor    TEXT    NOT NULL,
    forma_pago  TEXT    NOT NULL,
    anterior    TEXT    NOT NULL,
    sello       TEXT    NOT NULL,
    tipo        TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_huella_fecha ON huella(fecha);
CREATE INDEX IF NOT EXISTS idx_huella_venta ON huella(venta_id);
CREATE TRIGGER IF NOT EXISTS huella_no_cambiar BEFORE UPDATE ON huella
BEGIN
    SELECT RAISE(ABORT, 'La huella digital no se puede modificar.');
END;
CREATE TRIGGER IF NOT EXISTS huella_no_borrar BEFORE DELETE ON huella
BEGIN
    SELECT RAISE(ABORT, 'La huella digital no se puede borrar.');
END;
"""

_CAMPOS = ("fecha", "venta_id", "producto_id", "cliente", "codigo", "producto",
           "cantidad", "costo", "precio", "descuento", "vendedor", "forma_pago")


def _sello(anterior, fila):
    partes = [anterior]
    for campo in _CAMPOS:
        valor = fila[campo]
        partes.append(f"{valor:.2f}" if isinstance(valor, float) else str(valor))
    # El tipo de venta entra al sello solo si existe: las líneas anteriores a
    # esta columna conservan su sello original.
    if fila["tipo"]:
        partes.append(str(fila["tipo"]))
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


def _ultimo_sello(c):
    fila = c.execute("SELECT sello FROM huella ORDER BY id DESC LIMIT 1").fetchone()
    return fila["sello"] if fila else ""


def preparar(con, rellenar=False):
    """Crea la tabla. Con rellenar=True copia las ventas que ya existían."""
    con.executescript(_TABLA)
    columnas = {f["name"] for f in con.execute("PRAGMA table_info(huella)")}
    if "tipo" not in columnas:           # bases creadas antes de esta columna
        con.execute("ALTER TABLE huella ADD COLUMN tipo TEXT NOT NULL DEFAULT ''")
    if rellenar and con.execute("SELECT 1 FROM huella LIMIT 1").fetchone() is None:
        _rellenar(con)
    return con


def forma_de_pago(pagos, a_credito=False):
    """'Efectivo', 'Efectivo + Yape' o 'Crédito'."""
    if a_credito:
        return "Crédito"
    formas = list(dict.fromkeys(p["forma_pago"] for p in pagos))
    return " + ".join(formas) if formas else "—"


def repartir_descuento(lineas, descuento):
    """Reparte el descuento de la venta entre sus líneas, según lo que vale cada una."""
    bruto = [round(l["cantidad"] * l["precio"], 2) for l in lineas]
    total = sum(bruto)
    if not descuento or total <= 0:
        return [0.0] * len(lineas)
    partes, resto = [], round(descuento, 2)
    for i, b in enumerate(bruto):
        parte = resto if i == len(bruto) - 1 else round(descuento * b / total, 2)
        parte = min(parte, resto)
        partes.append(parte)
        resto = round(resto - parte, 2)
    return partes


def registrar(c, venta_id, fecha, cliente, vendedor, forma_pago, lineas,
              descuento=0):
    """Anota las líneas de una venta (dentro de la misma transacción).

    lineas: {"producto_id", "codigo", "nombre", "cantidad", "costo", "precio",
             "tipo"}  (tipo: "unidad" o "mayor")
    """
    anterior = _ultimo_sello(c)
    for l, desc in zip(lineas, repartir_descuento(lineas, descuento)):
        fila = {"fecha": fecha, "venta_id": venta_id,
                "producto_id": l["producto_id"], "cliente": cliente,
                "codigo": l["codigo"], "producto": l["nombre"],
                "cantidad": int(l["cantidad"]), "costo": float(l["costo"]),
                "precio": float(l["precio"]), "descuento": float(desc),
                "vendedor": vendedor or "", "forma_pago": forma_pago,
                "tipo": l.get("tipo", "")}
        sello = _sello(anterior, fila)
        c.execute(
            "INSERT INTO huella (fecha, venta_id, producto_id, cliente, codigo, "
            "producto, cantidad, costo, precio, descuento, vendedor, forma_pago, "
            "anterior, sello, tipo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(fila[k] for k in _CAMPOS) + (anterior, sello, fila["tipo"]))
        anterior = sello


def _rellenar(c):
    """Copia a la huella las ventas hechas antes de que existiera."""
    ventas = c.execute(
        "SELECT v.id, v.fecha, v.descuento, v.vendedor, "
        "COALESCE(cl.nombre, 'Público general') AS cliente, "
        "EXISTS(SELECT 1 FROM credito_cuotas q WHERE q.venta_id = v.id) AS credito "
        "FROM ventas v LEFT JOIN clientes cl ON cl.id = v.cliente_id "
        "ORDER BY v.id").fetchall()
    for v in ventas:
        lineas = [dict(f) for f in c.execute(
            "SELECT d.producto_id, p.codigo, p.nombre, d.cantidad, "
            "d.costo_unitario AS costo, d.precio_unitario AS precio, "
            "d.tipo AS tipo "
            "FROM venta_detalle d JOIN productos p ON p.id = d.producto_id "
            "WHERE d.venta_id = ? ORDER BY d.id", (v["id"],))]
        if not lineas:
            continue
        pagos = [dict(f) for f in c.execute(
            "SELECT forma_pago FROM venta_pagos WHERE venta_id = ? ORDER BY id",
            (v["id"],))]
        registrar(c, v["id"], v["fecha"], v["cliente"], v["vendedor"],
                  forma_de_pago(pagos, bool(v["credito"])), lineas, v["descuento"])


# ---------------------------------------------------------------- consultas
def _desde(periodo, hoy):
    if periodo == "hoy":
        return hoy.isoformat()
    if periodo == "7 días":
        return (hoy - timedelta(days=6)).isoformat()
    if periodo == "este mes":
        return hoy.replace(day=1).isoformat()
    return None


def _estado(anulada, devuelto, cambiado, cantidad):
    """(texto, color) del estado de una línea.

    Anulada (rojo): la venta se anuló o se devolvió el producto.
    Cambio (amarillo): el producto se cambió por otro.
    '-' sin color: no pasó nada.
    """
    partes, color = [], ""
    if anulada or (devuelto and devuelto >= cantidad):
        partes.append("Anulada")
        color = "peligro"
    elif devuelto:
        partes.append(f"Anulada ({devuelto})")
        color = "peligro"
    if not anulada and cambiado:
        partes.append("Cambio" if cambiado >= cantidad else f"Cambio ({cambiado})")
        color = color or "aviso"
    return (" + ".join(partes), color) if partes else ("-", "")


def _tipo_legible(c, fila):
    """'Unidad', 'Por mayor' o '-' (líneas viejas cuyo tipo ya no se puede saber)."""
    tipo = fila["tipo"]
    if not tipo:       # línea anterior a la columna: se busca en la venta original
        d = c.execute("SELECT tipo FROM venta_detalle WHERE venta_id = ? "
                      "AND producto_id = ? ORDER BY id LIMIT 1",
                      (fila["venta_id"], fila["producto_id"])).fetchone()
        tipo = d["tipo"] if d else ""
    return {"unidad": "Unidad", "mayor": "Por mayor"}.get(tipo, "-")


def listar(periodo="hoy", hoy=None, limite=LIMITE, con=None):
    """Líneas de la huella, la más nueva primero. periodo: ver PERIODOS."""
    if periodo not in PERIODOS:
        raise ValueError("Periodo desconocido.")
    from app.servicios import anulaciones        # (evita un import circular)
    hoy = hoy or date.today()
    desde = _desde(periodo, hoy)
    sql = ("SELECT h.*, "
           "EXISTS(SELECT 1 FROM anulaciones a WHERE a.venta_id = h.venta_id) "
           " AS anulada, "
           "(SELECT COALESCE(SUM(d.cantidad), 0) FROM devoluciones d "
           " WHERE d.venta_id = h.venta_id AND d.producto_id = h.producto_id "
           " AND d.fecha >= h.fecha AND d.producto_nuevo_id IS NULL) AS devuelto, "
           "(SELECT COALESCE(SUM(d.cantidad), 0) FROM devoluciones d "
           " WHERE d.venta_id = h.venta_id AND d.producto_id = h.producto_id "
           " AND d.fecha >= h.fecha AND d.producto_nuevo_id IS NOT NULL) AS cambiado "
           "FROM huella h ")
    args = []
    # El producto nuevo de un cambio no se lista como fila: queda anotado en la
    # huella, pero la fila original solo cambia de estado.
    sql += ("WHERE NOT EXISTS(SELECT 1 FROM devoluciones d "
            "WHERE d.venta_id = h.venta_id AND d.producto_nuevo_id = h.producto_id "
            "AND d.fecha = h.fecha) ")
    if desde:
        sql += "AND substr(h.fecha, 1, 10) >= ? "
        args.append(desde)
    sql += "ORDER BY h.id DESC LIMIT ?"
    args.append(limite)
    with _usar(con) as c:
        preparar(c)
        anulaciones.preparar(c)
        filas = []
        for f in c.execute(sql, args).fetchall():
            d = dict(f)
            d["tipo_venta"] = _tipo_legible(c, d)
            d["estado"], d["color"] = _estado(d["anulada"], d["devuelto"],
                                              d["cambiado"], d["cantidad"])
            d["anulado"] = "No" if d["estado"] == "-" else "Sí"
            d["ganancia"] = round(
                d["cantidad"] * (d["precio"] - d["costo"]) - d["descuento"], 2)
            filas.append(d)
        return filas


def verificar(con=None):
    """None si la huella está intacta; si no, el id de la primera línea alterada."""
    with _usar(con) as c:
        preparar(c)
        anterior = ""
        for f in c.execute("SELECT * FROM huella ORDER BY id"):
            if f["anterior"] != anterior or f["sello"] != _sello(anterior, f):
                return f["id"]
            anterior = f["sello"]
        return None