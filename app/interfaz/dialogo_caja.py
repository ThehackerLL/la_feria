"""Ventana para cerrar la caja: se cuenta el efectivo y se ve al instante si
cuadra, sobra o falta dinero.

Se usa para cerrar el día de hoy y también para un día anterior que se olvidó
cerrar (en ese caso además se puede «cerrar sin contar»).
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Campo, boton
from app.interfaz.dialogo_credito import fecha_corta
from app.utilidades.formato import moneda
from app.utilidades.validaciones import a_numero


class _DialogoCerrarCaja(ctk.CTkToplevel):
    def __init__(self, padre, fecha, esperado, anterior):
        super().__init__(padre)
        self.resultado = None      # {"contado", "nota", "sin_contar"} o None
        self._esperado = esperado
        self._contado = None       # número válido escrito, o None
        titulo = (f"Cerrar la caja del {fecha_corta(fecha)}" if anterior
                  else "Cerrar caja")
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)

        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text=titulo, anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 2))
        if anterior:
            ctk.CTkLabel(
                cuerpo, anchor="w", justify="left", wraplength=400,
                text="Ese día quedó sin cerrar. Cuenta el efectivo que había "
                     "o ciérralo sin contar.", text_color=e.COLOR_AVISO
                ).pack(fill="x", padx=18, pady=(0, 6))

        esp = ctk.CTkFrame(cuerpo, fg_color=e.COLOR_PRIMARIO_SUAVE,
                           corner_radius=e.RADIO)
        esp.pack(fill="x", padx=18, pady=(6, 10))
        ctk.CTkLabel(esp, text="Efectivo esperado en caja", anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE).pack(
                         fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(esp, text=moneda(esperado), anchor="w",
                     text_color=e.COLOR_PRIMARIO,
                     font=ctk.CTkFont(size=e.TAM_CIFRA, weight="bold")
                     ).pack(fill="x", padx=14, pady=(0, 10))

        self.f_contado = Campo(cuerpo, "Efectivo contado (lo que hay en el cajón)",
                               ayuda="0.00", ancho=400)
        self.f_contado.pack(fill="x", padx=18)
        self.f_contado.al_escribir(self._revisar)
        self.f_contado.al_enter(self._cerrar_caja)

        self._veredicto = ctk.CTkLabel(
            cuerpo, text="", anchor="w", justify="left", wraplength=400,
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._veredicto.pack(fill="x", padx=18, pady=(8, 4))

        self.f_nota = Campo(cuerpo, "Nota (opcional)",
                            ayuda="Por ejemplo: se dio vuelto de más", ancho=400)
        self.f_nota.pack(fill="x", padx=18, pady=(0, 4))

        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.pack(fill="x", padx=18, pady=(10, 16))
        self._b_cerrar = boton(pie, "Cerrar caja", self._cerrar_caja, "ok",
                               ancho=130)
        self._b_cerrar.pack(side="right")
        boton(pie, "Cancelar", self._cancelar, "secundario",
              ancho=100).pack(side="right", padx=(0, 8))
        if anterior:
            boton(pie, "Cerrar sin contar", self._sin_contar, "secundario",
                  ancho=150).pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _ev: self._cancelar())
        self._revisar()
        self._centrar(padre)
        self.f_contado.foco()

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
        self._terminar(None)

    def _revisar(self):
        """Dice al instante si cuadra, sobra o falta (y activa el botón)."""
        texto = self.f_contado.obtener()
        self._contado = None
        if texto:
            try:
                self._contado = a_numero(texto, "Efectivo contado")
            except ValueError as error:
                self._veredicto.configure(text=str(error),
                                          text_color=e.COLOR_AVISO)
        else:
            self._veredicto.configure(
                text="Cuenta el efectivo y escríbelo aquí.",
                text_color=e.COLOR_TEXTO_SUAVE)
        if self._contado is not None:
            dif = round(self._contado - self._esperado, 2)
            if dif == 0:
                self._veredicto.configure(text="Cuadra: no sobra ni falta nada.",
                                          text_color=e.COLOR_OK)
            elif dif > 0:
                self._veredicto.configure(text=f"Sobran {moneda(dif)}",
                                          text_color=e.COLOR_AVISO)
            else:
                self._veredicto.configure(text=f"Faltan {moneda(-dif)}",
                                          text_color=e.COLOR_PELIGRO)
        self._b_cerrar.configure(
            state="normal" if self._contado is not None else "disabled")

    def _cerrar_caja(self):
        if self._contado is None:
            return
        self._terminar({"contado": self._contado, "sin_contar": False,
                        "nota": self.f_nota.obtener()})

    def _sin_contar(self):
        self._terminar({"contado": None, "sin_contar": True,
                        "nota": self.f_nota.obtener()})


def cerrar_caja(padre, fecha, esperado, anterior=False):
    """Abre la ventana de cierre.

    Devuelve {"contado": número o None, "sin_contar": bool, "nota": texto},
    o None si se cancela. `anterior=True` es para un día que se olvidó cerrar.
    """
    dialogo = _DialogoCerrarCaja(padre, fecha, esperado, anterior)
    padre.wait_window(dialogo)
    return dialogo.resultado