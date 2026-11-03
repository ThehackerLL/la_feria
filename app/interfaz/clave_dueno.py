"""Contraseña del dueño (la misma para la ganancia y para las pestañas protegidas).

- Ganancia: al pulsar «Mostrar» se pide la contraseña; si es correcta, la
  ganancia se ve 60 segundos en Ventas, Caja y Reportes y luego se oculta sola.
- Pestañas protegidas (Inventario, Compras, Huella digital): se pide al entrar
  y se vuelve a pedir cada vez que se sale y se regresa (`pedir_acceso`).
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Campo, boton
from app.servicios import seguridad


class DialogoClaveDueno(ctk.CTkToplevel):
    def __init__(self, padre, titulo="Ver ganancia", texto=None,
                 texto_boton="Ver ganancia", accion=None):
        super().__init__(padre)
        self.resultado = False
        self._accion = accion or seguridad.desbloquear_ganancia
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text="Contraseña del dueño", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(cuerpo, anchor="w", justify="left", wraplength=340,
                     text_color=e.COLOR_TEXTO_SUAVE,
                     text=texto or f"La ganancia se verá "
                                   f"{seguridad.SEGUNDOS_GANANCIA} segundos y "
                                   "luego se oculta sola."
                     ).pack(fill="x", padx=18, pady=(0, 8))
        self.f_clave = Campo(cuerpo, "Contraseña", ancho=340)
        self.f_clave.caja.configure(show="•")
        self.f_clave.pack(fill="x", padx=18)
        self.f_clave.al_enter(self._aceptar)
        self._error = ctk.CTkLabel(cuerpo, text="", anchor="w", justify="left",
                                   wraplength=340, text_color=e.COLOR_PELIGRO,
                                   font=ctk.CTkFont(weight="bold"))
        self._error.pack(fill="x", padx=18, pady=(6, 0))
        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.pack(fill="x", padx=18, pady=(8, 16))
        boton(pie, texto_boton, self._aceptar, "ok", ancho=130).pack(side="right")
        boton(pie, "Cancelar", self._cancelar, "secundario",
              ancho=100).pack(side="right", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _ev: self._cancelar())
        self._centrar(padre)
        self.f_clave.foco()

    def _centrar(self, padre):
        self.update_idletasks()
        ancho, alto = self.winfo_reqwidth(), self.winfo_reqheight()
        raiz = padre.winfo_toplevel()
        x = raiz.winfo_rootx() + (raiz.winfo_width() - ancho) // 2
        y = raiz.winfo_rooty() + (raiz.winfo_height() - alto) // 2
        self.geometry(f"{ancho}x{alto}+{max(x, 0)}+{max(y, 0)}")
        self.transient(raiz)
        self.wait_visibility()
        self.grab_set()
        self.focus_set()

    def _terminar(self, resultado):
        self.resultado = resultado
        self.grab_release()
        self.destroy()

    def _cancelar(self):
        self._terminar(False)

    def _aceptar(self):
        try:
            self._accion(self.f_clave.obtener())
        except ValueError as error:
            self._error.configure(text=str(error))
            self.f_clave.limpiar()
            self.f_clave.foco()
            return
        self._terminar(True)


def alternar(padre):
    """Botón «Mostrar/Ocultar». Si está oculta, pide la contraseña del dueño.

    Devuelve True si la ganancia quedó visible."""
    if seguridad.ganancia_visible():
        seguridad.ocultar_ganancia()
        return False
    dialogo = DialogoClaveDueno(padre)
    padre.wait_window(dialogo)
    return dialogo.resultado


def pedir_acceso(padre, pestana):
    """Pide la contraseña del dueño para entrar a una pestaña protegida.

    Devuelve True si la escribió bien. No muestra la ganancia."""
    dialogo = DialogoClaveDueno(
        padre, titulo=f"Entrar a {pestana}",
        texto="Escribe la contraseña del dueño. Al salir de esta pestaña "
              "se vuelve a bloquear.",
        texto_boton="Entrar", accion=seguridad.comprobar_clave_dueno)
    padre.wait_window(dialogo)
    return dialogo.resultado


def pedir_para_exportar(padre):
    """Pide la contraseña del dueño antes de exportar el Excel (que lleva la
    ganancia de cada producto). True si la escribió bien."""
    dialogo = DialogoClaveDueno(
        padre, titulo="Exportar a Excel",
        texto="El Excel lleva la ganancia de cada producto. Escribe la "
              "contraseña del dueño para exportarlo.",
        texto_boton="Exportar", accion=seguridad.comprobar_clave_dueno)
    padre.wait_window(dialogo)
    return dialogo.resultado


def vigilar(widget, refrescar):
    """Cada segundo revisa si se acabaron los 60 s (o si otra pantalla ocultó
    la ganancia) y vuelve a dibujar el widget para que se oculte sola."""
    estado = {"visible": seguridad.ganancia_visible()}

    def _tic():
        try:
            if not widget.winfo_exists():
                return
            ahora = seguridad.ganancia_visible()
            if ahora != estado["visible"]:
                estado["visible"] = ahora
                refrescar()
            widget.after(1000, _tic)
        except Exception:          # la ventana se cerró
            pass

    widget.after(1000, _tic)