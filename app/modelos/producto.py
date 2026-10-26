"""Modelo de producto."""
from dataclasses import dataclass


@dataclass
class Producto:
    id: int
    codigo: str
    categoria: str
    nombre: str
    costo: float
    precio_unidad: float
    precio_mayor: float
    stock: int
    stock_minimo: int
    activo: int = 1
    creado: str = ""

    @property
    def valor_stock(self):
        """Valor del stock = stock x costo."""
        return round(self.stock * self.costo, 2)

    @property
    def bajo_stock(self):
        """True si el stock llegó al mínimo o por debajo."""
        return self.stock <= self.stock_minimo