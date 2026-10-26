"""Demo: caja del día (apertura, cobros, pagos, cierre).
Usa una base temporal: no toca tus datos reales."""
import tempfile
from datetime import date, timedelta
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DB_PATH = Path(_tmp.name) / "demo.db"

from app.base_datos.conexion import transaccion
from app.base_datos.esquema import crear_tablas
from app.servicios import caja, clientes, compras, creditos, inventario, proveedores, ventas

crear_tablas()
polo = inventario.crear_producto("Polo", "Ropa", costo=10, precio_unidad=25, precio_mayor=18, stock=100)
jean = inventario.crear_producto("Jean", "Ropa", costo=40, precio_unidad=90, precio_mayor=70, stock=50)
ana = clientes.crear_cliente("Ana Pérez", "999888777")
lima = proveedores.crear_proveedor("Textiles Lima", "999111222")


def vender(prod, cant, pagos, **kw):
    return ventas.registrar_venta(
        [{"producto_id": prod.id, "cantidad": cant, "tipo": "unidad", "precio": prod.precio_unidad}],
        pagos, **kw)


def mostrar(r):
    print(f"  Vendido {r['vendido']:8.2f} ({r['ventas']} ventas)  Ganancia {r['ganancia']:7.2f}  "
          f"A crédito {r['a_credito']:7.2f}")
    for d in r["por_forma"]:
        print(f"   {d['forma']:14} cobrado {d['cobrado']:7.2f} (ventas {d['cobrado_ventas']:6.2f} "
              f"abonos {d['cobrado_abonos']:6.2f})  pagado {d['pagado']:7.2f} "
              f"(compras {d['pagado_compras']:6.2f} cuotas {d['pagado_cuotas']:6.2f})")
    print(f"   Efectivo: +{r['efectivo_cobrado']:.2f} -{r['efectivo_pagado']:.2f}  "
          f"Digital cobrado {r['digital_cobrado']:.2f}  Esperado {r['efectivo_esperado']}")


print("SIN ABRIR:", caja.estado_dia(), "| tarjetas:", caja.indicadores_dia())

# ---- un día anterior (ayer) que se abrió y nunca se cerró, con una venta a crédito
ayer = date.today() - timedelta(days=1)
caja.abrir_dia(50, hoy=ayer)
v_cred = vender(jean, 2, [{"forma_pago": "Efectivo", "monto": 30}], cliente_id=ana.id,
                credito={"cuotas": 2, "dias": 15})["venta_id"]
with transaccion() as con:      # esa venta es de ayer
    con.execute("UPDATE ventas SET fecha=? || ' 10:00:00' WHERE id=?", (ayer.isoformat(), v_cred))
    con.execute("UPDATE venta_pagos SET fecha=? || ' 10:00:00' WHERE venta_id=?", (ayer.isoformat(), v_cred))
print("\nDÍAS SIN CERRAR:", caja.dias_pendientes())
print("AYER esperado (sin cerrar):", caja.resumen_dia(ayer)["efectivo_esperado"])
caja.cerrar_dia(80, hoy=ayer, nota="Faltaban 0")
print("Apertura sugerida hoy:", caja.sugerir_apertura())

# ---- hoy
print("\nHOY antes de abrir:", caja.indicadores_dia())
caja.abrir_dia(100)
vender(polo, 4, [{"forma_pago": "Efectivo", "monto": 100}])                      # 100 efectivo
vender(polo, 2, [{"forma_pago": "Yape/Plin", "monto": 30}, {"forma_pago": "Efectivo", "monto": 20}])
vender(jean, 1, [{"forma_pago": "Tarjeta", "monto": 90}])
vender(polo, 1, [{"forma_pago": "Efectivo", "monto": 25}])
anulada = vender(polo, 1, [{"forma_pago": "Efectivo", "monto": 25}])["venta_id"]
with transaccion() as con:
    con.execute("UPDATE ventas SET estado='anulada' WHERE id=?", (anulada,))
vender(jean, 1, [{"forma_pago": "Transferencia", "monto": 30}], cliente_id=ana.id,
       credito={"cuotas": 2, "dias": 10})                                           # crédito hoy
cuota = creditos.detalle_credito(v_cred)["cuotas"][0]["id"]
creditos.registrar_pago_cuota(cuota, 40, "Efectivo")                                # abono de la de ayer
compras.registrar_compra([dict(codigo="", nombre="Gorra", categoria="Ropa", cantidad=10,
    costo=5, precio_unidad=10, precio_mayor=8)],
    pagos=[{"forma_pago": "Efectivo", "monto": 50}])                                # sale efectivo
compras.registrar_compra([dict(codigo="", nombre="Medias", categoria="Ropa", cantidad=10,
    costo=3, precio_unidad=6, precio_mayor=5)], proveedor_id=lima.id,
    pagos=[{"forma_pago": "Yape/Plin", "monto": 10}], credito={"cuotas": 2, "dias": 10})
r = caja.resumen_dia()
print("\nRESUMEN DE HOY:"); mostrar(r)
print("  tarjetas:", caja.indicadores_dia())

print("\nERRORES:")
for texto, f in [("abrir otra vez", lambda: caja.abrir_dia(10)),
                 ("apertura negativa", lambda: caja.abrir_dia(-5, hoy=date.today() + timedelta(days=3))),
                 ("apertura letras", lambda: caja.abrir_dia("abc", hoy=date.today() + timedelta(days=3))),
                 ("contado vacío", lambda: caja.cerrar_dia("")),
                 ("cerrar día no abierto", lambda: caja.cerrar_dia(10, hoy=date.today() + timedelta(days=5))),
                 ("cerrar ayer otra vez", lambda: caja.cerrar_dia(10, hoy=ayer))]:
    try:
        f(); print(f"  {texto}: SIN ERROR (mal)")
    except ValueError as err:
        print(f"  {texto}: {err}")

print("\nCIERRE (cuento 5 menos de lo esperado):")
c = caja.cerrar_dia(r["efectivo_esperado"] - 5, nota="Faltaron 5")
print(f"  esperado {c['esperado']}  contado {c['contado']}  diferencia {c['diferencia']}")
print("  estado:", caja.estado_dia()["estado"], "| tarjetas:", caja.indicadores_dia()["abierta"])
print("\nHISTORIAL:")
for h in caja.historial():
    print(f"  {h['fecha']} {h['estado']:10} apertura {h['apertura']:7.2f} esperado {h['esperado']} "
          f"contado {h['contado']} dif {h['diferencia']}")

_tmp.cleanup()