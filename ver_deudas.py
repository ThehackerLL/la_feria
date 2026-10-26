"""Demo: deudas con proveedores (compras a crédito, pagos de cuotas, resumen).
Usa una base temporal: no toca tus datos reales."""
import tempfile
from datetime import date, timedelta
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DB_PATH = Path(_tmp.name) / "demo.db"

from app.base_datos.conexion import conectar, transaccion
from app.base_datos.esquema import crear_tablas
from app.servicios import compras, por_pagar, proveedores

crear_tablas()
lima = proveedores.crear_proveedor("Textiles Lima", "999111222", vende="Ropa")
gama = proveedores.crear_proveedor("Jeans Gamarra", "988777666", vende="Jeans")


def item(nombre, cant, costo):
    return dict(codigo="", nombre=nombre, categoria="Ropa", cantidad=cant,
                costo=costo, precio_unidad=costo * 2, precio_mayor=costo * 1.5)


a = compras.registrar_compra(
    [item("Polo", 10, 10)], proveedor_id=lima.id,
    pagos=[{"forma_pago": "Transferencia", "monto": 20}],
    credito={"cuotas": 3, "dias": 10})["compra_id"]
b = compras.registrar_compra(
    [item("Jean", 5, 40)], proveedor_id=gama.id, credito={"cuotas": 1, "dias": 15})["compra_id"]
compras.registrar_compra([item("Gorra", 4, 5)], proveedor_id=lima.id,
                         pagos=[{"forma_pago": "Efectivo", "monto": 20}])  # contado: no es deuda

hoy = date.today()
with transaccion() as con:     # simula: la cuota 1 de la compra A venció hace 5 días
    con.execute("UPDATE compra_cuotas SET vence=? WHERE compra_id=? AND numero=1",
                ((hoy - timedelta(days=5)).isoformat(), a))

print("RESUMEN:", por_pagar.resumen_deudas())
print("\nDEUDAS:")
for d in por_pagar.listar_deudas():
    print(f"  {d['numero']} {d['nombre']:15} total {d['total']:7.2f} debe {d['debe']:7.2f}"
          f" pendientes {d['pendientes']}/{d['cuotas']} vencidas {d['vencidas']}"
          f" próxima {d['proxima']['vence']} ({d['proxima']['estado']})")
print("\nBuscar 'jeans':", [d["numero"] for d in por_pagar.listar_deudas("jeans")])

print("\nPAGO parcial de la cuota vencida (20 por Yape/Plin):")
cuota1 = por_pagar.detalle_deuda(a)["cuotas"][0]
r = por_pagar.registrar_pago_cuota(cuota1["id"], 20, "Yape/Plin")
print("  ", r["numero"], "cuota", r["cuota"], "pagado", r["monto"],
      "→ le debo en la cuota", r["debe_cuota"], "y en total", r["debe_compra"])

print("\nERRORES:")
for texto, args in [("de más", (cuota1["id"], 999, "Efectivo")),
                    ("forma inválida", (cuota1["id"], 5, "Cheque")),
                    ("monto 0", (cuota1["id"], 0, "Efectivo")),
                    ("cuota inexistente", (9999, 5, "Efectivo"))]:
    try:
        por_pagar.registrar_pago_cuota(*args)
    except ValueError as e:
        print("  ", texto, "->", e)

print("\nDETALLE de", por_pagar.numero_compra(a))
d = por_pagar.detalle_deuda(a)
for q in d["cuotas"]:
    print("   cuota", q["numero"], q["vence"], "monto", q["monto"], "pagado", q["pagado"], q["estado"])
for p in d["pagos"]:
    print("   pago", p["forma_pago"], p["monto"])
print("   total", d["total"], "| pagado", d["pagado"], "| debe", d["debe"])
print("Compra al contado sin deuda:", por_pagar.detalle_deuda(3))

print("\nPESTAÑA PROVEEDORES (todos; primero los que se deben):")
proveedores.crear_proveedor("Fatima Flores", "935265352", "Av. Lima 22", "Cajas")
for r in por_pagar.resumen_por_proveedor():
    estado = f"{r['proxima']['vence']} ({r['proxima']['estado']})" if r["proxima"] else "Sin deuda"
    print(f"  {r['nombre']:15} {r['telefono']:10} {r['vende']:6} debe {r['debe']:7.2f}"
          f" vencidas {r['vencidas']} · {estado}")
print("  Buscar 'cajas':", [r["nombre"] for r in por_pagar.resumen_por_proveedor("cajas")])

print("\nLO QUE SE LE HA COMPRADO A Textiles Lima:")
for h in por_pagar.historial_compras(lima.id):
    print(f"  {h['numero']} {h['fecha'][:10]} total {h['total']:.2f} pagado {h['pagado']:.2f} debe {h['debe']:.2f}")
    for l in h["lineas"]:
        print(f"     {l['cantidad']} x {l['nombre']} a {l['costo']:.2f}")
_tmp.cleanup()