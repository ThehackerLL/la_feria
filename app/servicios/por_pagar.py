"""Deudas con proveedores: lo que debemos de las compras a crédito.

Es el espejo de creditos.py (lo que nos deben los clientes). Una compra a
crédito tiene de 1 a 12 cuotas. El dinero que sale (lo pagado al recibir y
cada pago de cuota) se guarda en compra_pagos con su propia fecha;
compra_cuotas guarda cuánto se debe y cuánto lleva pagado cada cuota.

También arma lo que muestra la pestaña Proveedores: todos los proveedores con
lo que se les debe, y lo que se le ha comprado a cada uno.
"""
from app.servicios import compras, creditos, proveedores
from app.servicios.inventario import _usar, normalizar

_MARGEN = creditos._MARGEN


def numero_compra(compra_id):
    """1 -> 'C-000001' (el número de compra que se ve en pantalla)."""
    return f"C-{int(compra_id):06d}"


# ------------------------------------------------------------ pagar una cuota
def registrar_pago_cuota(cuota_id, monto, forma_pago, con=None):
    """Registra lo que se le paga al proveedor de una cuota (puede ser parcial).

    No puede superar lo que esa cuota todavía debe. El pago queda en
    compra_pagos con la fecha de hoy y la forma de pago, así sale de la caja
    del día en que se pagó. Si algo falla, no se guarda nada.

    Devuelve {"compra_id", "numero", "proveedor", "cuota", "monto",
    "forma_pago", "debe_cuota", "debe_compra", "fecha"}.
    """
    if forma_pago not in compras.FORMAS_PAGO_COMPRA:
        raise ValueError("Elige la forma de pago.")
    try:
        monto = round(float(monto), 2)
    except (TypeError, ValueError):
        raise ValueError("El monto del pago no es válido.")
    if monto <= 0:
        raise ValueError("El monto del pago debe ser mayor a 0.")

    with _usar(con) as c:
        cuota = c.execute(
            "SELECT q.id, q.compra_id, q.numero, q.monto, q.pagado, "
            "       COALESCE(p.nombre, co.proveedor, '') AS nombre "
            "FROM compra_cuotas q JOIN compras co ON co.id = q.compra_id "
            "LEFT JOIN proveedores p ON p.id = co.proveedor_id "
            "WHERE q.id = ?", (cuota_id,)).fetchone()
        if cuota is None:
            raise ValueError("Esa cuota no existe.")
        debe = creditos.debe_cuota(cuota["monto"], cuota["pagado"])
        if debe == 0:
            raise ValueError(f"La cuota {cuota['numero']} ya está pagada.")
        if monto > debe + _MARGEN:
            raise ValueError(f"La cuota {cuota['numero']} solo debe "
                             f"{debe:.2f}; no se puede pagar {monto:.2f}.")
        monto = min(monto, debe)
        nuevo = round(cuota["pagado"] + monto, 2)
        if debe - monto <= _MARGEN:          # se paga completa: sin céntimos sueltos
            nuevo = cuota["monto"]
        c.execute("UPDATE compra_cuotas SET pagado = ? WHERE id = ?",
                  (nuevo, cuota_id))
        c.execute("INSERT INTO compra_pagos (compra_id, forma_pago, monto) "
                  "VALUES (?, ?, ?)", (cuota["compra_id"], forma_pago, monto))
        fecha = c.execute("SELECT datetime('now', 'localtime')").fetchone()[0]
        debe_compra = _debe_compra(c, cuota["compra_id"])

    return {"compra_id": cuota["compra_id"],
            "numero": numero_compra(cuota["compra_id"]),
            "proveedor": cuota["nombre"], "cuota": cuota["numero"],
            "monto": monto, "forma_pago": forma_pago,
            "debe_cuota": creditos.debe_cuota(cuota["monto"], nuevo),
            "debe_compra": debe_compra, "fecha": fecha}


def _debe_compra(con, compra_id):
    """Lo que falta pagar en total de una compra a crédito."""
    fila = con.execute(
        "SELECT COALESCE(SUM(monto - pagado), 0) AS debe "
        "FROM compra_cuotas WHERE compra_id = ?", (compra_id,)).fetchone()
    return creditos.debe_cuota(round(fila["debe"], 2), 0)


# --------------------------------------------------- consultas para la pantalla
def listar_deudas(texto="", hoy=None, con=None):
    """Las compras a crédito que todavía se deben, una fila por compra.

    Cada una: {"compra_id", "numero", "fecha", "proveedor_id", "nombre",
    "telefono", "total", "debe", "cuotas", "pendientes", "vencidas",
    "proxima": {"numero", "vence", "debe", "estado"}}.
    Orden: primero las que tienen cuotas vencidas, luego por fecha de la
    próxima cuota. `texto` filtra por nombre o teléfono del proveedor.
    """
    hoy = creditos._hoy(hoy)
    with _usar(con) as c:
        filas = c.execute(
            "SELECT co.id, co.fecha, co.total, co.proveedor_id, "
            "       COALESCE(p.nombre, co.proveedor, '') AS nombre, "
            "       COALESCE(p.telefono, '') AS telefono "
            "FROM compras co LEFT JOIN proveedores p "
            "ON p.id = co.proveedor_id "
            "WHERE EXISTS (SELECT 1 FROM compra_cuotas q "
            "  WHERE q.compra_id = co.id AND q.monto - q.pagado > ?)",
            (_MARGEN,)).fetchall()
        cuotas = {}
        for f in c.execute(
                "SELECT id, compra_id, numero, vence, monto, pagado "
                "FROM compra_cuotas ORDER BY compra_id, numero"):
            cuotas.setdefault(f["compra_id"], []).append(f)

    palabras = normalizar(texto).split()
    lista = []
    for v in filas:
        todas = [creditos._cuota(f, hoy) for f in cuotas.get(v["id"], [])]
        sin_pagar = [q for q in todas if q["estado"] != "pagada"]
        if not sin_pagar:
            continue
        if palabras and not all(
                p in normalizar(f"{v['nombre']} {v['telefono']}")
                for p in palabras):
            continue
        proxima = sin_pagar[0]
        lista.append({
            "compra_id": v["id"], "numero": numero_compra(v["id"]),
            "fecha": v["fecha"], "proveedor_id": v["proveedor_id"],
            "nombre": v["nombre"], "telefono": v["telefono"],
            "total": v["total"],
            "debe": round(sum(q["debe"] for q in sin_pagar), 2),
            "cuotas": len(todas), "pendientes": len(sin_pagar),
            "vencidas": sum(1 for q in sin_pagar if q["estado"] == "vencida"),
            "proxima": {"numero": proxima["numero"], "vence": proxima["vence"],
                        "debe": proxima["debe"],
                        "estado": proxima["estado"]}})
    lista.sort(key=lambda r: (r["vencidas"] == 0, r["proxima"]["vence"],
                              r["compra_id"]))
    return lista


def detalle_deuda(compra_id, hoy=None, con=None):
    """Todo de una compra a crédito: cuotas con su estado y pagos hechos.

    Devuelve None si la compra no tiene crédito. Los pagos incluyen lo
    pagado al recibir (el primero) y cada cuota pagada, con fecha y forma.
    """
    hoy = creditos._hoy(hoy)
    with _usar(con) as c:
        compra = c.execute(
            "SELECT co.id, co.fecha, co.total, co.proveedor_id, "
            "       COALESCE(p.nombre, co.proveedor, '') AS nombre, "
            "       COALESCE(p.telefono, '') AS telefono "
            "FROM compras co LEFT JOIN proveedores p "
            "ON p.id = co.proveedor_id WHERE co.id = ?",
            (compra_id,)).fetchone()
        cuotas = c.execute(
            "SELECT id, numero, vence, monto, pagado FROM compra_cuotas "
            "WHERE compra_id = ? ORDER BY numero", (compra_id,)).fetchall()
        if compra is None or not cuotas:
            return None
        pagos = c.execute(
            "SELECT fecha, forma_pago, monto FROM compra_pagos "
            "WHERE compra_id = ? ORDER BY fecha, id", (compra_id,)).fetchall()
    lista = [creditos._cuota(f, hoy) for f in cuotas]
    return {
        "compra_id": compra["id"], "numero": numero_compra(compra["id"]),
        "fecha": compra["fecha"], "proveedor_id": compra["proveedor_id"],
        "nombre": compra["nombre"], "telefono": compra["telefono"],
        "total": compra["total"],
        "pagado": round(sum(p["monto"] for p in pagos), 2),
        "debe": round(sum(q["debe"] for q in lista), 2),
        "cuotas": lista, "pagos": [dict(p) for p in pagos]}


def resumen_deudas(hoy=None, con=None):
    """Totales para las tarjetas y para el aviso al abrir el programa.

    {"deudas": cuántas compras se deben, "por_pagar": total que se debe,
     "vencido": parte de eso que ya venció, "cuotas_vencidas": cuántas,
     "proveedores_vencidos": a cuántos proveedores}
    """
    lista = listar_deudas(hoy=hoy, con=con)
    hoy = creditos._hoy(hoy)
    with _usar(con) as c:
        vencidas = c.execute(
            "SELECT q.compra_id, q.monto, q.pagado, co.proveedor_id, "
            "       co.proveedor "
            "FROM compra_cuotas q JOIN compras co ON co.id = q.compra_id "
            "WHERE q.vence < ? AND q.monto - q.pagado > ?",
            (hoy.isoformat(), _MARGEN)).fetchall()
    return {"deudas": len(lista),
            "por_pagar": round(sum(r["debe"] for r in lista), 2),
            "vencido": round(sum(f["monto"] - f["pagado"] for f in vencidas), 2),
            "cuotas_vencidas": len(vencidas),
            "proveedores_vencidos": len({f["proveedor_id"] or f["proveedor"]
                                         for f in vencidas})}


# ------------------------------------------------- la pestaña Proveedores
def resumen_por_proveedor(texto="", hoy=None, con=None):
    """TODOS los proveedores, con lo que se les debe a cada uno.

    Cada uno: {"id", "nombre", "telefono", "direccion", "vende", "debe",
    "deudas" (compras a crédito que se le deben), "vencidas" (cuotas),
    "proxima": None o {"vence", "estado", "debe"}}.

    Orden: primero los que tienen deuda (los de cuotas vencidas, y luego
    los que vencen antes) y debajo los que no se les debe nada, por nombre.
    `texto` filtra por nombre, teléfono o rubro.
    """
    with _usar(con) as c:
        guardados = proveedores.buscar_proveedores(texto, con=c)
        deudas = listar_deudas(hoy=hoy, con=c)
    por_proveedor = {}
    for d in deudas:
        por_proveedor.setdefault(d["proveedor_id"], []).append(d)

    lista = []
    for p in guardados:
        propias = por_proveedor.get(p.id, [])
        proxima = None
        if propias:
            primera = min(propias, key=lambda d: d["proxima"]["vence"])
            proxima = {"vence": primera["proxima"]["vence"],
                       "estado": primera["proxima"]["estado"],
                       "debe": primera["proxima"]["debe"]}
        lista.append({
            "id": p.id, "nombre": p.nombre, "telefono": p.telefono,
            "direccion": p.direccion, "vende": p.vende,
            "debe": round(sum(d["debe"] for d in propias), 2),
            "deudas": len(propias),
            "vencidas": sum(d["vencidas"] for d in propias),
            "proxima": proxima})
    lista.sort(key=lambda r: (
        r["debe"] == 0, r["vencidas"] == 0,
        r["proxima"]["vence"] if r["proxima"] else "",
        normalizar(r["nombre"])))
    return lista


def historial_compras(proveedor_id, con=None):
    """Lo que se le ha comprado a un proveedor, de la más nueva a la más vieja.

    Cada compra: {"compra_id", "numero", "fecha", "total", "pagado", "debe",
    "lineas": [{"codigo", "nombre", "cantidad", "costo"}]}.
    "pagado" es lo que ya salió de caja por esa compra (compras antiguas,
    anteriores a los pagos, muestran 0).
    """
    with _usar(con) as c:
        compras_ = c.execute(
            "SELECT id, fecha, total FROM compras WHERE proveedor_id = ? "
            "ORDER BY fecha DESC, id DESC", (proveedor_id,)).fetchall()
        resultado = []
        for co in compras_:
            lineas = c.execute(
                "SELECT p.codigo, p.nombre, d.cantidad, d.costo_unitario "
                "FROM compra_detalle d JOIN productos p ON p.id = d.producto_id "
                "WHERE d.compra_id = ? ORDER BY d.id", (co["id"],)).fetchall()
            pagado = c.execute(
                "SELECT COALESCE(SUM(monto), 0) AS t FROM compra_pagos "
                "WHERE compra_id = ?", (co["id"],)).fetchone()["t"]
            resultado.append({
                "compra_id": co["id"], "numero": numero_compra(co["id"]),
                "fecha": co["fecha"], "total": co["total"],
                "pagado": round(pagado, 2),
                "debe": _debe_compra(c, co["id"]),
                "lineas": [{"codigo": l["codigo"], "nombre": l["nombre"],
                            "cantidad": l["cantidad"],
                            "costo": l["costo_unitario"]} for l in lineas]})
    return resultado