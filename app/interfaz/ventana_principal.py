"""Ventana principal: barra de pestañas arriba y la pantalla elegida debajo."""
import importlib
from datetime import date

import customtkinter as ctk

from app import config
from app.interfaz import estilos as e
from app.interfaz.componentes import _Dialogo, aviso, confirmar
from app.servicios import creditos, respaldos
from app.utilidades.formato import moneda

# (nombre en la pestaña, módulo, clase, etapa en que se construye)
# Una pantalla solo aparece cuando su archivo ya tiene la clase escrita.
PESTANAS = [
    ("Ventas", "ventas", "PantallaVentas", "Etapa 2"),
    ("Inventario", "productos", "PantallaProductos", "Etapa 1"),
    ("Compras", "compras", "PantallaCompras", "Etapa 1"),
    ("Crédito", "creditos", "PantallaCreditos", "Etapa 5"),
    ("Proveedores", "proveedores", "PantallaProveedores", "Etapa 1"),
    ("Envíos", "envios", "PantallaEnvios", "Etapa 5"),
    ("Caja y reportes", "caja", "PantallaCaja", "Etapa 4"),
    ("Clientes", "clientes", "PantallaClientes", "Etapa 5"),
    ("Configuración", "configuracion", "PantallaConfiguracion", "Etapa 6"),
]
PESTANA_INICIAL = "Ventas"       # la pestaña que se ve al abrir el programa

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _cargar_clase(modulo, clase):
    """Devuelve la clase de la pantalla, o None si todavía no está escrita."""
    ruta = f"app.interfaz.pantallas.{modulo}"
    try:
        return getattr(importlib.import_module(ruta), clase, None)
    except ModuleNotFoundError as error:
        if error.name == ruta:
            return None
        raise


class Proximamente(ctk.CTkFrame):
    """Pantalla de relleno para lo que todavía no está construido."""

    def __init__(self, padre, nombre, etapa):
        super().__init__(padre, fg_color="transparent")
        centro = ctk.CTkFrame(self, border_width=1, border_color=e.COLOR_BORDE)
        centro.place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(centro, text=nombre,
                     font=ctk.CTkFont(size=e.TAM_TITULO, weight="bold")
                     ).pack(padx=48, pady=(28, 4))
        ctk.CTkLabel(centro, text=f"Próximamente ({etapa})",
                     text_color=e.COLOR_TEXTO_SUAVE
                     ).pack(padx=48, pady=(0, 28))


class VentanaPrincipal(ctk.CTk):
    def __init__(self):
        e.aplicar_tema()
        super().__init__()
        e.configurar_tabla()
        self.title(f"{config.NOMBRE_TIENDA} - Inventario y ventas")
        self.geometry("1240x760")
        self.minsize(1280, 680)

        self._botones = {}
        self._pantallas = {}
        self._activa = None

        self._crear_encabezado()
        self._zona = ctk.CTkFrame(self, fg_color="transparent")
        self._zona.pack(fill="both", expand=True, padx=e.MARGEN,
                        pady=(e.ESPACIO, e.MARGEN))
        self.mostrar(PESTANA_INICIAL)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.after(200, self._respaldo_al_abrir)
        self.after(400, self._avisar_vencidas)   # cuando la ventana ya se vio

    # ------------------------------------------------------------- encabezado
    def _crear_encabezado(self):
        barra = ctk.CTkFrame(self, corner_radius=0, fg_color=e.COLOR_TARJETA,
                             border_width=0)
        barra.pack(fill="x")
        ctk.CTkLabel(barra, text=config.NOMBRE_TIENDA, text_color=e.COLOR_PRIMARIO,
                     font=ctk.CTkFont(size=e.TAM_TITULO, weight="bold")
                     ).pack(side="left", padx=(e.MARGEN + 4, 28), pady=12)
        for nombre, *_ in PESTANAS:
            boton = ctk.CTkButton(
                barra, text=nombre, width=0, height=e.ALTO_CONTROL,
                fg_color="transparent", hover_color=e.COLOR_PESTANA_HOVER,
                text_color=e.COLOR_TEXTO_SUAVE,
                font=ctk.CTkFont(weight="bold"),
                command=lambda n=nombre: self.mostrar(n))
            boton.pack(side="left", padx=3, pady=12)
            self._botones[nombre] = boton
        hoy = date.today()
        ctk.CTkLabel(barra, text=f"{hoy.day} de {_MESES[hoy.month - 1]} de {hoy.year}",
                     text_color=e.COLOR_TEXTO_SUAVE
                     ).pack(side="right", padx=e.MARGEN + 4)
        # línea fina bajo la barra
        ctk.CTkFrame(self, height=1, corner_radius=0,
                     fg_color=e.COLOR_BORDE).pack(fill="x")

    # --------------------------------------------------------------- pestañas
    def mostrar(self, nombre):
        """Muestra la pantalla de la pestaña elegida (se crea la 1.ª vez)."""
        if nombre not in self._pantallas:
            self._pantallas[nombre] = self._crear_pantalla(nombre)
        if self._activa is not None:
            self._pantallas[self._activa].pack_forget()
        self._pantallas[nombre].pack(fill="both", expand=True)
        self._activa = nombre
        for n, boton in self._botones.items():
            activa = (n == nombre)
            boton.configure(
                fg_color=e.COLOR_PRIMARIO_SUAVE if activa else "transparent",
                text_color=e.COLOR_PRIMARIO if activa else e.COLOR_TEXTO_SUAVE)
        # Si la pantalla sabe refrescarse (p. ej. el stock cambió), lo hace.
        refrescar = getattr(self._pantallas[nombre], "refrescar", None)
        if callable(refrescar):
            refrescar()

    def _crear_pantalla(self, nombre):
        for titulo, modulo, clase, etapa in PESTANAS:
            if titulo == nombre:
                pantalla = _cargar_clase(modulo, clase)
                if pantalla is None:
                    return Proximamente(self._zona, nombre, etapa)
                return pantalla(self._zona)
        raise KeyError(nombre)

    # ---------------------------------------------------------------- respaldo
    def _respaldo_al_abrir(self):
        """Si pasó más de un día sin respaldo (p. ej. la PC se apagó sin cerrar
        el programa), lo hace ahora. Solo avisa si falla."""
        try:
            respaldos.respaldar_si_toca()
        except (ValueError, OSError) as error:
            aviso(self, "No se pudo respaldar",
                  f"{error}\n\nRevisa la pestaña Configuración.")

    # ---------------------------------------------------------- cuotas vencidas
    def _avisar_vencidas(self):
        """Al abrir el programa: avisa si hay cuotas de crédito vencidas."""
        resumen = creditos.resumen_creditos()
        cuotas, clientes = resumen["cuotas_vencidas"], resumen["clientes_vencidos"]
        if not cuotas:
            return
        texto = (f"Hay {cuotas} {'cuota vencida' if cuotas == 1 else 'cuotas vencidas'}"
                 f" de {clientes} {'cliente' if clientes == 1 else 'clientes'}"
                 f" por {moneda(resumen['vencido'])}.")
        dialogo = _Dialogo(self, "Cuotas vencidas", texto, [
            ("Más tarde", "secundario", False),
            ("Ver créditos", "principal", True)])
        self.wait_window(dialogo)
        if dialogo.resultado:
            self.mostrar("Crédito")

    # ----------------------------------------------------------------- cerrar
    def _cerrar(self):
        """Cierra el programa; si hay una venta sin terminar, avisa antes."""
        ventas = self._pantallas.get("Ventas")
        hay_pendientes = getattr(ventas, "tiene_pendientes", None)
        if callable(hay_pendientes) and hay_pendientes():
            if not confirmar(
                    self, "Hay una venta sin terminar",
                    "Hay una venta sin cobrar o ventas en espera. Si cierras "
                    "ahora se perderán.", texto_si="Cerrar", peligro=True):
                return
        self._respaldar_al_cerrar()
        self.destroy()

    def _respaldar_al_cerrar(self):
        """Respalda si hubo cambios. Nunca impide cerrar, pero avisa si algo falló."""
        try:
            resultado = respaldos.respaldar_al_cerrar()
        except (ValueError, OSError) as error:
            aviso(self, "No se pudo respaldar",
                  f"{error}\n\nEl programa se cerrará igual. Haz un respaldo "
                  "a mano en Configuración cuando puedas.")
            return
        if resultado and resultado["extra"] == "error":
            aviso(self, "Copia extra pendiente",
                  "El respaldo se guardó en esta PC, pero no se pudo copiar a:\n"
                  f"{resultado['extra_carpeta']}\n\n¿Está conectado el USB o "
                  "disponible la carpeta de Drive?")