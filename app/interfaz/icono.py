"""Icono del programa para las ventanas (barra de título y barra de tareas)."""
from app import config


def poner_icono(ventana):
    """Pone recursos/icono.ico a la ventana. Si falta el archivo, no pasa nada."""
    ruta = config.RECURSOS_DIR / "icono.ico"
    if not ruta.exists():
        return
    try:
        ventana.iconbitmap(str(ruta))
        # CustomTkinter pone su icono propio a los 200 ms; lo reponemos después.
        ventana.after(300, lambda: _reponer(ventana, ruta))
    except Exception:
        pass


def _reponer(ventana, ruta):
    try:
        if ventana.winfo_exists():
            ventana.iconbitmap(str(ruta))
    except Exception:
        pass