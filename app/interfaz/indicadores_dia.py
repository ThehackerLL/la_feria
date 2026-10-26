"""Franja con los 4 indicadores del día, para verlos mientras se vende:
Venta del día, Ganancia del día, Efectivo y Digital.

Los números salen de servicios/caja.py, los mismos de «Caja del día», así que
coinciden en todas las pantallas. Si la caja de hoy no se abrió, la tarjeta de
Efectivo ofrece «Abrir caja». La ganancia sale oculta hasta pulsar «Mostrar».
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Campo, boton
from app.servicios import caja
from app.utilidades.formato import moneda
from app.utilidades.validaciones import a_numero

OCULTO = "S/ ••••"


class _DialogoAbrirCaja(ctk.CTkToplevel):
    def __init__(self, padre, sugerida):
        super().__init__(padre)
        self.resultado = None          # el efectivo inicial, o None
        self.title("Abrir caja")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text="Abrir la caja de hoy", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(cuerpo, anchor="w", justify="left", wraplength=360,
                     text_color=e.COLOR_TEXTO_SUAVE,
                     text="Escribe con cuánto efectivo empiezas el día. Ya "
                          "aparece lo que contaste en el último cierre."
                     ).pack(fill="x", padx=18, pady=(0, 8))
        self.f_apertura = Campo(cuerpo, "Efectivo con el que empiezas",
                                ayuda="0.00", ancho=360)
        self.f_apertura.pack(fill="x", padx=18)
        self.f_apertura.poner(f"{sugerida:.2f}")
        self.f_apertura.al_enter(self._abrir)
        self._error = ctk.CTkLabel(cuerpo, text="", anchor="w", justify="left",
                                   wraplength=360, text_color=e.COLOR_PELIGRO,
                                   font=ctk.CTkFont(weight="bold"))
        self._error.pack(fill="x", padx=18, pady=(6, 0))
        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.pack(fill="x", padx=18, pady=(8, 16))
        boton(pie, "Abrir caja", self._abrir, "ok", ancho=130).pack(side="right")
        boton(pie, "Cancelar", self._cancelar, "secundario",
              ancho=100).pack(side="right", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _ev: self._cancelar())
        self._centrar(padre)
        self.f_apertura.foco()

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

    def _abrir(self):
        try:
            monto = a_numero(self.f_apertura.obtener(), "Efectivo con el que empiezas")
            caja.abrir_dia(monto)
        except ValueError as error:
            self._error.configure(text=str(error))
            return
        self._terminar(monto)


class FranjaIndicadores(ctk.CTkFrame):
    # Compartido por todas las pantallas: si se muestra la ganancia en una,
    # se ve igual en las demás hasta ocultarla o cerrar el programa.
    ver_ganancia = False

    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._valores, self._titulos = {}, {}
        for i, (clave, titulo) in enumerate([
                ("vendido", "Venta del día"), ("ganancia", "Ganancia del día"),
                ("efectivo", "Efectivo"), ("digital", "Digital")]):
            self.grid_columnconfigure(i, weight=1, uniform="ind")
            tarjeta = ctk.CTkFrame(self, border_width=1, border_color=e.COLOR_BORDE)
            tarjeta.grid(row=0, column=i, sticky="ew",
                         padx=(0 if i == 0 else e.ESPACIO // 2,
                               0 if i == 3 else e.ESPACIO // 2))
            self._titulos[clave] = ctk.CTkLabel(
                tarjeta, text=titulo, anchor="w", text_color=e.COLOR_TEXTO_SUAVE,
                font=ctk.CTkFont(size=e.TAM_PEQUENO))
            self._titulos[clave].pack(fill="x", padx=14, pady=(4, 0))
            self._valores[clave] = ctk.CTkLabel(
                tarjeta, text="", anchor="w",
                font=ctk.CTkFont(size=e.TAM_SUBTITULO + 2, weight="bold"))
            self._valores[clave].pack(fill="x", padx=14, pady=(0, 4))
            if clave == "ganancia":
                self._b_ojo = self._boton_chico(tarjeta, "Mostrar", self._alternar)
            if clave == "efectivo":
                self._b_abrir = self._boton_chico(tarjeta, "Abrir caja", self._abrir,
                                                  principal=True)
        self.refrescar()

    @staticmethod
    def _boton_chico(tarjeta, texto, comando, principal=False):
        b = ctk.CTkButton(
            tarjeta, text=texto, width=84 if principal else 64, height=26,
            command=comando, font=ctk.CTkFont(size=e.TAM_PEQUENO, weight="bold"),
            fg_color=e.COLOR_PRIMARIO if principal else e.COLOR_NEUTRO,
            hover_color=e.COLOR_PRIMARIO_HOVER if principal else e.COLOR_NEUTRO_HOVER,
            text_color="#FFFFFF" if principal else e.COLOR_TEXTO)
        b.place(relx=1.0, x=-10, rely=0.5, anchor="e")
        return b

    def _alternar(self):
        FranjaIndicadores.ver_ganancia = not FranjaIndicadores.ver_ganancia
        self.refrescar()

    def _abrir(self):
        dialogo = _DialogoAbrirCaja(self, caja.sugerir_apertura())
        self.wait_window(dialogo)
        self.refrescar()

    def refrescar(self):
        """Vuelve a leer los números (se llama después de cada venta)."""
        i = caja.indicadores_dia()
        self._valores["vendido"].configure(text=moneda(i["vendido"]))
        self._valores["ganancia"].configure(
            text=moneda(i["ganancia"]) if self.ver_ganancia else OCULTO)
        self._b_ojo.configure(text="Ocultar" if self.ver_ganancia else "Mostrar")
        self._valores["digital"].configure(text=moneda(i["digital"]))
        if i["estado"] is None:                        # caja sin abrir
            self._titulos["efectivo"].configure(text="Efectivo (caja sin abrir)")
            self._valores["efectivo"].configure(text="—", text_color=e.COLOR_TEXTO_SUAVE)
            self._b_abrir.place(relx=1.0, x=-10, rely=0.5, anchor="e")
        else:
            cerrada = not i["abierta"]
            self._titulos["efectivo"].configure(
                text="Efectivo (caja cerrada)" if cerrada else "Efectivo")
            self._valores["efectivo"].configure(
                text=moneda(i["efectivo"]),
                text_color=e.COLOR_TEXTO_SUAVE if cerrada else e.COLOR_TEXTO)
            self._b_abrir.place_forget()