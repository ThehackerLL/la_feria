"""Punto de entrada de La Feria (sistema de inventario y ventas)."""
from app.base_datos.esquema import crear_tablas


def main():
    crear_tablas()
    # Se importa aquí para no cargar la interfaz si algo falla antes.
    from app.interfaz.ventana_principal import VentanaPrincipal
    VentanaPrincipal().mainloop()


if __name__ == "__main__":
    main()