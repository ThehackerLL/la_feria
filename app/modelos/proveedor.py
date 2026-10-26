"""Modelo de proveedor."""
from dataclasses import dataclass


@dataclass
class Proveedor:
    id: int
    nombre: str
    telefono: str = ""
    direccion: str = ""
    vende: str = ""          # lo que nos provee (por ejemplo "polos y camisas")
    activo: int = 1
    creado: str = ""