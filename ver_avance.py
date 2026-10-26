"""Muestra lo que llevamos construido. Se puede borrar cuando quieras."""
import tempfile
from pathlib import Path

from app import config
from app.base_datos.conexion import transaccion
from app.base_datos.esquema import crear_tablas
from app.modelos.producto import Producto
from app.utilidades.formato import entero, moneda
from app.utilidades.validaciones import a_entero, a_numero


def titulo(texto):
    print(f"\n======== {texto} ========")


# ------------------------------------------------------------ 1. configuración
titulo("1. Configuración")
print("Tienda:                  ", config.NOMBRE_TIENDA)
print("Moneda:                  ", config.MONEDA)
print("Stock mínimo por defecto:", config.STOCK_MINIMO_DEFECTO)
print("Base de datos:           ", config.DB_PATH)

# ------------------------------------------------- 2. base de datos (real)
titulo("2. Base de datos real")
crear_tablas()
print("¿Se creó el archivo?     ", config.DB_PATH.exists())
with transaccion() as con:
    tablas = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    for tabla in tablas:
        columnas = [c["name"] for c in
                    con.execute(f"PRAGMA table_info({tabla['name']})")]
        print(f"- {tabla['name']}: {', '.join(columnas)}")

# ------------------------------------- 3. un producto (en una base temporal)
titulo("3. Un producto de prueba (base temporal, no ensucia la real)")
with tempfile.TemporaryDirectory() as tmp:
    config.DATOS_DIR = Path(tmp)
    config.DB_PATH = Path(tmp) / "prueba.db"
    crear_tablas()
    with transaccion() as con:
        con.execute(
            "INSERT INTO productos (codigo, categoria, nombre, costo, "
            "precio_unidad, precio_mayor, stock) "
            "VALUES ('CAM-001', 'Camisas', 'Camisa polo', 18, 30, 25, 10)")
        fila = con.execute("SELECT * FROM productos").fetchone()

producto = Producto(**dict(fila))
print(producto)
print("Valor del stock:", moneda(producto.valor_stock),
      f"({entero(producto.stock)} unidades x {moneda(producto.costo)})")
print("¿Stock bajo?   :", producto.bajo_stock,
      f"(stock {producto.stock} <= mínimo {producto.stock_minimo})")

# ----------------------------------------------------------- 4. validaciones
titulo("4. Validaciones de precios")
for texto in ["12.50", "1200", "12,5", "1.200", "abc"]:
    try:
        print(f"{texto!r:8} -> {a_numero(texto, 'Precio')}")
    except ValueError as error:
        print(f"{texto!r:8} -> AVISO: {error}")

titulo("5. Validaciones de cantidades")
for texto in ["7", "3.5"]:
    try:
        print(f"{texto!r:8} -> {a_entero(texto, 'Cantidad')}")
    except ValueError as error:
        print(f"{texto!r:8} -> AVISO: {error}")

print("\nTodo listo.")