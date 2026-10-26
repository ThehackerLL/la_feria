"""Crédito: plan de cuotas, pago de cuotas y consultas para la pestaña Crédito.

Una venta a crédito tiene de 1 a 12 cuotas. El dinero que entra (el abono
inicial y cada pago de cuota) se guarda en venta_pagos con su propia fecha;
credito_cuotas guarda cuánto debe y cuánto lleva pagado cada cuota.
"""
from datetime import date, datetime, timedelta

from app.servicios.inventario import _usar, normalizar

MAX_CUOTAS = 12          # lo máximo que permite el programa
CUOTAS_DEFECTO = 1
DIAS_DEFECTO = 15        # días entre una cuota y la siguiente
DIAS_MAX = 365
DIAS_AVISO = 3           # una cuota se marca "por vencer" faltando estos días
_MARGEN = 0.005          # para no equivocarse por céntimos al comparar


def _hoy(hoy):
    return hoy if hoy is not None else date.today()


def _a_fecha(texto):
    """'2026-10-17' o '2026-10-17 15:04:45' -> date."""
    return datetime.strptime(str(texto)[:10], "%Y-%m-%d").date()


# ------------------------------------------------------------------ el plan
def leer_condiciones(n_cuotas, dias):
    """Valida cuántas cuotas y cada cuántos días. Devuelve (cuotas, días)."""
    try:
        cuotas = int(n_cuotas)
        exacto = (cuotas == float(n_cuotas))
    except (TypeError, ValueError):
        raise ValueError("El número de cuotas debe ser un número entero.")
    if not exacto or not 1 <= cuotas <= MAX_CUOTAS:
        raise ValueError(f"Las cuotas deben ser de 1 a {MAX_CUOTAS}.")
    try:
        entre = int(dias)
        exacto = (entre == float(dias))
    except (TypeError, ValueError):
        raise ValueError("Los días entre cuotas deben ser un número entero.")
    if not exacto or not 1 <= entre <= DIAS_MAX:
        raise ValueError(f"Los días entre cuotas deben ser de 1 a {DIAS_MAX}.")
    return cuotas, entre


def crear_plan(saldo, n_cuotas, dias, desde=None):
    """Reparte el saldo en cuotas iguales.

    Si no se puede repartir exacto (100 en 3 cuotas), lo que sobra de
    céntimos va a la PRIMERA cuota: 33.34, 33.33 y 33.33. La cuota k vence
    k × dias después de `desde` (por defecto, hoy).

    Devuelve [{"numero", "vence" ('YYYY-MM-DD'), "monto"}].
    """
    try:
        centimos = round(float(saldo) * 100)
    except (TypeError, ValueError):
        raise ValueError("El monto a financiar no es válido.")
    if centimos <= 0:
        raise ValueError("No hay saldo para repartir en cuotas.")
    cuotas, entre = leer_condiciones(n_cuotas, dias)
    if centimos < cuotas:
        raise ValueError("El saldo es muy pequeño para tantas cuotas.")
    base, resto = divmod(centimos, cuotas)
    inicio = _hoy(desde)
    plan = []
    for k in range(1, cuotas + 1):
        monto = (base + (resto if k == 1 else 0)) / 100
        plan.append({"numero": k,
                     "vence": (inicio + timedelta(days=entre * k)).isoformat(),
                     "monto": round(monto, 2)})
    return plan


def guardar_plan(con, venta_id, plan):
    """Guarda las cuotas de una venta (la usa registrar_venta al vender)."""
    for cuota in plan:
        con.execute(
            "INSERT INTO credito_cuotas (venta_id, numero, vence, monto) "
            "VALUES (?, ?, ?, ?)",
            (venta_id, cuota["numero"], cuota["vence"], cuota["monto"]))


# --------------------------------------------------------- estado de cuotas
def debe_cuota(monto, pagado):
    """Lo que todavía falta pagar de una cuota (nunca negativo)."""
    resta = round(monto - pagado, 2)
    return resta if resta > _MARGEN else 0.0


def estado_cuota(monto, pagado, vence, hoy=None):
    """'pagada', 'vencida', 'por_vencer' (faltan 3 días o menos) o 'pendiente'.

    El último día para pagar es la fecha de vencimiento: pasa a 'vencida'
    al día siguiente. Una cuota vencida lo sigue siendo hasta pagarse entera.
    """
    if debe_cuota(monto, pagado) == 0:
        return "pagada"
    faltan = (_a_fecha(vence) - _hoy(hoy)).days
    if faltan < 0:
        return "vencida"
    if faltan <= DIAS_AVISO:
        return "por_vencer"
    return "pendiente"


def _cuota(fila, hoy):
    return {"id": fila["id"], "numero": fila["numero"], "vence": fila["vence"],
            "monto": fila["monto"], "pagado": fila["pagado"],
            "debe": debe_cuota(fila["monto"], fila["pagado"]),
            "estado": estado_cuota(fila["monto"], fila["pagado"],
                                   fila["vence"], hoy)}


# ------------------------------------------------------------ pagar una cuota
def registrar_pago_cuota(cuota_id, monto, forma_pago, con=None):
    """Registra lo que el cliente paga de una cuota (puede ser parcial).

    No puede superar lo que esa cuota todavía debe. El pago queda en
    venta_pagos con la fecha de hoy y la forma de pago, así entra en la caja
    del día en que se cobró. Si algo falla, no se guarda nada.

    Devuelve {"venta_id", "numero", "cliente", "cuota", "monto",
    "forma_pago", "debe_cuota", "debe_venta", "fecha"}.
    """
    from app.servicios.ventas import FORMAS_PAGO, numero_venta   # evita ciclo

    if forma_pago not in FORMAS_PAGO:
        raise ValueError("Elige la forma de pago.")
    try:
        monto = round(float(monto), 2)
    except (TypeError, ValueError):
        raise ValueError("El monto del pago no es válido.")
    if monto <= 0:
        raise ValueError("El monto del pago debe ser mayor a 0.")

    with _usar(con) as c:
        cuota = c.execute(
            "SELECT q.id, q.venta_id, q.numero, q.monto, q.pagado, v.estado, "
            "       cl.nombre "
            "FROM credito_cuotas q JOIN ventas v ON v.id = q.venta_id "
            "LEFT JOIN clientes cl ON cl.id = v.cliente_id "
            "WHERE q.id = ?", (cuota_id,)).fetchone()
        if cuota is None:
            raise ValueError("Esa cuota no existe.")
        if cuota["estado"] != "activa":
            raise ValueError("Esa venta está anulada.")
        debe = debe_cuota(cuota["monto"], cuota["pagado"])
        if debe == 0:
            raise ValueError(f"La cuota {cuota['numero']} ya está pagada.")
        if monto > debe + _MARGEN:
            raise ValueError(f"La cuota {cuota['numero']} solo debe "
                             f"{debe:.2f}; no se puede cobrar {monto:.2f}.")
        monto = min(monto, debe)
        nuevo = round(cuota["pagado"] + monto, 2)
        if debe - monto <= _MARGEN:          # se paga completa: sin céntimos sueltos
            nuevo = cuota["monto"]
        c.execute("UPDATE credito_cuotas SET pagado = ? WHERE id = ?",
                  (nuevo, cuota_id))
        c.execute("INSERT INTO venta_pagos (venta_id, forma_pago, monto) "
                  "VALUES (?, ?, ?)", (cuota["venta_id"], forma_pago, monto))
        fecha = c.execute("SELECT datetime('now', 'localtime')").fetchone()[0]
        debe_venta = _debe_venta(c, cuota["venta_id"])

    return {"venta_id": cuota["venta_id"],
            "numero": numero_venta(cuota["venta_id"]),
            "cliente": cuota["nombre"], "cuota": cuota["numero"],
            "monto": monto, "forma_pago": forma_pago,
            "debe_cuota": debe_cuota(cuota["monto"], nuevo),
            "debe_venta": debe_venta, "fecha": fecha}


def _debe_venta(con, venta_id):
    """Lo que falta pagar en total de una venta a crédito."""
    fila = con.execute(
        "SELECT COALESCE(SUM(monto - pagado), 0) AS debe "
        "FROM credito_cuotas WHERE venta_id = ?", (venta_id,)).fetchone()
    return debe_cuota(round(fila["debe"], 2), 0)


# --------------------------------------------------- consultas para la pantalla
def listar_creditos(texto="", hoy=None, con=None):
    """Las ventas a crédito que todavía se deben, una fila por crédito.

    Cada una: {"venta_id", "numero", "fecha", "cliente_id", "nombre",
    "telefono", "total", "debe", "cuotas", "pendientes", "vencidas",
    "proxima": {"numero", "vence", "debe", "estado"}}.
    Orden: primero los que tienen cuotas vencidas, luego por fecha de la
    próxima cuota. `texto` filtra por nombre o teléfono.
    """
    from app.servicios.ventas import numero_venta                # evita ciclo

    hoy = _hoy(hoy)
    with _usar(con) as c:
        ventas = c.execute(
            "SELECT v.id, v.fecha, v.total, v.cliente_id, cl.nombre, "
            "       cl.telefono "
            "FROM ventas v LEFT JOIN clientes cl ON cl.id = v.cliente_id "
            "WHERE v.estado = 'activa' AND EXISTS ("
            "  SELECT 1 FROM credito_cuotas q WHERE q.venta_id = v.id "
            "  AND q.monto - q.pagado > ?)", (_MARGEN,)).fetchall()
        cuotas = {}
        for f in c.execute(
                "SELECT id, venta_id, numero, vence, monto, pagado "
                "FROM credito_cuotas ORDER BY venta_id, numero"):
            cuotas.setdefault(f["venta_id"], []).append(f)

    palabras = normalizar(texto).split()
    lista = []
    for v in ventas:
        todas = [_cuota(f, hoy) for f in cuotas.get(v["id"], [])]
        sin_pagar = [q for q in todas if q["estado"] != "pagada"]
        if not sin_pagar:
            continue
        nombre, telefono = v["nombre"] or "", v["telefono"] or ""
        if palabras and not all(
                p in normalizar(f"{nombre} {telefono}") for p in palabras):
            continue
        proxima = sin_pagar[0]
        lista.append({
            "venta_id": v["id"], "numero": numero_venta(v["id"]),
            "fecha": v["fecha"], "cliente_id": v["cliente_id"],
            "nombre": nombre, "telefono": telefono, "total": v["total"],
            "debe": round(sum(q["debe"] for q in sin_pagar), 2),
            "cuotas": len(todas), "pendientes": len(sin_pagar),
            "vencidas": sum(1 for q in sin_pagar if q["estado"] == "vencida"),
            "proxima": {"numero": proxima["numero"], "vence": proxima["vence"],
                        "debe": proxima["debe"],
                        "estado": proxima["estado"]}})
    lista.sort(key=lambda r: (r["vencidas"] == 0, r["proxima"]["vence"],
                              r["venta_id"]))
    return lista


def detalle_credito(venta_id, hoy=None, con=None):
    """Todo de un crédito: cuotas con su estado y lista de pagos hechos.

    Devuelve None si la venta no tiene crédito. Los pagos incluyen el abono
    inicial (el primero) y cada cuota pagada, con fecha y forma de pago.
    """
    from app.servicios.ventas import numero_venta                # evita ciclo

    hoy = _hoy(hoy)
    with _usar(con) as c:
        venta = c.execute(
            "SELECT v.id, v.fecha, v.total, v.estado, v.cliente_id, "
            "       cl.nombre, cl.telefono "
            "FROM ventas v LEFT JOIN clientes cl ON cl.id = v.cliente_id "
            "WHERE v.id = ?", (venta_id,)).fetchone()
        cuotas = c.execute(
            "SELECT id, numero, vence, monto, pagado FROM credito_cuotas "
            "WHERE venta_id = ? ORDER BY numero", (venta_id,)).fetchall()
        if venta is None or not cuotas:
            return None
        pagos = c.execute(
            "SELECT fecha, forma_pago, monto FROM venta_pagos "
            "WHERE venta_id = ? ORDER BY fecha, id", (venta_id,)).fetchall()
    lista = [_cuota(f, hoy) for f in cuotas]
    return {
        "venta_id": venta["id"], "numero": numero_venta(venta["id"]),
        "fecha": venta["fecha"], "estado": venta["estado"],
        "cliente_id": venta["cliente_id"], "nombre": venta["nombre"] or "",
        "telefono": venta["telefono"] or "", "total": venta["total"],
        "pagado": round(sum(p["monto"] for p in pagos), 2),
        "debe": round(sum(q["debe"] for q in lista), 2),
        "cuotas": lista, "pagos": [dict(p) for p in pagos]}


def resumen_creditos(hoy=None, con=None):
    """Totales para las tarjetas y para el aviso al abrir el programa.

    {"creditos": cuántos se deben, "por_cobrar": total que se debe,
     "vencido": parte de eso que ya venció, "cuotas_vencidas": cuántas,
     "clientes_vencidos": a cuántos clientes}
    """
    lista = listar_creditos(hoy=hoy, con=con)
    hoy = _hoy(hoy)
    with _usar(con) as c:
        vencidas = c.execute(
            "SELECT q.venta_id, q.monto, q.pagado, v.cliente_id "
            "FROM credito_cuotas q JOIN ventas v ON v.id = q.venta_id "
            "WHERE v.estado = 'activa' AND q.vence < ? "
            "AND q.monto - q.pagado > ?",
            (hoy.isoformat(), _MARGEN)).fetchall()
    return {"creditos": len(lista),
            "por_cobrar": round(sum(r["debe"] for r in lista), 2),
            "vencido": round(sum(f["monto"] - f["pagado"] for f in vencidas), 2),
            "cuotas_vencidas": len(vencidas),
            "clientes_vencidos": len({f["cliente_id"] for f in vencidas})}