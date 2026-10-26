"""Diagnóstico: por qué Reportes sale 'próximamente'. Borrar después."""
import importlib
import os

BASE = os.path.dirname(os.path.abspath(__file__))

ARCHIVOS = [
    ("app/interfaz/pantallas/reportes.py", "class PantallaReportes", "Exportar a Excel"),
    ("app/servicios/reportes.py", "def ventas_del_periodo", "def dias_del_periodo"),
    ("app/servicios/excel.py", "def exportar_reporte", "from openpyxl import"),
]

print("=== Archivos ===")
for ruta, a, b in ARCHIVOS:
    p = os.path.join(BASE, *ruta.split("/"))
    if not os.path.exists(p):
        print(f"FALTA   {ruta}")
        continue
    texto = open(p, encoding="utf-8", errors="replace").read()
    print(f"{'OK     ' if a in texto and b in texto else 'MAL    '} {ruta}"
          f"  ({len(texto.splitlines())} líneas)"
          + ("" if a in texto else f"  <- no contiene: {a}")
          + ("" if b in texto else f"  <- no contiene: {b}"))

print("\n=== Importación ===")
try:
    m = importlib.import_module("app.interfaz.pantallas.reportes")
    print("Clase PantallaReportes:", "existe" if hasattr(m, "PantallaReportes") else "NO existe")
except Exception as error:
    print("ERROR al importar:", type(error).__name__, error)