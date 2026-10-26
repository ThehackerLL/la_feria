"""Reportes por periodo: hoy, semana, mes y año.

Igual que la caja, NO guarda nada: solo LEE ventas, venta_pagos, compra_pagos
y productos. Todos los periodos llegan hasta "hoy" (la semana empieza el
lunes). Cada uno se compara con el periodo anterior tomando el MISMO tramo
de días, para que la comparación sea justa: este mes hasta el 21 contra el
mes pasado hasta el 21.

Las ventas anuladas no suman. Un pago cuenta como "abono/cuota" cuando se
cobra (o se paga) en un día distinto al de la venta (o compra).
"""
import calendar
from datetime import date, datetime, timedelta

from app.servicios.caja import FORMA_EFECTIVO
from app.servicios.inventario import _usar

PERIODOS = ("hoy", "semana", "mes", "año")
ETIQUETAS = {"hoy": "Hoy", "semana": "Esta semana", "mes": "Este mes", "año": "Este año"}
ANTERIOR = {"hoy": "ayer", "semana": "la semana pasada",
            "mes": "el mes pasado", "año": "el año pasado"}

# Un producto "poco vendido" es el que vendió menos de esta parte de su stock.
UMBRAL_POCO = 0.10


# ------------------------------------------------------------------ periodos
def _fecha(hoy):
    if hoy is None:
        return date.today()
    return hoy.date() if isinstance(hoy, datetime) else hoy


def _mover(dia, meses):
    """Mismo día de otro mes (si no existe, el último día de ese mes)."""
    total = dia.year * 12 + dia.month - 1 + meses
    anio, mes = divmod(total, 12)
    mes += 1
    return date(anio, mes, min(dia.day, calendar.monthrange(anio, mes)[1]))


def rango(periodo, hoy=None):
    """(desde, hasta, desde_anterior, hasta_anterior) como objetos date."""
    h = _fecha(hoy)
    if periodo == "hoy":
        desde = h
        d_ant = h - timedelta(days=1)
        return desde, h, d_ant, d_ant
    if periodo == "semana":
        desde = h - timedelta(days=h.weekday())
        return desde, h, desde - timedelta(days=7), h - timedelta(days=7)
    if periodo == "mes":
        desde = h.replace(day=1)
        return desde, h, _mover(desde, -1), _mover(h, -1)
    if periodo == "año":
        desde = date(h.year, 1, 1)
        return desde, h, date(h.year - 1, 1, 1), _mover(h, -12)
    raise ValueError("Periodo desconocido: elige hoy, semana, mes o año.")


def _cambio(actual, anterior):
    """Variación en % frente al periodo anterior (None si antes no había nada)."""
    if not anterior:
        return None
    return round((actual - anterior) * 100 / anterior, 1)


# ------------------------------------------------------------ cifras sueltas
def _ventas(c, desde, hasta):
    """(cantidad, vendido, ganancia) de las ventas de ese rango de fechas."""
    d, h = desde.isoformat(), hasta.isoformat()
    n, total = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(total), 0) FROM ventas "
        "WHERE estado = 'activa' AND substr(fecha, 1, 10) BETWEEN ? AND ?",
        (d, h)).fetchone()
    costo = c.execute(
        "SELECT COALESCE(SUM(det.cantidad * det.costo_unitario), 0) "
        "FROM venta_detalle det JOIN ventas v ON v.id = det.venta_id "
        "WHERE v.estado = 'activa' AND substr(v.fecha, 1, 10) BETWEEN ? AND ?",
        (d, h)).fetchone()[0]
    return n, round(total, 2), round(total - costo, 2)


def _cobros(c, desde, hasta):
    """Dinero cobrado: efectivo, digital y cuánto de eso fueron abonos/cuotas."""
    d, h = desde.isoformat(), hasta.isoformat()
    sal = {"efectivo": 0.0, "digital": 0.0, "abonos": 0.0}
    for f in c.execute(
            "SELECT p.forma_pago AS forma, "
            "(substr(p.fecha, 1, 10) <> substr(v.fecha, 1, 10)) AS abono, "
            "SUM(p.monto) AS m FROM venta_pagos p JOIN ventas v ON v.id = p.venta_id "
            "WHERE v.estado = 'activa' AND substr(p.fecha, 1, 10) BETWEEN ? AND ? "
            "GROUP BY p.forma_pago, abono", (d, h)):
        sal["efectivo" if f["forma"] == FORMA_EFECTIVO else "digital"] += f["m"]
        if f["abono"]:
            sal["abonos"] += f["m"]
    return {k: round(v, 2) for k, v in sal.items()}


def _pagos(c, desde, hasta):
    """Dinero pagado en compras y cuotas a proveedores."""
    d, h = desde.isoformat(), hasta.isoformat()
    sal = {"efectivo": 0.0, "digital": 0.0, "cuotas": 0.0}
    for f in c.execute(
            "SELECT p.forma_pago AS forma, "
            "(substr(p.fecha, 1, 10) <> substr(k.fecha, 1, 10)) AS cuota, "
            "SUM(p.monto) AS m FROM compra_pagos p JOIN compras k ON k.id = p.compra_id "
            "WHERE substr(p.fecha, 1, 10) BETWEEN ? AND ? "
            "GROUP BY p.forma_pago, cuota", (d, h)):
        sal["efectivo" if f["forma"] == FORMA_EFECTIVO else "digital"] += f["m"]
        if f["cuota"]:
            sal["cuotas"] += f["m"]
    return {k: round(v, 2) for k, v in sal.items()}


# ------------------------------------------------------------------ reporte
def resumen_periodo(periodo, hoy=None, con=None):
    """Todas las cifras del periodo, más su comparación con el anterior."""
    desde, hasta, d_ant, h_ant = rango(periodo, hoy)
    with _usar(con) as c:
        n, vendido, ganancia = _ventas(c, desde, hasta)
        n0, vendido0, ganancia0 = _ventas(c, d_ant, h_ant)
        cobros, pagos = _cobros(c, desde, hasta), _pagos(c, desde, hasta)
    return {
        "periodo": periodo, "etiqueta": ETIQUETAS[periodo],
        "desde": desde, "hasta": hasta, "desde_anterior": d_ant, "hasta_anterior": h_ant,
        "frente_a": ANTERIOR[periodo],
        "ventas": n, "vendido": vendido, "ganancia": ganancia,
        "ticket_promedio": round(vendido / n, 2) if n else 0.0,
        "efectivo_cobrado": cobros["efectivo"], "digital_cobrado": cobros["digital"],
        "cobrado_total": round(cobros["efectivo"] + cobros["digital"], 2),
        "abonos_cobrados": cobros["abonos"],
        "efectivo_pagado": pagos["efectivo"], "digital_pagado": pagos["digital"],
        "pagado_total": round(pagos["efectivo"] + pagos["digital"], 2),
        "cuotas_pagadas": pagos["cuotas"],
        "anterior": {"ventas": n0, "vendido": vendido0, "ganancia": ganancia0},
        "cambio": {"ventas": _cambio(n, n0), "vendido": _cambio(vendido, vendido0),
                   "ganancia": _cambio(ganancia, ganancia0)},
    }


def meses_del_año(anio=None, con=None):
    """Para un año: ventas, ganancia y compras de cada mes (12 filas)."""
    anio = anio or date.today().year
    filas = []
    with _usar(con) as c:
        for mes in range(1, 13):
            desde = date(anio, mes, 1)
            hasta = date(anio, mes, calendar.monthrange(anio, mes)[1])
            n, vendido, ganancia = _ventas(c, desde, hasta)
            pagos = _pagos(c, desde, hasta)
            filas.append({"mes": mes, "ventas": n, "vendido": vendido,
                          "ganancia": ganancia,
                          "pagado": round(pagos["efectivo"] + pagos["digital"], 2)})
    return filas


def dias_del_periodo(periodo, hoy=None, con=None):
    """Ventas, total y ganancia de cada día del periodo (del más reciente al
    más antiguo). Los días sin ventas también salen, con ceros."""
    desde, hasta, _, _ = rango(periodo, hoy)
    with _usar(con) as c:
        ventas = {f["dia"]: (f["n"], f["total"]) for f in c.execute(
            "SELECT substr(fecha, 1, 10) AS dia, COUNT(*) AS n, SUM(total) AS total "
            "FROM ventas WHERE estado = 'activa' AND substr(fecha, 1, 10) BETWEEN ? AND ? "
            "GROUP BY dia", (desde.isoformat(), hasta.isoformat()))}
        costos = {f["dia"]: f["costo"] for f in c.execute(
            "SELECT substr(v.fecha, 1, 10) AS dia, "
            "SUM(det.cantidad * det.costo_unitario) AS costo "
            "FROM venta_detalle det JOIN ventas v ON v.id = det.venta_id "
            "WHERE v.estado = 'activa' AND substr(v.fecha, 1, 10) BETWEEN ? AND ? "
            "GROUP BY dia", (desde.isoformat(), hasta.isoformat()))}
    filas = []
    dia = hasta
    while dia >= desde:
        clave = dia.isoformat()
        n, total = ventas.get(clave, (0, 0.0))
        filas.append({"fecha": clave, "ventas": n, "vendido": round(total, 2),
                      "ganancia": round(total - costos.get(clave, 0.0), 2)})
        dia -= timedelta(days=1)
    return filas


def ventas_del_periodo(periodo, hoy=None, con=None):
    """Cada venta del periodo (no anuladas), de la más reciente a la más antigua.

    Trae: número, fecha y hora, cliente, total, lo pagado hasta hoy, lo que
    falta por cobrar, las formas de pago usadas, el costo y la ganancia.
    """
    from app.servicios.ventas import numero_venta     # evita un ciclo de imports
    desde, hasta, _, _ = rango(periodo, hoy)
    with _usar(con) as c:
        filas = c.execute(
            "SELECT v.id, v.fecha, v.total, COALESCE(cl.nombre, 'Público general') AS cliente, "
            "COALESCE((SELECT SUM(p.monto) FROM venta_pagos p WHERE p.venta_id = v.id), 0) AS pagado, "
            "COALESCE((SELECT GROUP_CONCAT(DISTINCT p.forma_pago) FROM venta_pagos p "
            "         WHERE p.venta_id = v.id), '') AS formas, "
            "COALESCE((SELECT SUM(d.cantidad * d.costo_unitario) FROM venta_detalle d "
            "         WHERE d.venta_id = v.id), 0) AS costo "
            "FROM ventas v LEFT JOIN clientes cl ON cl.id = v.cliente_id "
            "WHERE v.estado = 'activa' AND substr(v.fecha, 1, 10) BETWEEN ? AND ? "
            "ORDER BY v.fecha DESC, v.id DESC",
            (desde.isoformat(), hasta.isoformat())).fetchall()
    return [{"id": f["id"], "numero": numero_venta(f["id"]), "fecha": f["fecha"],
             "cliente": f["cliente"], "total": round(f["total"], 2),
             "pagado": round(f["pagado"], 2),
             "por_cobrar": round(max(0.0, f["total"] - f["pagado"]), 2),
             "formas": f["formas"].replace(",", ", "),
             "costo": round(f["costo"], 2),
             "ganancia": round(f["total"] - f["costo"], 2)} for f in filas]


# ----------------------------------------------------------------- productos
def _unidades_vendidas(c, desde, hasta):
    return {f["producto_id"]: f["u"] for f in c.execute(
        "SELECT det.producto_id, SUM(det.cantidad) AS u FROM venta_detalle det "
        "JOIN ventas v ON v.id = det.venta_id WHERE v.estado = 'activa' "
        "AND substr(v.fecha, 1, 10) BETWEEN ? AND ? GROUP BY det.producto_id",
        (desde.isoformat(), hasta.isoformat()))}


def mas_vendidos(periodo, hoy=None, limite=10, con=None):
    """Los productos más vendidos del periodo (por unidades)."""
    desde, hasta, _, _ = rango(periodo, hoy)
    with _usar(con) as c:
        return [dict(f) for f in c.execute(
            "SELECT p.id, p.codigo, p.nombre, SUM(det.cantidad) AS unidades, "
            "SUM(det.cantidad * det.precio_unitario) AS vendido, p.stock "
            "FROM venta_detalle det JOIN ventas v ON v.id = det.venta_id "
            "JOIN productos p ON p.id = det.producto_id "
            "WHERE v.estado = 'activa' AND substr(v.fecha, 1, 10) BETWEEN ? AND ? "
            "GROUP BY p.id ORDER BY unidades DESC, vendido DESC, p.nombre LIMIT ?",
            (desde.isoformat(), hasta.isoformat(), limite))]


def productos_parados(periodo, hoy=None, limite=7, con=None):
    """Productos con stock que casi no se venden en el periodo.

    Primero los que no vendieron nada (estado "sin_ventas") y luego los que
    vendieron menos del 10 % de su stock ("poco"). Hoy no tiene sentido (casi
    todo está sin vender), así que "hoy" se trata como "semana".
    Un producto creado dentro del periodo no cuenta: todavía no tuvo tiempo de
    venderse.
    Cada fila trae `valor_parado` (stock x costo): es dato de costos, la
    pantalla lo muestra solo con contraseña.
    """
    if periodo == "hoy":
        periodo = "semana"
    desde, hasta, _, _ = rango(periodo, hoy)
    with _usar(con) as c:
        vendidas = _unidades_vendidas(c, desde, hasta)
        ultima = {f["producto_id"]: f["u"] for f in c.execute(
            "SELECT det.producto_id, MAX(substr(v.fecha, 1, 10)) AS u "
            "FROM venta_detalle det JOIN ventas v ON v.id = det.venta_id "
            "WHERE v.estado = 'activa' GROUP BY det.producto_id")}
        productos = c.execute(
            "SELECT id, codigo, nombre, stock, costo FROM productos "
            "WHERE activo = 1 AND stock > 0 AND substr(creado, 1, 10) < ?",
            (desde.isoformat(),)).fetchall()
    h = _fecha(hoy)
    filas = []
    for p in productos:
        u = vendidas.get(p["id"], 0)
        if u == 0:
            estado = "sin_ventas"
        elif u / p["stock"] < UMBRAL_POCO:
            estado = "poco"
        else:
            continue
        ult = ultima.get(p["id"])
        filas.append({
            "id": p["id"], "codigo": p["codigo"], "nombre": p["nombre"],
            "stock": p["stock"], "vendido": u, "estado": estado,
            "ultima_venta": ult,
            "dias_sin_vender": (h - datetime.strptime(ult, "%Y-%m-%d").date()).days if ult else None,
            "valor_parado": round(p["stock"] * p["costo"], 2)})
    filas.sort(key=lambda f: (f["estado"] != "sin_ventas", f["vendido"] / f["stock"],
                              -f["stock"], f["nombre"]))
    return filas[:limite]