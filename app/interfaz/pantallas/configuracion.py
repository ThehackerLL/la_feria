"""Pantalla Configuración: usuarios y contraseñas, respaldos y carpeta de los Excel.

El programa respalda solo (al abrir si pasó un día, y al cerrar si hubo
cambios). Aquí se puede respaldar a mano, ver los respaldos guardados,
elegir una carpeta para una copia extra (Google Drive, USB) y restaurar.
También se elige la carpeta (p. ej. de Google Drive) donde se copia cada Excel
de reportes, para verlo desde el celular.
Datos de la tienda: el nombre que se ve en el programa y en los Excel (cambiarlo
pide la contraseña del dueño).
Usuarios y contraseñas: crear y quitar usuarios y cambiar contraseñas (casi todo
pide la contraseña del dueño).
"""
import os
from datetime import date, datetime
from tkinter import filedialog

import customtkinter as ctk

from app import config
from app.interfaz import estilos as e
from app.interfaz.componentes import Alerta, Tabla, aviso, boton, confirmar
from app.interfaz.dialogo_formulario import pedir_formulario
from app.servicios import respaldos, seguridad, tienda

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
        # Con scroll: en ventanas bajas todas las secciones siguen alcanzables.
        self._cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._cuerpo.pack(fill="both", expand=True)
        self._crear_tienda()
        self._crear_usuarios()
        self._crear_respaldos()
        self._crear_excel()

    # --------------------------------------------------------------- armado
    def _crear_tienda(self):
        panel = ctk.CTkFrame(self._cuerpo, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.pack(fill="x", pady=(0, e.ESPACIO))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Datos de la tienda", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, sticky="ew",
                            padx=16, pady=(14, 2))
        ctk.CTkLabel(panel, anchor="w", justify="left", wraplength=760,
                     text_color=e.COLOR_TEXTO_SUAVE,
                     text="El nombre se ve arriba en el programa, en la ventana "
                          "de ingreso y en los Excel."
                     ).grid(row=1, column=0, columnspan=2, sticky="ew",
                            padx=16, pady=(0, 8))
        self._nombre_tienda = ctk.CTkLabel(
            panel, text="", anchor="w", font=ctk.CTkFont(weight="bold"))
        self._nombre_tienda.grid(row=2, column=0, sticky="ew", padx=16,
                                 pady=(0, 16))
        boton(panel, "Cambiar nombre", self._cambiar_nombre_tienda,
              "secundario", ancho=160).grid(row=2, column=1, padx=(8, 16),
                                            pady=(0, 16))

    def _cambiar_nombre_tienda(self):
        def accion(v):
            seguridad.comprobar_clave_dueno(v["dueno"])
            tienda.guardar_nombre(v["nombre"])
        if pedir_formulario(
                self, "Nombre de la tienda",
                [("nombre", "Nombre de la tienda", False),
                 ("dueno", "Contraseña del dueño", True)],
                "Guardar", accion):
            self._cargar_tienda()
            ventana = self.winfo_toplevel()
            if hasattr(ventana, "actualizar_nombre"):
                ventana.actualizar_nombre()
            self.alerta.mostrar("El nombre de la tienda se guardó.", "ok")

    def _cargar_tienda(self):
        self._nombre_tienda.configure(text=f"Nombre de la tienda:  {tienda.nombre()}")

    def _crear_usuarios(self):
        panel = ctk.CTkFrame(self._cuerpo, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.pack(fill="x", pady=(0, e.ESPACIO))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Usuarios y contraseñas", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, sticky="ew",
                            padx=16, pady=(14, 2))
        ctk.CTkLabel(panel, anchor="w", justify="left", wraplength=760,
                     text_color=e.COLOR_TEXTO_SUAVE,
                     text="Cada persona que vende entra con su usuario y su "
                          "contraseña; su nombre queda anotado en lo que registra. "
                          "La contraseña del dueño es otra y sirve para la "
                          "ganancia, Inventario, Compras, Huella digital y el "
                          "Excel. Crear o quitar usuarios también la pide."
                     ).grid(row=1, column=0, columnspan=2, sticky="ew",
                            padx=16, pady=(0, 8))
        self._t_usuarios = Tabla(panel, [("nombre", "Usuario", 300, "w", True),
                                         ("estado", "", 120, "w")], alto=4)
        for hijo in self._t_usuarios.winfo_children():
            if isinstance(hijo, ctk.CTkScrollbar):
                hijo.configure(height=60)
        self._t_usuarios.grid(row=2, column=0, columnspan=2, sticky="ew",
                              padx=16, pady=(0, 8))
        fila = ctk.CTkFrame(panel, fg_color="transparent")
        fila.grid(row=3, column=0, columnspan=2, sticky="w", padx=16,
                  pady=(0, 6))
        boton(fila, "Nuevo usuario", self._nuevo_usuario, "principal",
              ancho=140).pack(side="left", padx=(0, 8))
        boton(fila, "Quitar usuario", self._quitar_usuario, "peligro",
              ancho=140).pack(side="left", padx=(0, 8))
        boton(fila, "Contraseña nueva para el usuario",
              self._clave_a_usuario, "secundario",
              ancho=230).pack(side="left")
        fila2 = ctk.CTkFrame(panel, fg_color="transparent")
        fila2.grid(row=4, column=0, columnspan=2, sticky="w", padx=16,
                   pady=(0, 16))
        boton(fila2, "Cambiar mi contraseña", self._cambiar_mi_clave,
              "secundario", ancho=190).pack(side="left", padx=(0, 8))
        boton(fila2, "Cambiar contraseña del dueño", self._cambiar_clave_dueno,
              "secundario", ancho=230).pack(side="left")

    def _crear_respaldos(self):
        panel = ctk.CTkFrame(self._cuerpo, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.pack(fill="x")
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

    def _crear_excel(self):
        panel = ctk.CTkFrame(self._cuerpo, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.pack(fill="x", pady=(e.ESPACIO, 0))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Excel de reportes", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, columnspan=3, sticky="ew",
                            padx=16, pady=(14, 2))
        ctk.CTkLabel(panel, anchor="w", justify="left", wraplength=760,
                     text_color=e.COLOR_TEXTO_SUAVE,
                     text="Cada Excel que exportes en Reportes se guarda directo "
                          "en la carpeta que elijas (por ejemplo una de Google "
                          "Drive), sin dejar copia en esta PC, y así lo ves desde "
                          "el celular. Si Drive no está disponible, se guarda en "
                          "la PC. Ojo: el Excel lleva la ganancia de cada producto "
                          "elige una carpeta que solo vean personas de confianza."
                     ).grid(row=1, column=0, columnspan=3, sticky="ew",
                            padx=16, pady=(0, 8))
        self._texto_excel = ctk.CTkLabel(panel, text="", anchor="w",
                                         justify="left", wraplength=520)
        self._texto_excel.grid(row=2, column=0, sticky="ew", padx=16,
                               pady=(0, 16))
        boton(panel, "Elegir carpeta…", self._elegir_excel, "secundario",
              ancho=140).grid(row=2, column=1, padx=(8, 0), pady=(0, 16))
        self._quitar_excel = boton(panel, "Quitar", self._quitar_excel_accion,
                                   "secundario", ancho=80)
        self._quitar_excel.grid(row=2, column=2, padx=(8, 16), pady=(0, 16))

    # ------------------------------------------------------ usuarios y claves
    def _cargar_usuarios(self):
        yo = seguridad.nombre_usuario()
        self._usuarios = seguridad.listar_usuarios()
        self._t_usuarios.cargar([
            (u["id"], (u["nombre"], "(tú)" if u["nombre"] == yo else ""), "")
            for u in self._usuarios])

    def _usuario_elegido(self):
        elegido = self._t_usuarios.seleccionado()
        if elegido is None:
            self.alerta.mostrar("Primero elige un usuario de la lista.", "aviso")
            return None
        return next((u for u in self._usuarios if str(u["id"]) == str(elegido)),
                    None)

    @staticmethod
    def _iguales(a, b):
        if a != b:
            raise ValueError("Las dos contraseñas nuevas no son iguales.")

    def _nuevo_usuario(self):
        def accion(v):
            seguridad.comprobar_clave_dueno(v["dueno"])
            self._iguales(v["clave"], v["repetir"])
            self._nombre_creado = seguridad.formato_nombre(v["nombre"])
            seguridad.crear_usuario(v["nombre"], v["clave"])
        if pedir_formulario(
                self, "Nuevo usuario",
                [("nombre", "Nombre de la persona (ej.: Marta)", False),
                 ("clave", "Contraseña del usuario", True),
                 ("repetir", "Repite la contraseña", True),
                 ("dueno", "Contraseña del dueño", True)],
                "Crear usuario", accion,
                texto="El usuario se llamará Analista-Nombre."):
            self._cargar_usuarios()
            self.alerta.mostrar(f"Usuario {self._nombre_creado} creado.", "ok")

    def _quitar_usuario(self):
        u = self._usuario_elegido()
        if u is None:
            return
        def accion(v):
            seguridad.comprobar_clave_dueno(v["dueno"])
            seguridad.quitar_usuario(u["id"])
        if pedir_formulario(
                self, "Quitar usuario", [("dueno", "Contraseña del dueño", True)],
                "Quitar", accion, peligro=True,
                texto=f"Se quitará a {u['nombre']}. Lo que ya registró conserva "
                      "su nombre."):
            self._cargar_usuarios()
            self.alerta.mostrar(f"Usuario {u['nombre']} quitado.", "ok")

    def _clave_a_usuario(self):
        u = self._usuario_elegido()
        if u is None:
            return
        def accion(v):
            seguridad.comprobar_clave_dueno(v["dueno"])
            self._iguales(v["clave"], v["repetir"])
            seguridad.poner_clave_usuario(u["id"], v["clave"])
        if pedir_formulario(
                self, "Contraseña nueva",
                [("clave", f"Contraseña nueva para {u['nombre']}", True),
                 ("repetir", "Repite la contraseña", True),
                 ("dueno", "Contraseña del dueño", True)],
                "Guardar", accion,
                texto="Sirve cuando el usuario olvidó la suya."):
            self.alerta.mostrar(f"Contraseña de {u['nombre']} cambiada.", "ok")

    def _cambiar_mi_clave(self):
        def accion(v):
            self._iguales(v["clave"], v["repetir"])
            seguridad.cambiar_clave_usuario(seguridad.nombre_usuario(),
                                            v["actual"], v["clave"])
        if pedir_formulario(
                self, "Cambiar mi contraseña",
                [("actual", "Contraseña actual", True),
                 ("clave", "Contraseña nueva", True),
                 ("repetir", "Repite la contraseña nueva", True)],
                "Cambiar", accion,
                texto=f"Usuario: {seguridad.nombre_usuario()}"):
            self.alerta.mostrar("Tu contraseña se cambió.", "ok")

    def _cambiar_clave_dueno(self):
        def accion(v):
            self._iguales(v["clave"], v["repetir"])
            seguridad.cambiar_clave_dueno(v["actual"], v["clave"])
        if pedir_formulario(
                self, "Cambiar contraseña del dueño",
                [("actual", "Contraseña actual del dueño", True),
                 ("clave", "Contraseña nueva del dueño", True),
                 ("repetir", "Repite la contraseña nueva", True)],
                "Cambiar", accion,
                texto="Esta es la que protege la ganancia, Inventario, Compras, "
                      "Huella digital y el Excel."):
            self.alerta.mostrar("La contraseña del dueño se cambió.", "ok")

    # ------------------------------------------------------------- mostrar
    def refrescar(self):
        """Se llama al abrir la pestaña."""
        self._cargar_tienda()
        self._cargar_usuarios()
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

        carpeta = respaldos.carpeta_excel()
        if carpeta is None:
            self._texto_excel.configure(
                text="Carpeta de los Excel: ninguna (se guardan en esta PC, "
                     "en la carpeta «reportes»).",
                text_color=e.COLOR_TEXTO_SUAVE)
            self._quitar_excel.configure(state="disabled")
        else:
            disponible = carpeta.exists()
            self._texto_excel.configure(
                text=f"Carpeta de los Excel: {carpeta}\n" +
                     ("Disponible." if disponible else
                      "No disponible ahora (¿está abierto Google Drive?). "
                      "Mientras tanto los Excel se guardan en la PC."),
                text_color=e.COLOR_TEXTO if disponible else e.COLOR_AVISO)
            self._quitar_excel.configure(state="normal")

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

    def _elegir_excel(self):
        carpeta = filedialog.askdirectory(
            parent=self.winfo_toplevel(),
            title="Carpeta para los Excel de reportes (Google Drive…)")
        if not carpeta:
            return
        try:
            respaldos.poner_carpeta_excel(carpeta)
        except OSError as error:
            self.alerta.mostrar(f"No se pudo guardar la carpeta: {error}", "error")
            return
        self.refrescar()
        self.alerta.mostrar("Listo. Desde ahora cada Excel que exportes se "
                            "guardará ahí.", "ok")

    def _quitar_excel_accion(self):
        respaldos.poner_carpeta_excel(None)
        self.refrescar()
        self.alerta.mostrar("Los Excel volverán a guardarse en la carpeta "
                            "«reportes» de esta PC. Los que ya estaban en la otra "
                            "carpeta no se borran.", "ok")

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