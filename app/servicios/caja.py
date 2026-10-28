"""Caja del día: apertura, cobros y pagos por forma de pago, y cierre.

La caja NO guarda cada movimiento: solo LEE lo que ya está registrado en
venta_pagos (dinero que entra) y compra_pagos (dinero que sale), cada uno con
su propia fecha. Lo único que guarda es la apertura y el cierre de cada día
(tabla caja_dias).

El día es el del calendario: a las 00:00 empieza uno nuevo.

Efectivo esperado = apertura + efectivo cobrado - efectivo pagado.
Yape/Plin, transferencia y tarjeta no entran al cajón: se llaman "digital".
Las ventas a crédito cuentan como vendidas el día que se hicieron; el dinero
cuenta el día que realmente se cobra (abono inicial o cuota).

Las ventas anuladas no suman como vendidas, pero el dinero que se cobró de ellas
sigue contando el día que se cobró; al anular, lo devuelto sale de la caja del
día de la anulación (así los días cerrados no cambian). Las compras hechas antes de que existieran los
pagos de compra no tienen pagos registrados y por eso no aparecen aquí.
"""
from datetime import date, datetime

from app.servicios import anulaciones
from app.servicios.inventario import _usar
from app.servicios.ventas import FORMAS_PAGO

FORMA_EFECTIVO = "Efectivo"
FORMAS_DIGITALES = tuple(f for f in FORMAS_PAGO if f != FORMA_EFECTIVO)

ABIERTA, CERRADA, SIN_CONTAR = "abierta", "cerrada", "sin_contar"

_TABLA = """
CREATE TABLE IF NOT EXISTS caja_dias (
    fecha      TEXT PRIMARY KEY,
    apertura   REAL NOT NULL CHECK (apertura >= 0),
    abierta_en TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    estado     TEXT NOT NULL DEFAULT 'abierta'
               CHECK (estado IN ('abierta', 'cerrada', 'sin_contar')),
    esperado   REAL,
    contado    REAL,
    diferencia REAL,
    cerrada_en TEXT,
    nota       TEXT NOT NULL DEFAULT ''
)
"""


# ------------------------------------------------------------------ ayudas
def _dia(hoy):
    """date, 'AAAA-MM-DD' o None (hoy) -> 'AAAA-MM-DD'."""
    if hoy is None:
        hoy = date.today()
    if isinstance(hoy, datetime):
        hoy = hoy.date()
    if isinstance(hoy, date):
        return hoy.isoformat()
    return str(hoy)[:10]


def _preparar(con):
    con.execute(_TABLA)
    anulaciones.preparar(con)
    return con


def _dinero(valor, texto):
    try:
        monto = round(float(str(valor).replace(",", ".").strip()), 2)
    except (TypeError, ValueError):
        raise ValueError(texto) from None
    if monto < 0:
        raise ValueError(texto)
    return monto


def _fila_dia(fila):
    return None if fila is None else dict(fila)


# ------------------------------------------------------------ estado del día
def estado_dia(hoy=None, con=None):
    """La fila de caja de ese día (dict) o None si todavía no se abrió."""
    with _usar(con) as c:
        _preparar(c)
        return _fila_dia(c.execute("SELECT * FROM caja_dias WHERE fecha = ?",
                                   (_dia(hoy),)).fetchone())


def sugerir_apertura(hoy=None, con=None):
    """Efectivo contado en el último cierre anterior (o 0 si no hay)."""
    with _usar(con) as c:
        _preparar(c)
        fila = c.execute(
            "SELECT contado FROM caja_dias WHERE fecha < ? AND contado IS NOT NULL "
            "ORDER BY fecha DESC LIMIT 1", (_dia(hoy),)).fetchone()
        return round(fila["contado"], 2) if fila else 0.0


def dias_pendientes(hoy=None, con=None):
    """Fechas anteriores a hoy que se abrieron y nunca se cerraron."""
    with _usar(con) as c:
        _preparar(c)
        return [f["fecha"] for f in c.execute(
            "SELECT fecha FROM caja_dias WHERE estado = ? AND fecha < ? "
            "ORDER BY fecha", (ABIERTA, _dia(hoy)))]


def historial(limite=60, con=None):
    """Aperturas y cierres, del más reciente al más antiguo."""
    with _usar(con) as c:
        _preparar(c)
        return [dict(f) for f in c.execute(
            "SELECT * FROM caja_dias ORDER BY fecha DESC LIMIT ?", (limite,))]


# ----------------------------------------------------- lo que pasó en el día
def resumen_dia(hoy=None, con=None):
    """Todo lo que entró y salió en ese día, calculado de los registros."""
    f = _dia(hoy)
    with _usar(con) as c:
        _preparar(c)
        dia = _fila_dia(c.execute("SELECT * FROM caja_dias WHERE fecha = ?",
                                  (f,)).fetchone())

        ventas = c.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(total), 0) AS total FROM ventas "
            "WHERE estado = 'activa' AND substr(fecha, 1, 10) = ?", (f,)).fetchone()
        costo = c.execute(
            "SELECT COALESCE(SUM(d.cantidad * d.costo_unitario), 0) FROM venta_detalle d "
            "JOIN ventas v ON v.id = d.venta_id "
            "WHERE v.estado = 'activa' AND substr(v.fecha, 1, 10) = ?",
            (f,)).fetchone()[0]

        por = {forma: {"forma": forma, "cobrado_ventas": 0.0, "cobrado_abonos": 0.0,
                       "pagado_compras": 0.0, "pagado_cuotas": 0.0,
                       "devuelto": 0.0}
               for forma in FORMAS_PAGO}

        for fila in c.execute(
                "SELECT p.forma_pago AS forma, SUM(p.monto) AS m, "
                "CASE WHEN substr(v.fecha, 1, 10) = ? THEN 'venta' ELSE 'abono' END AS o "
                "FROM venta_pagos p JOIN ventas v ON v.id = p.venta_id "
                "WHERE substr(p.fecha, 1, 10) = ? "
                "GROUP BY p.forma_pago, o", (f, f)):
            if fila["forma"] in por:
                clave = "cobrado_ventas" if fila["o"] == "venta" else "cobrado_abonos"
                por[fila["forma"]][clave] += fila["m"]

        for fila in c.execute(
                "SELECT p.forma_pago AS forma, SUM(p.monto) AS m, "
                "CASE WHEN substr(k.fecha, 1, 10) = ? THEN 'compra' ELSE 'cuota' END AS o "
                "FROM compra_pagos p JOIN compras k ON k.id = p.compra_id "
                "WHERE substr(p.fecha, 1, 10) = ? "
                "GROUP BY p.forma_pago, o", (f, f)):
            if fila["forma"] in por:
                clave = "pagado_compras" if fila["o"] == "compra" else "pagado_cuotas"
                por[fila["forma"]][clave] += fila["m"]

        for forma, monto in anulaciones.devuelto_por_forma(f, c).items():
            if forma in por:
                por[forma]["devuelto"] += monto

        # Lo que aún deben las ventas vigentes (sin contar las anuladas).
        cobrado_vigentes = c.execute(
            "SELECT COALESCE(SUM(p.monto), 0) FROM venta_pagos p "
            "JOIN ventas v ON v.id = p.venta_id "
            "WHERE v.estado = 'activa' AND substr(v.fecha, 1, 10) = ? "
            "AND substr(p.fecha, 1, 10) = ?", (f, f)).fetchone()[0]

    filas = []
    for forma in FORMAS_PAGO:
        d = por[forma]
        for clave in ("cobrado_ventas", "cobrado_abonos", "pagado_compras",
                      "pagado_cuotas", "devuelto"):
            d[clave] = round(d[clave], 2)
        d["cobrado"] = round(d["cobrado_ventas"] + d["cobrado_abonos"], 2)
        # «pagado» = todo lo que sale: compras, cuotas y devoluciones.
        d["pagado"] = round(d["pagado_compras"] + d["pagado_cuotas"]
                            + d["devuelto"], 2)
        filas.append(d)

    def suma(clave, formas=None):
        return round(sum(d[clave] for d in filas
                         if formas is None or d["forma"] in formas), 2)

    vendido = round(ventas["total"], 2)
    cobrado_ventas = suma("cobrado_ventas")
    efectivo = por[FORMA_EFECTIVO]
    apertura = dia["apertura"] if dia else None
    return {
        "fecha": f, "dia": dia,
        "ventas": ventas["n"], "vendido": vendido,
        "ganancia": round(vendido - costo, 2),
        "a_credito": round(max(0.0, vendido - cobrado_vigentes), 2),
        "devuelto_total": suma("devuelto"),
        "por_forma": filas,
        "cobrado_ventas": cobrado_ventas,
        "cobrado_abonos": suma("cobrado_abonos"),
        "cobrado_total": suma("cobrado"),
        "pagado_total": suma("pagado"),
        "efectivo_cobrado": efectivo["cobrado"],
        "efectivo_pagado": efectivo["pagado"],
        "digital_cobrado": suma("cobrado", FORMAS_DIGITALES),
        "digital_pagado": suma("pagado", FORMAS_DIGITALES),
        "apertura": apertura,
        "efectivo_esperado": (None if apertura is None else round(
            apertura + efectivo["cobrado"] - efectivo["pagado"], 2)),
    }


def indicadores_dia(hoy=None, con=None):
    """Las 4 tarjetas que se ven mientras se vende (pantalla Ventas)."""
    r = resumen_dia(hoy, con)
    abierta = bool(r["dia"]) and r["dia"]["estado"] == ABIERTA
    return {"abierta": abierta, "estado": r["dia"]["estado"] if r["dia"] else None,
            "vendido": r["vendido"], "ganancia": r["ganancia"],
            "efectivo": r["efectivo_esperado"], "digital": r["digital_cobrado"]}


# ------------------------------------------------------- abrir y cerrar caja
def abrir_dia(apertura, hoy=None, con=None):
    """Abre la caja del día con el efectivo con el que se empieza."""
    f = _dia(hoy)
    monto = _dinero(apertura, "Apertura: escribe cuánto efectivo hay (0 o más).")
    with _usar(con) as c:
        _preparar(c)
        previo = c.execute("SELECT estado FROM caja_dias WHERE fecha = ?",
                           (f,)).fetchone()
        if previo:
            raise ValueError("La caja de hoy ya está abierta." if previo["estado"] == ABIERTA
                             else "La caja de hoy ya fue cerrada.")
        c.execute("INSERT INTO caja_dias (fecha, apertura) VALUES (?, ?)", (f, monto))
        return _fila_dia(c.execute("SELECT * FROM caja_dias WHERE fecha = ?",
                                   (f,)).fetchone())


def _exigir_abierta(c, f):
    fila = c.execute("SELECT estado FROM caja_dias WHERE fecha = ?", (f,)).fetchone()
    if fila is None:
        raise ValueError("Ese día la caja no se abrió.")
    if fila["estado"] != ABIERTA:
        raise ValueError("Ese día la caja ya está cerrada.")


def cerrar_dia(contado, hoy=None, nota="", con=None):
    """Cierra el día con el efectivo realmente contado.

    Devuelve el resumen del día más esperado, contado y diferencia
    (diferencia = contado - esperado: negativa si falta dinero).
    """
    f = _dia(hoy)
    monto = _dinero(contado, "Efectivo contado: escribe cuánto hay (0 o más).")
    with _usar(con) as c:
        _preparar(c)
        _exigir_abierta(c, f)
        r = resumen_dia(f, c)
        esperado = r["efectivo_esperado"]
        diferencia = round(monto - esperado, 2)
        c.execute(
            "UPDATE caja_dias SET estado = ?, esperado = ?, contado = ?, "
            "diferencia = ?, nota = ?, cerrada_en = datetime('now', 'localtime') "
            "WHERE fecha = ?",
            (CERRADA, esperado, monto, diferencia, (nota or "").strip(), f))
        r["esperado"], r["contado"], r["diferencia"] = esperado, monto, diferencia
        r["dia"] = _fila_dia(c.execute("SELECT * FROM caja_dias WHERE fecha = ?",
                                       (f,)).fetchone())
        return r


def cerrar_sin_contar(hoy, nota="", con=None):
    """Para un día que se olvidó cerrar: queda registrado el esperado, sin conteo."""
    f = _dia(hoy)
    with _usar(con) as c:
        _preparar(c)
        _exigir_abierta(c, f)
        esperado = resumen_dia(f, c)["efectivo_esperado"]
        c.execute(
            "UPDATE caja_dias SET estado = ?, esperado = ?, nota = ?, "
            "cerrada_en = datetime('now', 'localtime') WHERE fecha = ?",
            (SIN_CONTAR, esperado, (nota or "").strip(), f))
        return _fila_dia(c.execute("SELECT * FROM caja_dias WHERE fecha = ?",
                                   (f,)).fetchone())