"""Modelo de cliente."""
from dataclasses import dataclass


@dataclass
class Cliente:
    id: int
    nombre: str
    telefono: str = ""
    activo: int = 1
    creado: str = ""
    dni: str = ""            # opcional (8 dígitos)
    direccion: str = ""      # opcional