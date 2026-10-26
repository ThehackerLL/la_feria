"""Formato de números para mostrar en pantalla."""
from app import config


def moneda(valor):
    """1234.5 -> 'S/ 1,234.50'"""
    return f"{config.MONEDA} {valor:,.2f}"


def entero(valor):
    """1234 -> '1,234'"""
    return f"{int(valor):,}"