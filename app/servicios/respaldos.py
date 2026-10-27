"""Respaldos de la base de datos (la copia de seguridad del negocio).

- Se copian con el propio SQLite (backup), que es seguro aunque el programa
  esté abierto: nunca queda una copia a medias.
- Nombre: la_feria_2026-10-25_20-31-05_auto.db  (auto, manual o previo).
- Se guardan en la carpeta «respaldos»; solo se conservan los últimos 30.
- Copia extra (opcional): una segunda carpeta, por ejemplo Google Drive o un
  USB. Si no está disponible, el respaldo normal igual se hace y se avisa.
- Restaurar: antes de reemplazar los datos se guarda un respaldo «previo».
"""
import json
import re
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app import config

MAXIMO = 30                      # respaldos que se conservan en cada carpeta
HORAS_ENTRE_AUTOMATICOS = 24     # al abrir: si no hay uno más reciente, se hace
AUTOMATICO, MANUAL, PREVIO = "auto", "manual", "previo"
NOMBRE_TIPO = {AUTOMATICO: "Automático", MANUAL: "Manual",
               PREVIO: "Antes de restaurar"}

_PATRON = re.compile(
    r"^la_feria_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})_(auto|manual|previo)\.db$")


# ------------------------------------------------------------------ ajustes
def _archivo_ajustes():
    # Fuera de la base de datos, para que restaurar no lo cambie.
    return config.DATOS_BASE / "ajustes.json"


def leer_ajustes():
    try:
        return json.loads(_archivo_ajustes().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_ajustes(ajustes):
    _archivo_ajustes().parent.mkdir(parents=True, exist_ok=True)
    _archivo_ajustes().write_text(
        json.dumps(ajustes, ensure_ascii=False, indent=2), encoding="utf-8")


def carpeta_extra():
    """Carpeta de la copia extra (Path), o None si no hay."""
    texto = leer_ajustes().get("respaldo_extra", "")
    return Path(texto) if texto else None


def poner_carpeta_extra(carpeta):
    """Guarda la carpeta de la copia extra. None o '' la quita."""
    ajustes = leer_ajustes()
    if carpeta:
        ajustes["respaldo_extra"] = str(carpeta)
    else:
        ajustes.pop("respaldo_extra", None)
    _guardar_ajustes(ajustes)


def carpeta_excel():
    """Carpeta donde se copia también cada Excel de reportes (Path), o None."""
    texto = leer_ajustes().get("excel_extra", "")
    return Path(texto) if texto else None


def poner_carpeta_excel(carpeta):
    """Guarda la carpeta de los Excel. None o '' la quita."""
    ajustes = leer_ajustes()
    if carpeta:
        ajustes["excel_extra"] = str(carpeta)
    else:
        ajustes.pop("excel_extra", None)
    _guardar_ajustes(ajustes)


# ----------------------------------------------------------------- listado
def _leer_nombre(ruta):
    """(fecha, tipo) según el nombre del archivo, o None si no es un respaldo."""
    m = _PATRON.match(ruta.name)
    if not m:
        return None
    fecha = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H-%M-%S")
    return fecha, m.group(3)


def listar(carpeta=None):
    """Respaldos de una carpeta (por defecto la local), del más nuevo al más viejo."""
    carpeta = Path(carpeta) if carpeta else config.RESPALDOS_DIR
    if not carpeta.exists():
        return []
    lista = []
    for ruta in carpeta.iterdir():
        leido = _leer_nombre(ruta)
        if leido:
            lista.append({"ruta": ruta, "nombre": ruta.name, "fecha": leido[0],
                          "tipo": leido[1], "tamano": ruta.stat().st_size})
    return sorted(lista, key=lambda r: r["fecha"], reverse=True)


def ultimo():
    """El respaldo local más reciente (dict) o None."""
    lista = listar()
    return lista[0] if lista else None


def datos_cambiaron_desde_el_ultimo():
    """True si la base de datos se modificó después del último respaldo."""
    if not config.DB_PATH.exists():
        return False
    anterior = ultimo()
    if anterior is None:
        return True
    # Se compara con la hora real del archivo de respaldo (el nombre solo
    # llega hasta los segundos).
    return config.DB_PATH.stat().st_mtime > anterior["ruta"].stat().st_mtime


# ----------------------------------------------------------------- crear
def _comprobar(ruta):
    """Abre la copia y verifica que no esté dañada."""
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        resultado = con.execute("PRAGMA integrity_check").fetchone()[0]
        tablas = {f[0] for f in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        con.close()
    if resultado != "ok":
        raise ValueError("el archivo está dañado")
    if "productos" not in tablas or "ventas" not in tablas:
        raise ValueError("no es un respaldo de La Feria")


def _limpiar(carpeta):
    for viejo in listar(carpeta)[MAXIMO:]:
        try:
            viejo["ruta"].unlink()
        except OSError:
            pass


def crear(tipo=MANUAL, ahora=None):
    """Hace un respaldo ahora mismo.

    Devuelve {"ruta": Path, "extra": estado, "extra_carpeta": Path|None}.
    estado de la copia extra: "no_hay" (no configurada), "ok" o "error".
    Si no se puede ni el respaldo local, lanza ValueError con el motivo.
    """
    if not config.DB_PATH.exists():
        raise ValueError("Todavía no hay datos que respaldar.")
    ahora = ahora or datetime.now()
    config.RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
    nombre = f"la_feria_{ahora:%Y-%m-%d_%H-%M-%S}_{tipo}.db"
    destino = config.RESPALDOS_DIR / nombre
    origen = sqlite3.connect(config.DB_PATH)
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
    except (sqlite3.Error, OSError) as error:
        copia.close()
        origen.close()
        destino.unlink(missing_ok=True)
        raise ValueError(f"No se pudo hacer el respaldo: {error}")
    copia.close()
    origen.close()
    try:
        _comprobar(destino)
    except (sqlite3.Error, ValueError) as error:
        destino.unlink(missing_ok=True)
        raise ValueError(f"El respaldo salió dañado y se descartó ({error}).")
    _limpiar(config.RESPALDOS_DIR)

    extra, estado = carpeta_extra(), "no_hay"
    if extra is not None:
        try:
            if not extra.exists():
                raise OSError("la carpeta no está disponible")
            shutil.copy2(destino, extra / nombre)
            _limpiar(extra)
            estado = "ok"
        except OSError:
            estado = "error"
    return {"ruta": destino, "extra": estado, "extra_carpeta": extra}


def respaldar_si_toca(ahora=None):
    """Al abrir el programa: respalda si no hay uno de las últimas 24 horas.

    Cubre el caso de una PC que se apaga sin cerrar el programa.
    Devuelve el resultado de crear(), o None si no hacía falta.
    """
    if not config.DB_PATH.exists():
        return None
    ahora = ahora or datetime.now()
    anterior = ultimo()
    if anterior and ahora - anterior["fecha"] < timedelta(hours=HORAS_ENTRE_AUTOMATICOS):
        return None
    return crear(AUTOMATICO, ahora)


def respaldar_al_cerrar():
    """Al cerrar el programa: respalda solo si los datos cambiaron."""
    if not datos_cambiaron_desde_el_ultimo():
        return None
    return crear(AUTOMATICO)


# --------------------------------------------------------------- restaurar
def restaurar(ruta):
    """Reemplaza los datos actuales por los de un respaldo.

    Antes guarda un respaldo «previo» de lo que hay, por si te arrepientes.
    El programa debe reiniciarse después para cargar los datos.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise ValueError("No se encontró ese archivo.")
    try:
        _comprobar(ruta)
    except (sqlite3.Error, ValueError) as error:
        raise ValueError(f"Ese archivo no sirve para restaurar: {error}.")
    if config.DB_PATH.exists():
        crear(PREVIO)
    config.DATOS_DIR.mkdir(parents=True, exist_ok=True)
    origen = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    destino = sqlite3.connect(config.DB_PATH)
    try:
        origen.backup(destino)
    except (sqlite3.Error, OSError) as error:
        raise ValueError(f"No se pudo restaurar: {error}")
    finally:
        destino.close()
        origen.close()