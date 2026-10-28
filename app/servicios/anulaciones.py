"""Ventas hechas: consultar una venta y anularla.

Anular NO borra nada: la venta queda en el historial como «anulada», con la
fecha y el motivo. Al anular:
- las unidades vuelven al stock (salvo que se marque «dañado»: entonces no);
- todo el dinero que el cliente había pagado (venta, abono o cuotas) se
  devuelve, y esa devolución sale de la caja del DÍA EN QUE SE ANULA
  (los días ya cerrados no cambian);
- si era a crédito, la deuda deja de existir (las cuotas ya no se cobran).

Devolución parcial: el cliente devuelve un producto (o parte de sus unidades)
y se queda con el resto. La venta se reduce (líneas, total y cuotas), así que
los reportes y la caja salen bien solos. Lo devuelto primero baja lo que el
cliente debe; solo el sobrante se devuelve en dinero. Queda anotado en la
tabla devoluciones.

Tablas propias (se crean solas): anulaciones y reembolsos.
"""
from datetime import datetime

from app.base_datos.conexion import transaccion
from app.servicios.inventario import _usar
from app.servicios.ventas import FORMAS_PAGO, numero_venta

_TABLAS = """
CREATE TABLE IF NOT EXISTS anulaciones (
    venta_id INTEGER PRIMARY KEY REFERENCES ventas(id),
    fecha    TEXT NOT NULL,
    motivo   TEXT NOT NULL,
    al_stock INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS reembolsos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id   INTEGER NOT NULL REFERENCES ventas(id),
    fecha      TEXT    NOT NULL,
    forma_pago TEXT    NOT NULL,
    monto      REAL    NOT NULL CHECK (monto > 0)
);
CREATE TABLE IF NOT EXISTS devoluciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id    INTEGER NOT NULL REFERENCES ventas(id),
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    fecha       TEXT    NOT NULL,
    cantidad    INTEGER NOT NULL CHECK (cantidad > 0),
    valor       REAL    NOT NULL,
    dinero      REAL    NOT NULL DEFAULT 0,
    forma_pago  TEXT    NOT NULL DEFAULT '',
    al_stock    INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_reembolsos_fecha ON reembolsos(fecha);
"""


def preparar(con):
    """Crea las tablas si faltan (la caja también la llama)."""
    con.executescript(_TABLAS)
    columnas = {f["name"] for f in con.execute("PRAGMA table_info(anulaciones)")}
    if "al_stock" not in columnas:       # bases creadas antes de esta opción
        con.execute("ALTER TABLE anulaciones ADD COLUMN al_stock "
                    "INTEGER NOT NULL DEFAULT 1")
    return con


def _ahora(ahora):
    return (ahora or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def _neto_por_forma(c, venta_id):
    """[(forma, monto)] de lo que el cliente tiene pagado de verdad:
    lo cobrado menos lo que ya se le devolvió, forma por forma."""
    neto = {}
    for f in c.execute("SELECT forma_pago, SUM(monto) AS m FROM venta_pagos "
                       "WHERE venta_id = ? GROUP BY forma_pago", (venta_id,)):
        neto[f["forma_pago"]] = f["m"]
    for f in c.execute("SELECT forma_pago, SUM(monto) AS m FROM reembolsos "
                       "WHERE venta_id = ? GROUP BY forma_pago", (venta_id,)):
        neto[f["forma_pago"]] = neto.get(f["forma_pago"], 0) - f["m"]
    # Si se devolvió en una forma distinta a la cobrada, se compensa con las otras.
    falta = -sum(m for m in neto.values() if m < 0)
    for forma in list(neto):
        if neto[forma] < 0:
            neto[forma] = 0.0
        elif falta > 0:
            quitar = min(neto[forma], falta)
            neto[forma] -= quitar
            falta -= quitar
    return [(f, round(m, 2)) for f, m in neto.items() if m > 0.004]


# ---------------------------------------------------------------- consultas
def listar_ventas(desde=None, hasta=None, texto="", limite=300, con=None):
    """Ventas (activas y anuladas), de la más reciente a la más antigua.

    desde/hasta: 'AAAA-MM-DD' (incluidos). texto: número o cliente.
    """
    sql = ("SELECT v.id, v.fecha, v.total, v.estado, "
           "COALESCE(c.nombre, 'Público general') AS cliente, "
           "COALESCE((SELECT SUM(p.monto) FROM venta_pagos p "
           "          WHERE p.venta_id = v.id), 0) "
           "- COALESCE((SELECT SUM(r.monto) FROM reembolsos r "
           "           WHERE r.venta_id = v.id), 0) AS pagado, "
           "a.motivo AS motivo, a.fecha AS fecha_anulada "
           "FROM ventas v LEFT JOIN clientes c ON c.id = v.cliente_id "
           "LEFT JOIN anulaciones a ON a.venta_id = v.id WHERE 1 = 1 ")
    args = []
    if desde:
        sql += "AND substr(v.fecha, 1, 10) >= ? "
        args.append(str(desde)[:10])
    if hasta:
        sql += "AND substr(v.fecha, 1, 10) <= ? "
        args.append(str(hasta)[:10])
    texto = (texto or "").strip()
    if texto:
        sql += "AND (COALESCE(c.nombre, 'Público general') LIKE ? OR v.id = ?) "
        solo = texto.upper().replace("V-", "").lstrip("0")
        args += [f"%{texto}%", int(solo) if solo.isdigit() else -1]
    sql += "ORDER BY v.id DESC LIMIT ?"
    args.append(limite)
    with _usar(con) as c:
        preparar(c)
        filas = []
        for f in c.execute(sql, args):
            d = dict(f)
            d["numero"] = numero_venta(d["id"])
            d["pagado"] = round(max(0.0, d["pagado"]), 2)
            d["debe"] = (round(max(0.0, d["total"] - d["pagado"]), 2)
                         if d["estado"] == "activa" else 0.0)
            filas.append(d)
        return filas


def detalle_venta(venta_id, con=None):
    """Todo de una venta: líneas, pagos, devoluciones y datos de anulación."""
    with _usar(con) as c:
        preparar(c)
        v = c.execute(
            "SELECT v.*, COALESCE(c.nombre, 'Público general') AS cliente "
            "FROM ventas v LEFT JOIN clientes c ON c.id = v.cliente_id "
            "WHERE v.id = ?", (venta_id,)).fetchone()
        if v is None:
            return None
        lineas = [dict(f) for f in c.execute(
            "SELECT d.id, d.producto_id, d.cantidad, d.tipo, d.precio_unitario, "
            "p.codigo, p.nombre "
            "FROM venta_detalle d JOIN productos p ON p.id = d.producto_id "
            "WHERE d.venta_id = ? ORDER BY d.id", (venta_id,))]
        for l in lineas:
            l["subtotal"] = round(l["cantidad"] * l["precio_unitario"], 2)
        pagos = [dict(f) for f in c.execute(
            "SELECT fecha, forma_pago, monto FROM venta_pagos "
            "WHERE venta_id = ? ORDER BY id", (venta_id,))]
        anulacion = c.execute("SELECT fecha, motivo, al_stock FROM anulaciones "
                              "WHERE venta_id = ?", (venta_id,)).fetchone()
        por_forma = _neto_por_forma(c, venta_id)
        pagado = round(sum(m for _, m in por_forma), 2)
        devs = [dict(f) for f in c.execute(
            "SELECT d.fecha, d.cantidad, d.valor, d.dinero, d.forma_pago, "
            "d.al_stock, p.nombre FROM devoluciones d "
            "JOIN productos p ON p.id = d.producto_id "
            "WHERE d.venta_id = ? ORDER BY d.id", (venta_id,))]
        d = dict(v)
        d.update({"numero": numero_venta(venta_id), "lineas": lineas,
                  "pagos": pagos, "pagado": pagado, "por_forma": por_forma,
                  "devoluciones": devs,
                  "debe": round(max(0.0, v["total"] - pagado), 2),
                  "anulacion": dict(anulacion) if anulacion else None})
        return d


def devuelto_por_forma(fecha, con=None):
    """{forma_pago: dinero devuelto ese día}. Lo usa la caja."""
    with _usar(con) as c:
        preparar(c)
        return {f["forma_pago"]: f["m"] for f in c.execute(
            "SELECT forma_pago, SUM(monto) AS m FROM reembolsos "
            "WHERE substr(fecha, 1, 10) = ? GROUP BY forma_pago",
            (str(fecha)[:10],))}


# ------------------------------------------------------------------- anular
def anular_venta(venta_id, motivo, volver_al_stock=True, ahora=None, con=None):
    """Anula una venta completa. Devuelve un resumen de lo que pasó.

    volver_al_stock=False: la mercadería no se puede volver a vender
    (dañada); el stock no cambia.
    """
    motivo = " ".join(str(motivo or "").split())
    if len(motivo) < 3:
        raise ValueError("Escribe el motivo de la anulación.")
    fecha = _ahora(ahora)
    with _usar(con) as c:
        preparar(c)
        v = c.execute("SELECT id, estado, total FROM ventas WHERE id = ?",
                      (venta_id,)).fetchone()
        if v is None:
            raise ValueError("No se encontró esa venta.")
        if v["estado"] != "activa":
            raise ValueError("Esa venta ya estaba anulada.")

        for l in (c.execute("SELECT producto_id, SUM(cantidad) AS n "
                            "FROM venta_detalle WHERE venta_id = ? "
                            "GROUP BY producto_id", (venta_id,)).fetchall()
                  if volver_al_stock else []):
            c.execute("UPDATE productos SET stock = stock + ? WHERE id = ?",
                      (l["n"], l["producto_id"]))

        devuelto = []
        for forma, monto in _neto_por_forma(c, venta_id):
            c.execute("INSERT INTO reembolsos (venta_id, fecha, forma_pago, "
                      "monto) VALUES (?, ?, ?, ?)",
                      (venta_id, fecha, forma, monto))
            devuelto.append({"forma_pago": forma, "monto": monto})

        c.execute("UPDATE ventas SET estado = 'anulada' WHERE id = ?", (venta_id,))
        c.execute("INSERT INTO anulaciones (venta_id, fecha, motivo, al_stock) "
                  "VALUES (?, ?, ?, ?)",
                  (venta_id, fecha, motivo, 1 if volver_al_stock else 0))
    return {"venta_id": venta_id, "numero": numero_venta(venta_id),
            "devuelto": devuelto, "volvio_al_stock": bool(volver_al_stock),
            "total_devuelto": round(sum(d["monto"] for d in devuelto), 2)}


# ------------------------------------------------------- devolución parcial
def _calcular_devolucion(c, venta_id, detalle_id, cantidad):
    """Valida y calcula una devolución sin guardar nada."""
    v = c.execute("SELECT id, estado, subtotal, descuento, total FROM ventas "
                  "WHERE id = ?", (venta_id,)).fetchone()
    if v is None:
        raise ValueError("No se encontró esa venta.")
    if v["estado"] != "activa":
        raise ValueError("Esa venta está anulada.")
    linea = c.execute(
        "SELECT d.id, d.producto_id, d.cantidad, d.precio_unitario, p.nombre "
        "FROM venta_detalle d JOIN productos p ON p.id = d.producto_id "
        "WHERE d.id = ? AND d.venta_id = ?", (detalle_id, venta_id)).fetchone()
    if linea is None:
        raise ValueError("Ese producto no es de esta venta.")
    try:
        cantidad = int(cantidad)
    except (TypeError, ValueError):
        raise ValueError("Escribe cuántas unidades devuelve.") from None
    if cantidad < 1 or cantidad > linea["cantidad"]:
        raise ValueError(f"Las unidades deben ser de 1 a {linea['cantidad']}.")
    restantes = c.execute("SELECT SUM(cantidad) FROM venta_detalle "
                          "WHERE venta_id = ?", (venta_id,)).fetchone()[0]
    if cantidad >= restantes:
        raise ValueError("Está devolviendo todo: usa «Anular venta».")

    bruto = round(cantidad * linea["precio_unitario"], 2)
    desc = (round(v["descuento"] * bruto / v["subtotal"], 2)
            if v["subtotal"] > 0 else 0.0)
    valor = round(bruto - desc, 2)
    pagado = round(sum(m for _, m in _neto_por_forma(c, venta_id)), 2)
    debe = round(max(0.0, v["total"] - pagado), 2)
    baja_deuda = min(valor, debe)
    dinero = round(valor - baja_deuda, 2)
    return {"linea": linea, "cantidad": cantidad, "bruto": bruto,
            "descuento": desc, "valor": valor, "baja_deuda": baja_deuda,
            "dinero": dinero, "nombre": linea["nombre"]}


def vista_previa_devolucion(venta_id, detalle_id, cantidad, con=None):
    """Lo que pasaría al devolver: valor, deuda que baja y dinero a devolver."""
    with _usar(con) as c:
        preparar(c)
        r = _calcular_devolucion(c, venta_id, detalle_id, cantidad)
    return {k: r[k] for k in ("cantidad", "valor", "baja_deuda", "dinero",
                              "nombre")}


def devolver_producto(venta_id, detalle_id, cantidad, forma_pago="Efectivo",
                      volver_al_stock=True, ahora=None, con=None):
    """Devolución parcial: el cliente se queda con la venta menos ese producto.

    Primero se descuenta lo que el cliente todavía debe; solo el resto se le
    devuelve en dinero, por la forma de pago elegida (sale de la caja de hoy).
    """
    fecha = _ahora(ahora)
    with _usar(con) as c:
        preparar(c)
        r = _calcular_devolucion(c, venta_id, detalle_id, cantidad)
        if r["dinero"] > 0 and forma_pago not in FORMAS_PAGO:
            raise ValueError("Elige en qué forma se devuelve el dinero.")
        linea, n = r["linea"], r["cantidad"]

        # La venta queda con lo que el cliente se quedó.
        if n == linea["cantidad"]:
            c.execute("DELETE FROM venta_detalle WHERE id = ?", (detalle_id,))
        else:
            c.execute("UPDATE venta_detalle SET cantidad = cantidad - ? "
                      "WHERE id = ?", (n, detalle_id))
        c.execute("UPDATE ventas SET subtotal = ROUND(subtotal - ?, 2), "
                  "descuento = ROUND(descuento - ?, 2), "
                  "total = ROUND(total - ?, 2) WHERE id = ?",
                  (r["bruto"], r["descuento"], r["valor"], venta_id))
        if volver_al_stock:
            c.execute("UPDATE productos SET stock = stock + ? WHERE id = ?",
                      (n, linea["producto_id"]))

        # Deuda: se rebajan las últimas cuotas pendientes.
        falta = r["baja_deuda"]
        for cuota in c.execute(
                "SELECT id, monto, pagado FROM credito_cuotas "
                "WHERE venta_id = ? ORDER BY numero DESC", (venta_id,)).fetchall():
            if falta <= 0:
                break
            quitar = round(min(falta, cuota["monto"] - cuota["pagado"]), 2)
            if quitar <= 0:
                continue
            nuevo = round(cuota["monto"] - quitar, 2)
            if nuevo <= 0:
                c.execute("DELETE FROM credito_cuotas WHERE id = ?", (cuota["id"],))
            else:
                c.execute("UPDATE credito_cuotas SET monto = ? WHERE id = ?",
                          (nuevo, cuota["id"]))
            falta = round(falta - quitar, 2)

        if r["dinero"] > 0:
            c.execute("INSERT INTO reembolsos (venta_id, fecha, forma_pago, "
                      "monto) VALUES (?, ?, ?, ?)",
                      (venta_id, fecha, forma_pago, r["dinero"]))
        c.execute("INSERT INTO devoluciones (venta_id, producto_id, fecha, "
                  "cantidad, valor, dinero, forma_pago, al_stock) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (venta_id, linea["producto_id"], fecha, n, r["valor"],
                   r["dinero"], forma_pago if r["dinero"] > 0 else "",
                   1 if volver_al_stock else 0))
    return {"venta_id": venta_id, "numero": numero_venta(venta_id),
            "producto": r["nombre"], "cantidad": n, "valor": r["valor"],
            "baja_deuda": r["baja_deuda"], "dinero": r["dinero"],
            "volvio_al_stock": bool(volver_al_stock)}