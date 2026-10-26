"""Demo: compras con forma de pago, proveedor guardado y crédito.
Usa una base temporal: no toca tus datos reales."""
import tempfile
from pathlib import Path

from app import config

_tmp = tempfile.TemporaryDirectory()
config.DB_PATH = Path(_tmp.name) / "demo.db"

from app.base_datos.conexion import conectar
from app.base_datos.esquema import crear_tablas
from app.servicios import compras, proveedores

crear_tablas()
prov = proveedores.crear_proveedor("Textiles Lima", "999111222", vende="Polos")


def item(**k):
    base = dict(codigo="P-1", nombre="Polo", categoria="Polos", cantidad=10,
                costo=8, precio_unidad=15, precio_mayor=12)
    base.update(k)
    return base


print("1) Al contado, pagado por Transferencia")
r = compras.registrar_compra(
    [item()], pagos=[{"forma_pago": "Transferencia", "monto": 80}],
    proveedor_id=prov.id)
print("  ", r["proveedor"], r["total"], r["pagos"])

print("2) A crédito: paga 20 al recibir y el resto en 3 cuotas")
r = compras.registrar_compra(
    [item()], pagos=[{"forma_pago": "Yape/Plin", "monto": 20}],
    proveedor_id=prov.id, credito={"cuotas": 3, "dias": 10})
print("  ", "abono", r["credito"]["abono"], "saldo", r["credito"]["saldo"])
for c in r["credito"]["cuotas"]:
    print("   cuota", c["numero"], c["vence"], c["monto"])

print("3) Errores (no debe guardarse nada):")
for texto, args in [
    ("crédito sin proveedor", dict(credito={"cuotas": 2, "dias": 5})),
    ("pagó menos del total", dict(proveedor_id=prov.id, pagos=[{"forma_pago": "Efectivo", "monto": 79}])),
    ("forma inválida", dict(proveedor_id=prov.id, pagos=[{"forma_pago": "Cheque", "monto": 80}])),
]:
    try:
        compras.registrar_compra([item()], **args)
    except ValueError as e:
        print("  ", texto, "->", e)

con = conectar()
print("Compras:", con.execute("SELECT COUNT(*) FROM compras").fetchone()[0],
      "| Pagos:", con.execute("SELECT COUNT(*) FROM compra_pagos").fetchone()[0],
      "| Cuotas:", con.execute("SELECT COUNT(*) FROM compra_cuotas").fetchone()[0],
      "| Stock:", con.execute("SELECT stock FROM productos").fetchone()[0])
con.close()
_tmp.cleanup()