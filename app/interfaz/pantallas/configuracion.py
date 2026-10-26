"""Pantalla Configuración: por ahora, los respaldos de la información.

El programa respalda solo (al abrir si pasó un día, y al cerrar si hubo
cambios). Aquí se puede respaldar a mano, ver los respaldos guardados,
elegir una carpeta para una copia extra (Google Drive, USB) y restaurar.
Más adelante aquí irán también la contraseña y los datos de la tienda.
"""
import os
from datetime import date, datetime
from tkinter import filedialog

import customtkinter as ctk

from app import config
from app.interfaz import estilos as e
from app.interfaz.componentes import Alerta, Tabla, aviso, boton, confirmar
from app.servicios import respaldos

COLUMNAS = [
    ("fecha", "Fecha y hora", 190, "w"),
    ("tipo", "Tipo", 170, "w", True),
    ("tamano", "Tamaño", 100, "e"),
]
DIAS_AVISO = 3        # más de estos días sin respaldo se ve en ámbar


def _fecha_texto(dt):
    hoy = date.today()
    if dt.date() == hoy:
        return f"hoy a las {dt:%H:%M}"
    if (hoy - dt.date()).days == 1:
        return f"ayer a las {dt:%H:%M}"
    return f"{dt:%d/%m/%Y} a las {dt:%H:%M}"


def _tamano_texto(bytes_):
    return (f"{bytes_ / 1024:.0f} KB" if bytes_ < 1024 * 1024
            else f"{bytes_ / 1024 / 1024:.1f} MB")


class PantallaConfiguracion(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._lista = []           # respaldos que se ven en la tabla
        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")
        self._crear_respaldos()

    # --------------------------------------------------------------- armado
    def _crear_respaldos(self):
        panel = ctk.CTkFrame(self, border_width=1, border_color=e.COLOR_BORDE)
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Respaldos", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 2))
        ctk.CTkLabel(panel, anchor="w", justify="left", wraplength=760,
                     text_color=e.COLOR_TEXTO_SUAVE,
                     text="Una copia de seguridad de todo: productos, ventas, "
                          "clientes y deudas. El programa la hace solo; si algún "
                          "día se daña la PC, desde aquí se recupera."
                     ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self._estado = ctk.CTkLabel(panel, text="", anchor="w",
                                    font=ctk.CTkFont(weight="bold"))
        self._estado.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 0))

        extra = ctk.CTkFrame(panel, fg_color="transparent")
        extra.grid(row=3, column=0, sticky="ew", padx=16, pady=(8, 0))
        extra.grid_columnconfigure(0, weight=1)
        self._texto_extra = ctk.CTkLabel(extra, text="", anchor="w",
                                         justify="left", wraplength=520)
        self._texto_extra.grid(row=0, column=0, sticky="ew")
        boton(extra, "Elegir carpeta…", self._elegir_extra, "secundario",
              ancho=140).grid(row=0, column=1, padx=(8, 0))
        self._quitar_extra = boton(extra, "Quitar", self._quitar_extra_accion,
                                   "secundario", ancho=80)
        self._quitar_extra.grid(row=0, column=2, padx=(8, 0))

        acciones = ctk.CTkFrame(panel, fg_color="transparent")
        acciones.grid(row=4, column=0, sticky="ew", padx=16, pady=(14, 8))
        boton(acciones, "Respaldar ahora", self._respaldar_ahora, "principal",
              ancho=160).pack(side="left")
        boton(acciones, "Abrir carpeta", self._abrir_carpeta, "secundario",
              ancho=130).pack(side="left", padx=8)
        boton(acciones, "Restaurar desde otro archivo…", self._restaurar_archivo,
              "secundario", ancho=230).pack(side="left")

        ctk.CTkLabel(panel, text="Respaldos guardados en esta PC", anchor="w",
                     font=ctk.CTkFont(weight="bold")
                     ).grid(row=5, column=0, sticky="ew", padx=16, pady=(8, 4))
        self._tabla = Tabla(panel, COLUMNAS, alto=7)
        self._tabla.grid(row=6, column=0, sticky="ew", padx=16)
        self._tabla.al_elegir(lambda _id: self._boton_restaurar.configure(
            state="normal"))
        self._boton_restaurar = boton(panel, "Restaurar el elegido",
                                      self._restaurar_elegido, "peligro",
                                      ancho=190)
        self._boton_restaurar.grid(row=7, column=0, sticky="w", padx=16,
                                   pady=(10, 16))
        self._boton_restaurar.configure(state="disabled")

    # ------------------------------------------------------------- mostrar
    def refrescar(self):
        """Se llama al abrir la pestaña."""
        self._lista = respaldos.listar()
        self._tabla.cargar([
            (i, (_fecha_texto(r["fecha"]).capitalize(),
                 respaldos.NOMBRE_TIPO[r["tipo"]], _tamano_texto(r["tamano"])), "")
            for i, r in enumerate(self._lista)])
        self._boton_restaurar.configure(state="disabled")

        if not self._lista:
            self._estado.configure(
                text="Todavía no hay respaldos. Pulsa «Respaldar ahora».",
                text_color=e.COLOR_PELIGRO)
        else:
            reciente = self._lista[0]
            dias = (datetime.now() - reciente["fecha"]).days
            self._estado.configure(
                text=f"Último respaldo: {_fecha_texto(reciente['fecha'])} "
                     f"({respaldos.NOMBRE_TIPO[reciente['tipo']].lower()})",
                text_color=e.COLOR_OK if dias <= DIAS_AVISO else e.COLOR_AVISO)

        carpeta = respaldos.carpeta_extra()
        if carpeta is None:
            self._texto_extra.configure(
                text="Copia extra: ninguna. Puedes elegir una carpeta de Google "
                     "Drive o un USB para tener una segunda copia fuera de la PC.",
                text_color=e.COLOR_TEXTO_SUAVE)
            self._quitar_extra.configure(state="disabled")
        else:
            disponible = carpeta.exists()
            self._texto_extra.configure(
                text=f"Copia extra: {carpeta}\n" +
                     ("Disponible." if disponible else
                      "No disponible ahora (¿está conectado el USB?)."),
                text_color=e.COLOR_TEXTO if disponible else e.COLOR_AVISO)
            self._quitar_extra.configure(state="normal")

    # ------------------------------------------------------------- acciones
    def _respaldar_ahora(self):
        try:
            resultado = respaldos.crear(respaldos.MANUAL)
        except (ValueError, OSError) as error:
            self.alerta.mostrar(str(error), "error")
            return
        self.refrescar()
        if resultado["extra"] == "error":
            self.alerta.mostrar(
                "Respaldo hecho en esta PC, pero NO se pudo copiar a "
                f"{resultado['extra_carpeta']}. ¿Está conectado el USB?",
                "aviso", segundos=10)
        elif resultado["extra"] == "ok":
            self.alerta.mostrar("Respaldo hecho y copiado también a la copia "
                                "extra.", "ok")
        else:
            self.alerta.mostrar("Respaldo hecho.", "ok")

    def _elegir_extra(self):
        carpeta = filedialog.askdirectory(
            parent=self.winfo_toplevel(),
            title="Carpeta para la copia extra (Google Drive, USB…)")
        if not carpeta:
            return
        try:
            respaldos.poner_carpeta_extra(carpeta)
        except OSError as error:
            self.alerta.mostrar(f"No se pudo guardar la carpeta: {error}", "error")
            return
        self.refrescar()
        self.alerta.mostrar("Listo. Desde ahora cada respaldo se copia también "
                            "ahí.", "ok")

    def _quitar_extra_accion(self):
        respaldos.poner_carpeta_extra(None)
        self.refrescar()
        self.alerta.mostrar("Ya no se hace copia extra. Los respaldos ya "
                            "copiados no se borran.", "ok")

    def _abrir_carpeta(self):
        try:
            config.RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(config.RESPALDOS_DIR)
        except (AttributeError, OSError):
            self.alerta.mostrar(f"La carpeta está en: {config.RESPALDOS_DIR}",
                                "aviso", segundos=10)

    def _restaurar_elegido(self):
        elegido = self._tabla.seleccionado()
        if elegido is None:
            return
        r = self._lista[int(elegido)]
        self._restaurar(r["ruta"], f"del {_fecha_texto(r['fecha'])}")

    def _restaurar_archivo(self):
        inicio = respaldos.carpeta_extra()
        ruta = filedialog.askopenfilename(
            parent=self.winfo_toplevel(), title="Elige el respaldo a restaurar",
            initialdir=str(inicio if inicio and inicio.exists()
                           else config.RESPALDOS_DIR),
            filetypes=[("Respaldo de La Feria", "*.db"), ("Todos", "*.*")])
        if ruta:
            self._restaurar(ruta, "del archivo elegido")

    def _restaurar(self, ruta, descripcion):
        if not confirmar(
                self, "Restaurar respaldo",
                f"Se reemplazarán TODOS los datos actuales (inventario, ventas, "
                f"clientes, deudas) por los {descripcion}.\n\n"
                "Antes se guarda un respaldo de lo que hay ahora, por si te "
                "arrepientes.\n\nEl programa se cerrará y tendrás que abrirlo "
                "otra vez.", texto_si="Restaurar", peligro=True):
            return
        try:
            respaldos.restaurar(ruta)
        except (ValueError, OSError) as error:
            self.alerta.mostrar(str(error), "error")
            return
        aviso(self, "Respaldo restaurado",
              "Listo. El programa se cerrará; ábrelo otra vez para ver los "
              "datos restaurados.")
        self.winfo_toplevel().destroy()