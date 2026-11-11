"""Configuración general de La Feria."""
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Programa instalado (.exe) en la PC del cliente:
    # los datos van en C:\LaFeria, separados del programa.
    PROGRAMA_DIR = Path(sys.executable).parent
    DATOS_BASE = Path("C:/LaFeria")
else:
    # Mientras programamos: todo dentro de la carpeta del proyecto.
    PROGRAMA_DIR = Path(__file__).resolve().parent.parent
    DATOS_BASE = PROGRAMA_DIR

DATOS_DIR = DATOS_BASE / "datos"
REPORTES_DIR = DATOS_BASE / "reportes"
RESPALDOS_DIR = DATOS_BASE / "respaldos"
# Logo e iconos viajan con el programa. En el .exe, PyInstaller los deja
# dentro de su carpeta interna (_MEIPASS).
if getattr(sys, "frozen", False):
    RECURSOS_DIR = Path(getattr(sys, "_MEIPASS", PROGRAMA_DIR)) / "recursos"
else:
    RECURSOS_DIR = PROGRAMA_DIR / "recursos"

# Toda la información del negocio vive en este único archivo.
DB_PATH = DATOS_DIR / "la_feria.db"

NOMBRE_TIENDA = "LA FERIA"
MONEDA = "S/"
STOCK_MINIMO_DEFECTO = 12