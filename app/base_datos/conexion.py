"""Conexión a la base de datos SQLite."""
import sqlite3
from contextlib import contextmanager

from app import config


def conectar():
    """Abre una conexión nueva a la base de datos."""
    config.DATOS_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row          # permite fila["columna"]
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def transaccion():
    """Agrupa varias operaciones: o se guardan todas o no se guarda ninguna."""
    con = conectar()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()