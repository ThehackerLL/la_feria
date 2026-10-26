"""Demo: reportes por periodo (hoy, semana, mes, año), comparación y productos.
Usa una base temporal y una fecha fija (miércoles 21/10/2026): no toca tus datos."""
import tempfile
from datetime import date
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DB_PATH = Path(_tmp.name) / "demo.db"

from app.base_datos.conexion import transaccion
from app.base_datos.esquema import crear_tablas
from app.servicios import clientes, compras, creditos, inventario, proveedores, reportes, ventas

HOY = date(2026, 10, 21)
crear_tablas()
polo = inventario.crear_producto("Polo", "Ropa", costo=10, precio_unidad=25, precio_mayor=18, stock=500)
jean = inventario.crear_producto("Jean", "Ropa", costo=40, precio_unidad=90, precio_mayor=70, stock=500)
short = inventario.crear_producto("Short", "Ropa", costo=4, precio_unidad=10, precio_mayor=8, stock=500)
chaleco = inventario.crear_producto("Chaleco", "Ropa", costo=20, precio_unidad=50, precio_mayor=40, stock=500)
medias = inventario.crear_producto("Medias", "Ropa", costo=3, precio_unidad=6, precio_mayor=5, stock=500)
ana = clientes.crear_cliente("Ana Pérez", "999888777")
lima = proveedores.crear_proveedor("Textiles Lima", "999111222")


def vender(fecha, prod, cant, forma, **kw):
    """Vende y cambia la fecha de la venta (y de sus pagos) a `fecha`."""
    pagos = [{"forma_pago": forma, "monto": cant * prod.precio_unidad}] if forma else []
    r = ventas.registrar_venta(
        [{"producto_id": prod.id, "cantidad": cant, "tipo": "unidad", "precio": prod.precio_unidad}],
        kw.pop("pagos", pagos), **kw)
    with transaccion() as con:
        con.execute("UPDATE ventas SET fecha=? WHERE id=?", (fecha + " 11:00:00", r["venta_id"]))
        con.execute("UPDATE venta_pagos SET fecha=? WHERE venta_id=?", (fecha + " 11:00:00", r["venta_id"]))
    return r["venta_id"]


vender("2026-10-21", polo, 4, "Efectivo")        # A  100
vender("2026-10-21", jean, 1, "Yape/Plin")       # B   90
vender("2026-10-19", polo, 2, "Tarjeta")         # C   50
vender("2026-10-05", jean, 1, "Efectivo")        # D   90
vender("2026-09-15", polo, 3, "Efectivo")        # E   75
vender("2026-09-25", jean, 1, "Efectivo")        # F   90 (mes pasado, pero después del día 21)
vender("2025-10-10", jean, 2, "Efectivo")        # G  180 (año pasado)
vender("2026-10-12", polo, 1, "Efectivo")        # H   25 (semana pasada)
vender("2026-10-02", short, 5, "Efectivo")       # I   50
j = vender("2026-10-10", jean, 1, None, cliente_id=ana.id, credito={"cuotas": 2, "dias": 10},
           pagos=[{"forma_pago": "Efectivo", "monto": 30}])              # J 90 a crédito
cuota = creditos.detalle_credito(j)["cuotas"][0]["id"]
creditos.registrar_pago_cuota(cuota, 30, "Efectivo")                     # cuota cobrada HOY (real)
item = lambda n: dict(codigo="", nombre=n, categoria="Ropa", cantidad=10, costo=5,
                      precio_unidad=10, precio_mayor=8)
compras.registrar_compra([item("Gorra")], pagos=[{"forma_pago": "Efectivo", "monto": 50}])
k = compras.registrar_compra([item("Cinta")], proveedor_id=lima.id,
                             pagos=[{"forma_pago": "Yape/Plin", "monto": 10}],
                             credito={"cuotas": 2, "dias": 10})["compra_id"]
with transaccion() as con:                          # esa compra fue el 10/10; el pago de 10 es de HOY
    con.execute("UPDATE compras SET fecha='2026-10-10 09:00:00' WHERE id=?", (k,))
    con.execute("UPDATE compra_pagos SET fecha='2026-10-21 12:00:00' WHERE compra_id=?", (k,))
    con.execute("UPDATE compras SET fecha='2026-10-21 09:00:00' WHERE id<>?", (k,))
    con.execute("UPDATE compra_pagos SET fecha='2026-10-21 09:00:00' WHERE compra_id<>?", (k,))
    con.execute("UPDATE productos SET creado='2026-01-01 08:00:00' WHERE nombre IN "
                "('Polo','Jean','Short','Chaleco','Medias')")   # Gorra y Cinta son de hoy
    for p, st in ((polo, 100), (jean, 50), (short, 100), (chaleco, 30), (medias, 20)):
        con.execute("UPDATE productos SET stock=? WHERE id=?", (st, p.id))

malos = 0


def revisar(texto, real, esperado):
    global malos
    ok = real == esperado
    malos += not ok
    print(f"  {'OK ' if ok else 'MAL'} {texto}: {real}" + ("" if ok else f"  (esperaba {esperado})"))


print("RANGOS:")
for p in reportes.PERIODOS:
    print(" ", p, [d.isoformat() for d in reportes.rango(p, HOY)])

esperado = {   # vendido, ventas, ganancia, anterior vendido, cambio %
    "hoy": (190, 2, 110, 0, None),
    "semana": (240, 3, 140, 25, 860.0),
    "mes": (495, 7, 285, 75, 560.0),
    "año": (660, 9, 380, 180, 266.7),
}
for p, (v, n, g, ant, cam) in esperado.items():
    r = reportes.resumen_periodo(p, HOY)
    print(f"\n{r['etiqueta'].upper()} ({r['desde']} a {r['hasta']}) frente a {r['frente_a']}:")
    revisar("vendido", r["vendido"], v)
    revisar("ventas", r["ventas"], n)
    revisar("ganancia", r["ganancia"], g)
    revisar("vendido anterior", r["anterior"]["vendido"], ant)
    revisar("cambio %", r["cambio"]["vendido"], cam)
r = reportes.resumen_periodo("hoy", HOY)
print("\nCOBROS Y PAGOS DE HOY:")
revisar("efectivo cobrado", r["efectivo_cobrado"], 130.0)     # 100 + cuota 30
revisar("digital cobrado", r["digital_cobrado"], 90.0)
revisar("abonos/cuotas cobrados", r["abonos_cobrados"], 30.0)
revisar("pagado total", r["pagado_total"], 60.0)              # 50 efectivo + 10 Yape (cuota)
revisar("cuotas pagadas a proveedores", r["cuotas_pagadas"], 10.0)
revisar("ticket promedio", r["ticket_promedio"], 95.0)

print("\nMESES DE 2026:")
m = reportes.meses_del_año(2026)
revisar("octubre vendido", m[9]["vendido"], 495.0)
revisar("septiembre vendido", m[8]["vendido"], 165.0)
revisar("enero vendido", m[0]["vendido"], 0.0)
revisar("suma de los 12 meses", round(sum(f["vendido"] for f in m), 2), 660.0)

print("\nMÁS VENDIDOS (mes):")
mv = reportes.mas_vendidos("mes", HOY)
for f in mv:
    print(f"   {f['nombre']:8} {f['unidades']} u  S/ {f['vendido']:.2f}")
revisar("orden", [f["nombre"] for f in mv], ["Polo", "Short", "Jean"])

print("\nPRODUCTOS PARADOS (semana):")
for f in reportes.productos_parados("semana", HOY):
    print(f"   {f['nombre']:8} stock {f['stock']:3} vendió {f['vendido']} {f['estado']:10} "
          f"última {f['ultima_venta']} ({f['dias_sin_vender']} días) valor S/ {f['valor_parado']}")
revisar("orden semana", [f["nombre"] for f in reportes.productos_parados("semana", HOY)],
        ["Short", "Chaleco", "Medias", "Jean", "Polo"])
print("PRODUCTOS PARADOS (mes):")
pm = reportes.productos_parados("mes", HOY)
for f in pm:
    print(f"   {f['nombre']:8} stock {f['stock']:3} vendió {f['vendido']} {f['estado']}")
revisar("orden mes", [f["nombre"] for f in pm], ["Chaleco", "Medias", "Short", "Jean", "Polo"])
revisar("'hoy' usa la semana", reportes.productos_parados("hoy", HOY), reportes.productos_parados("semana", HOY))

try:
    reportes.rango("siglo", HOY)
except ValueError as err:
    print("\nERROR esperado:", err)

print("\n>>> TODO CORRECTO" if not malos else f"\n>>> {malos} COSAS MAL")
_tmp.cleanup()