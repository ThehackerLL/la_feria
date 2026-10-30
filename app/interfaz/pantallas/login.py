"""Ventana de ingreso: se abre SIEMPRE al iniciar el programa.

- Primera vez (todavía no hay usuarios): se crea el primer usuario, la
  contraseña del dueño (la de la ganancia) y se entrega la clave de recuperación.
- Después: usuario + contraseña. «Olvidé mi contraseña» usa la clave de
  recuperación.
Si se cierra la ventana sin entrar, el programa no se abre (entro = False).
"""
import customtkinter as ctk

from app import config
from app.interfaz import estilos as e
from app.interfaz.componentes import Campo, CampoLista, boton
from app.servicios import seguridad


def _centrar(ventana, padre=None):
    ventana.update_idletasks()
    ancho, alto = ventana.winfo_reqwidth(), ventana.winfo_reqheight()
    if padre is not None:
        raiz = padre.winfo_toplevel()
        x = raiz.winfo_rootx() + (raiz.winfo_width() - ancho) // 2
        y = raiz.winfo_rooty() + (raiz.winfo_height() - alto) // 2
    else:
        x = (ventana.winfo_screenwidth() - ancho) // 2
        y = (ventana.winfo_screenheight() - alto) // 3
    ventana.geometry(f"{ancho}x{alto}+{max(x, 0)}+{max(y, 0)}")


def _clave(campo):
    """Convierte un Campo en una caja de contraseña (puntos en vez de letras)."""
    campo.caja.configure(show="•")
    return campo


def _clave_exacta(campo):
    """La contraseña se toma tal cual (sin quitar espacios de los lados)."""
    return campo.caja.get()


class _DialogoClaveRecuperacion(ctk.CTkToplevel):
    """Muestra la clave de recuperación; no se puede cerrar sin confirmar."""

    def __init__(self, padre, clave, titulo="Guarda tu clave de recuperación"):
        super().__init__(padre)
        self.title("Clave de recuperación")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        self._clave = clave
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text=titulo, anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            cuerpo, anchor="w", justify="left", wraplength=400,
            text_color=e.COLOR_TEXTO_SUAVE,
            text="Esta clave sirve para poner una contraseña nueva si alguien "
                 "la olvida. Se muestra UNA sola vez: anótala en papel o "
                 "guárdala en un lugar seguro, y no la compartas con quien "
                 "vende."
        ).pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkLabel(cuerpo, text=clave, font=ctk.CTkFont(
            family="Consolas", size=24, weight="bold"),
            text_color=e.COLOR_PRIMARIO).pack(padx=18, pady=(0, 6))
        self._copiado = ctk.CTkLabel(cuerpo, text="", text_color=e.COLOR_OK)
        self._copiado.pack()
        boton(cuerpo, "Copiar", self._copiar, "secundario",
              ancho=110).pack(pady=(2, 10))
        self._ok = ctk.CTkCheckBox(cuerpo, text="Ya la guardé en un lugar seguro",
                                   command=self._cambio)
        self._ok.pack(anchor="w", padx=18, pady=(0, 10))
        self._seguir = boton(cuerpo, "Continuar", self.destroy, "principal",
                             ancho=140)
        self._seguir.pack(anchor="e", padx=18, pady=(0, 16))
        self._seguir.configure(state="disabled")
        self.protocol("WM_DELETE_WINDOW", lambda: None)   # no se cierra con la X
        _centrar(self, padre)
        self.transient(padre.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()
        self.focus_set()

    def _copiar(self):
        self.clipboard_clear()
        self.clipboard_append(self._clave)
        self._copiado.configure(text="Copiada")

    def _cambio(self):
        self._seguir.configure(state="normal" if self._ok.get() else "disabled")


class _DialogoRecuperar(ctk.CTkToplevel):
    """Poner una contraseña nueva con la clave de recuperación."""

    def __init__(self, padre):
        super().__init__(padre)
        self.title("Olvidé mi contraseña")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        self.exito = False
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text="Olvidé mi contraseña", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(cuerpo, anchor="w", justify="left", wraplength=380,
                     text_color=e.COLOR_TEXTO_SUAVE,
                     text="Necesitas la clave de recuperación que se entregó al "
                          "crear el programa."
                     ).pack(fill="x", padx=18, pady=(0, 10))
        self.recuperacion = Campo(cuerpo, "Clave de recuperación", ancho=380,
                                  ayuda="XXXX-XXXX-XXXX-XXXX")
        self.recuperacion.pack(fill="x", padx=18, pady=(0, 8))
        self.cual = ctk.CTkSegmentedButton(
            cuerpo, values=["Contraseña de usuario", "Contraseña del dueño"],
            command=self._cambiar_cual, height=e.ALTO_CONTROL)
        self.cual.set("Contraseña de usuario")
        self.cual.pack(fill="x", padx=18, pady=(0, 8))
        self.usuario = CampoLista(cuerpo, "Usuario",
                                  valores=[u["nombre"] for u in
                                           seguridad.listar_usuarios()],
                                  ancho=380)
        self.usuario.pack(fill="x", padx=18, pady=(0, 8))
        self.nueva = _clave(Campo(cuerpo, "Contraseña nueva", ancho=380))
        self.nueva.pack(fill="x", padx=18, pady=(0, 8))
        self.repetir = _clave(Campo(cuerpo, "Repite la contraseña nueva",
                                    ancho=380))
        self.repetir.pack(fill="x", padx=18, pady=(0, 6))
        self.error = ctk.CTkLabel(cuerpo, text="", anchor="w", justify="left",
                                  text_color=e.COLOR_PELIGRO, wraplength=380)
        self.error.pack(fill="x", padx=18)
        fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=(6, 16))
        boton(fila, "Cambiar contraseña", self._aceptar, "principal",
              ancho=170).pack(side="right", padx=(8, 0))
        boton(fila, "Cancelar", self.destroy, "secundario",
              ancho=110).pack(side="right")
        self.bind("<Escape>", lambda _ev: self.destroy())
        self.repetir.al_enter(self._aceptar)
        _centrar(self, padre)
        self.transient(padre.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()
        self.recuperacion.foco()

    def _cambiar_cual(self, valor):
        if valor == "Contraseña de usuario":
            self.usuario.pack(fill="x", padx=18, pady=(0, 8),
                              before=self.nueva)
        else:
            self.usuario.pack_forget()

    def _aceptar(self):
        nueva, repetir = _clave_exacta(self.nueva), _clave_exacta(self.repetir)
        if nueva != repetir:
            self.error.configure(text="Las dos contraseñas no son iguales.")
            return
        try:
            if self.cual.get() == "Contraseña de usuario":
                nueva_clave = seguridad.restablecer_clave_usuario(
                    self.usuario.obtener(), self.recuperacion.obtener(), nueva)
            else:
                nueva_clave = seguridad.restablecer_clave_dueno(
                    self.recuperacion.obtener(), nueva)
        except ValueError as error:
            self.error.configure(text=str(error))
            return
        self.exito = True
        self.grab_release()
        padre = self.master
        self.withdraw()
        espera = _DialogoClaveRecuperacion(
            padre, nueva_clave, "Contraseña cambiada. Esta es tu clave nueva")
        padre.wait_window(espera)
        self.destroy()


class VentanaIngreso(ctk.CTk):
    """Pide usuario y contraseña. Al terminar, `entro` dice si se pudo entrar."""

    def __init__(self):
        e.aplicar_tema()
        super().__init__()
        self.entro = False
        self.title(f"{config.NOMBRE_TIENDA} - Ingresar")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        self._cuerpo = None
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        if seguridad.hay_configuracion():
            self._mostrar_ingreso()
        else:
            self._mostrar_primera_vez()

    # ----------------------------------------------------------------- común
    def _nuevo_cuerpo(self, titulo, subtitulo):
        if self._cuerpo is not None:
            self._cuerpo.destroy()
        self._cuerpo = ctk.CTkFrame(self)
        self._cuerpo.pack(fill="both", expand=True, padx=e.MARGEN * 2,
                          pady=e.MARGEN * 2)
        ctk.CTkLabel(self._cuerpo, text=config.NOMBRE_TIENDA,
                     text_color=e.COLOR_PRIMARIO,
                     font=ctk.CTkFont(size=28, weight="bold")
                     ).pack(padx=40, pady=(28, 0))
        ctk.CTkLabel(self._cuerpo, text=titulo,
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(padx=40, pady=(6, 0))
        ctk.CTkLabel(self._cuerpo, text=subtitulo, wraplength=340,
                     text_color=e.COLOR_TEXTO_SUAVE
                     ).pack(padx=40, pady=(2, 14))
        return self._cuerpo

    def _error_label(self, cuerpo):
        etiqueta = ctk.CTkLabel(cuerpo, text="", anchor="w", justify="left",
                                text_color=e.COLOR_PELIGRO, wraplength=340)
        etiqueta.pack(fill="x", padx=40, pady=(0, 4))
        return etiqueta

    # --------------------------------------------------------------- ingreso
    def _mostrar_ingreso(self):
        cuerpo = self._nuevo_cuerpo("Ingresar", "Escribe tu usuario y contraseña.")
        usuarios = [u["nombre"] for u in seguridad.listar_usuarios()]
        self.usuario = CampoLista(cuerpo, "Usuario", valores=usuarios, ancho=340)
        self.usuario.pack(fill="x", padx=40, pady=(0, 8))
        if len(usuarios) == 1:
            self.usuario.poner(usuarios[0])
        self.clave = _clave(Campo(cuerpo, "Contraseña", ancho=340))
        self.clave.pack(fill="x", padx=40, pady=(0, 8))
        self.clave.al_enter(self._ingresar)
        self.error = self._error_label(cuerpo)
        boton(cuerpo, "Ingresar", self._ingresar, "principal",
              ancho=340).pack(padx=40, pady=(4, 6))
        boton(cuerpo, "Olvidé mi contraseña", self._recuperar, "secundario",
              ancho=340).pack(padx=40, pady=(0, 28))
        _centrar(self)
        (self.clave if len(usuarios) == 1 else self.usuario).foco()

    def _ingresar(self):
        try:
            seguridad.iniciar_sesion(self.usuario.obtener(),
                                     _clave_exacta(self.clave))
        except ValueError as error:
            self.error.configure(text=str(error))
            self.clave.limpiar()
            self.clave.foco()
            return
        self.entro = True
        self.destroy()

    def _recuperar(self):
        dialogo = _DialogoRecuperar(self)
        self.wait_window(dialogo)
        if dialogo.exito:
            self.error.configure(text="")
            self.clave.limpiar()
            self.clave.foco()

    # ---------------------------------------------------------- primera vez
    def _mostrar_primera_vez(self):
        cuerpo = self._nuevo_cuerpo(
            "Primer uso",
            "Crea el primer usuario y la contraseña del dueño. La del dueño "
            "solo la debe saber el dueño: protege la ganancia.")
        self.nombre = Campo(cuerpo, "Nombre de quien vende (solo el nombre)",
                            ancho=340, ayuda="Ej.: Marta  →  Analista-Marta")
        self.nombre.pack(fill="x", padx=40, pady=(0, 8))
        self.clave_u = _clave(Campo(cuerpo, "Contraseña del usuario", ancho=340))
        self.clave_u.pack(fill="x", padx=40, pady=(0, 8))
        self.clave_u2 = _clave(Campo(cuerpo, "Repite la contraseña del usuario",
                                     ancho=340))
        self.clave_u2.pack(fill="x", padx=40, pady=(0, 8))
        self.clave_d = _clave(Campo(cuerpo, "Contraseña del dueño (ganancia)",
                                    ancho=340))
        self.clave_d.pack(fill="x", padx=40, pady=(0, 8))
        self.clave_d2 = _clave(Campo(cuerpo, "Repite la contraseña del dueño",
                                     ancho=340))
        self.clave_d2.pack(fill="x", padx=40, pady=(0, 8))
        self.clave_d2.al_enter(self._crear)
        self.error = self._error_label(cuerpo)
        boton(cuerpo, "Crear y continuar", self._crear, "principal",
              ancho=340).pack(padx=40, pady=(4, 28))
        _centrar(self)
        self.nombre.foco()

    def _crear(self):
        usuario, dueno = _clave_exacta(self.clave_u), _clave_exacta(self.clave_d)
        if usuario != _clave_exacta(self.clave_u2):
            self.error.configure(
                text="Las dos contraseñas del usuario no son iguales.")
            return
        if dueno != _clave_exacta(self.clave_d2):
            self.error.configure(
                text="Las dos contraseñas del dueño no son iguales.")
            return
        try:
            recuperacion = seguridad.configurar_primera_vez(
                self.nombre.obtener(), usuario, dueno)
        except ValueError as error:
            self.error.configure(text=str(error))
            return
        # Las cuentas ya están creadas: se muestra la clave y se entra.
        dialogo = _DialogoClaveRecuperacion(self, recuperacion)
        self.wait_window(dialogo)
        seguridad.iniciar_sesion(self.nombre.obtener(), usuario)
        self.entro = True
        self.destroy()