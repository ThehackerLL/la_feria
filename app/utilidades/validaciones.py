"""Conversión y validación de lo que se escribe en los formularios."""
import re

# Número válido: dígitos, con punto decimal opcional y máximo 2 decimales.
_NUMERO = re.compile(r"-?(?:\d+(?:\.\d{1,2})?|\.\d{1,2})")


def a_numero(texto, campo="Valor", minimo=0.0):
    """Convierte texto a número. Vacío = 0.

    Formato: decimales con punto y como máximo 2 (12.50).
    Los miles se escriben sin punto ni coma (1200).
    """
    limpio = str(texto).strip()
    if limpio == "":
        valor = 0.0
    else:
        if "," in limpio:
            raise ValueError(f"{campo}: no uses comas. Decimales con punto "
                             "(12.50) y miles sin separador (1200).")
        if limpio.count(".") > 1 or re.fullmatch(r"-?\d+\.\d{3,}", limpio):
            raise ValueError(f"{campo}: '{texto}' tiene más de 2 decimales. "
                             "Los miles se escriben sin punto (1200).")
        if not _NUMERO.fullmatch(limpio):
            raise ValueError(f"{campo}: '{texto}' no es un número válido.")
        valor = float(limpio)
    if valor < minimo:
        raise ValueError(f"{campo} no puede ser menor que {minimo:g}.")
    return round(valor, 2)


def a_entero(texto, campo="Valor", minimo=0):
    """Convierte texto a número entero. Vacío = 0."""
    limpio = str(texto).strip()
    if limpio == "":
        valor = 0
    else:
        try:
            valor = int(limpio)
        except ValueError:
            raise ValueError(f"{campo}: '{texto}' debe ser un número entero.")
    if valor < minimo:
        raise ValueError(f"{campo} no puede ser menor que {minimo}.")
    return valor