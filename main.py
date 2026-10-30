"""Punto de entrada de La Feria (sistema de inventario y ventas)."""
from app.base_datos.esquema import crear_tablas


def main():
    crear_tablas()
    # Se importa aquí para no cargar la interfaz si algo falla antes.
    from app.interfaz.pantallas.login import VentanaIngreso
    from app.interfaz.ventana_principal import VentanaPrincipal
    from app.servicios import seguridad

    while True:
        ingreso = VentanaIngreso()          # siempre pide usuario y contraseña
        ingreso.mainloop()
        if not ingreso.entro:               # cerró la ventana: no se abre nada
            break
        principal = VentanaPrincipal()
        principal.mainloop()
        seguridad.cerrar_sesion()
        if not principal.cerro_sesion:      # cerró el programa
            break


if __name__ == "__main__":
    main()