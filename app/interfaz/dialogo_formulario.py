"""Ventana pequeña con varios campos (nombre, contraseñas…) y un botón de acción.

Se usa en Configuración → Usuarios y contraseñas. La acción recibe un diccionario
{clave_del_campo: texto}; si algo está mal levanta ValueError y el mensaje se
muestra en rojo sin cerrar la ventana.
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Campo, boton


class DialogoFormulario(ctk.CTkToplevel):
    def __init__(self, padre, titulo, campos, texto_boton, accion, texto="",
                 peligro=False):
        """campos: lista de (clave, etiqueta, oculto). oculto=True -> puntos (•)."""
        super().__init__(padre)
        self.resultado = False
        self._accion = accion
        self._claves = [c[0] for c in campos]
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text=titulo, anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 2))
        if texto:
            ctk.CTkLabel(cuerpo, text=texto, anchor="w", justify="left",
                         wraplength=360, text_color=e.COLOR_TEXTO_SUAVE
                         ).pack(fill="x", padx=18, pady=(0, 8))
        self._campos = {}
        for clave, etiqueta, oculto in campos:
            campo = Campo(cuerpo, etiqueta, ancho=360)
            if oculto:
                campo.caja.configure(show="•")
            campo.pack(fill="x", padx=18, pady=(0, 6))
            campo.al_enter(self._aceptar)
            self._campos[clave] = campo
        self._error = ctk.CTkLabel(cuerpo, text="", anchor="w", justify="left",
                                   wraplength=360, text_color=e.COLOR_PELIGRO,
                                   font=ctk.CTkFont(weight="bold"))
        self._error.pack(fill="x", padx=18, pady=(2, 0))
        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.pack(fill="x", padx=18, pady=(8, 16))
        boton(pie, texto_boton, self._aceptar, "peligro" if peligro else "ok",
              ancho=150).pack(side="right")
        boton(pie, "Cancelar", self._cancelar, "secundario",
              ancho=100).pack(side="right", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _ev: self._cancelar())
        self._centrar(padre)
        self._campos[self._claves[0]].foco()

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
        valores = {k: self._campos[k].caja.get() for k in self._claves}
        try:
            self._accion(valores)
        except ValueError as error:
            self._error.configure(text=str(error))
            return
        self._terminar(True)


def pedir_formulario(padre, titulo, campos, texto_boton, accion, texto="",
                     peligro=False):
    """Abre el formulario y espera. True si la acción se hizo."""
    dialogo = DialogoFormulario(padre, titulo, campos, texto_boton, accion,
                                texto, peligro)
    padre.wait_window(dialogo)
    return dialogo.resultado