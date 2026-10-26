"""Piezas visuales reutilizables: botones, campos, tablas, alertas y ventanas.

Todas las pantallas usan estas piezas, así se ven iguales en todo el programa.
"""
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from app.interfaz import estilos as e

# ------------------------------------------------------------------ botones
_TIPOS_BOTON = {
    "principal": (e.COLOR_PRIMARIO, e.COLOR_PRIMARIO_HOVER, "#FFFFFF"),
    "ok": (e.COLOR_OK, e.COLOR_OK_HOVER, "#FFFFFF"),
    "peligro": (e.COLOR_PELIGRO, e.COLOR_PELIGRO_HOVER, "#FFFFFF"),
    "secundario": (e.COLOR_NEUTRO, e.COLOR_NEUTRO_HOVER, e.COLOR_TEXTO),
}


def boton(padre, texto, comando=None, tipo="principal", ancho=120):
    """Botón estándar. tipo: principal, ok, peligro o secundario."""
    fondo, hover, texto_color = _TIPOS_BOTON[tipo]
    return ctk.CTkButton(padre, text=texto, command=comando, width=ancho,
                         height=e.ALTO_CONTROL, fg_color=fondo,
                         hover_color=hover, text_color=texto_color,
                         font=ctk.CTkFont(weight="bold"))


# ------------------------------------------------------------------ campos
def _etiqueta(padre, texto):
    return ctk.CTkLabel(padre, text=texto, anchor="w",
                        text_color=e.COLOR_TEXTO_SUAVE,
                        font=ctk.CTkFont(size=e.TAM_PEQUENO))


class Campo(ctk.CTkFrame):
    """Caja de texto con su etiqueta arriba."""

    def __init__(self, padre, etiqueta, ancho=200, ayuda=""):
        super().__init__(padre, fg_color="transparent")
        _etiqueta(self, etiqueta).pack(fill="x")
        self.caja = ctk.CTkEntry(self, width=ancho, height=e.ALTO_CONTROL,
                                 placeholder_text=ayuda)
        self.caja.pack(fill="x", pady=(2, 0))

    def obtener(self):
        return self.caja.get().strip()

    def poner(self, texto):
        self.caja.delete(0, "end")
        self.caja.insert(0, "" if texto is None else str(texto))

    def limpiar(self):
        self.poner("")

    def foco(self):
        self.caja.focus_set()

    def al_escribir(self, funcion):
        """Llama a funcion() cada vez que se suelta una tecla."""
        self.caja.bind("<KeyRelease>", lambda _ev: funcion())

    def al_enter(self, funcion):
        self.caja.bind("<Return>", lambda _ev: funcion())

    def desactivar(self, desactivado=True):
        self.caja.configure(state="disabled" if desactivado else "normal")


class CampoLista(ctk.CTkFrame):
    """Lista desplegable que también deja escribir, con su etiqueta."""

    def __init__(self, padre, etiqueta, valores=(), ancho=200):
        super().__init__(padre, fg_color="transparent")
        _etiqueta(self, etiqueta).pack(fill="x")
        self.caja = ctk.CTkComboBox(self, values=list(valores) or [""],
                                    width=ancho, height=e.ALTO_CONTROL)
        self.caja.set("")
        self.caja.pack(fill="x", pady=(2, 0))

    def obtener(self):
        return self.caja.get().strip()

    def poner(self, texto):
        self.caja.set("" if texto is None else str(texto))

    def limpiar(self):
        self.caja.set("")

    def cambiar_valores(self, valores):
        self.caja.configure(values=list(valores) or [""])


# ---------------------------------------------------------------- tarjetas
class TarjetaResumen(ctk.CTkFrame):
    """Cifra grande con su título, para los resúmenes de arriba."""

    def __init__(self, padre, titulo, valor="0"):
        super().__init__(padre, border_width=1, border_color=e.COLOR_BORDE)
        ctk.CTkLabel(self, text=titulo, anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_PEQUENO)
                     ).pack(fill="x", padx=14, pady=(10, 0))
        self._valor = ctk.CTkLabel(self, text=valor, anchor="w",
                                   font=ctk.CTkFont(size=e.TAM_CIFRA,
                                                    weight="bold"))
        self._valor.pack(fill="x", padx=14, pady=(0, 10))

    def actualizar(self, valor, color=None):
        self._valor.configure(text=valor, text_color=color or e.COLOR_TEXTO)


# ------------------------------------------------------------------ tabla
class Tabla(ctk.CTkFrame):
    """Tabla con barra de desplazamiento.

    columnas: lista de (id, título, ancho, alineación[, elástica]).
    alineación: "w" (izquierda), "center" o "e" (derecha, para cifras).
    elástica=True en UNA columna (la de texto largo): es la que se estira
    cuando la ventana crece. Los anchos se ajustan solos al escalado de
    pantalla de Windows.
    """

    def __init__(self, padre, columnas, alto=10):
        super().__init__(padre, border_width=1, border_color=e.COLOR_BORDE)
        e.configurar_tabla()
        ids = [c[0] for c in columnas]
        self.arbol = ttk.Treeview(self, style="Feria.Treeview", columns=ids,
                                  show="headings", height=alto,
                                  selectmode="browse")
        escala = self.winfo_fpixels("1i") / 96     # 1.0 = 100 %, 1.25 = 125 %
        for id_, titulo, ancho, alineacion, *extra in columnas:
            px = int(ancho * escala)
            self.arbol.heading(id_, text=titulo,
                               anchor="w" if alineacion == "w" else alineacion)
            self.arbol.column(id_, width=px, minwidth=px, anchor=alineacion,
                              stretch=bool(extra and extra[0]))
        barra = ctk.CTkScrollbar(self, command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra.set)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.arbol.grid(row=0, column=0, sticky="nsew", padx=(2, 0), pady=2)
        barra.grid(row=0, column=1, sticky="ns", padx=(0, 2), pady=2)
        # colores de estado para las filas
        self.arbol.tag_configure("aviso", background=e.COLOR_AVISO_FONDO,
                                 foreground=e.COLOR_AVISO)
        self.arbol.tag_configure("peligro", background=e.COLOR_PELIGRO_FONDO,
                                 foreground=e.COLOR_PELIGRO)

    def vaciar(self):
        self.arbol.delete(*self.arbol.get_children())

    def cargar(self, filas):
        """filas: lista de (id, valores, estado). estado: '', 'aviso' o 'peligro'."""
        self.vaciar()
        for id_, valores, estado in filas:
            self.arbol.insert("", "end", iid=str(id_), values=valores,
                              tags=(estado,) if estado else ())

    def seleccionado(self):
        """Id de la fila elegida, o None."""
        elegido = self.arbol.selection()
        return elegido[0] if elegido else None

    def al_elegir(self, funcion):
        """Llama a funcion(id) cuando el usuario elige una fila."""
        def _evento(_ev):
            id_ = self.seleccionado()
            if id_ is not None:
                funcion(id_)
        self.arbol.bind("<<TreeviewSelect>>", _evento)

    def al_doble_clic(self, funcion):
        def _evento(_ev):
            id_ = self.seleccionado()
            if id_ is not None:
                funcion(id_)
        self.arbol.bind("<Double-1>", _evento)

    def quitar_seleccion(self):
        self.arbol.selection_remove(self.arbol.selection())


# ------------------------------------------------------------------ alerta
_TIPOS_ALERTA = {
    "error": (e.COLOR_PELIGRO_FONDO, e.COLOR_PELIGRO),
    "aviso": (e.COLOR_AVISO_FONDO, e.COLOR_AVISO),
    "ok": (e.COLOR_OK_FONDO, e.COLOR_OK),
}


class Alerta(ctk.CTkFrame):
    """Franja de mensaje dentro de la pantalla.

    Se coloca UNA vez con pack(fill="x") donde deba aparecer. Mientras no hay
    mensaje no ocupa espacio.
    """

    def __init__(self, padre):
        super().__init__(padre, height=0, fg_color="transparent")
        self._banda = ctk.CTkFrame(self, corner_radius=e.RADIO)
        self._texto = ctk.CTkLabel(self._banda, text="", anchor="w",
                                   justify="left", wraplength=700,
                                   font=ctk.CTkFont(weight="bold"))
        self._texto.pack(fill="x", padx=14, pady=8)
        self._pendiente = None

    def mostrar(self, mensaje, tipo="error", segundos=None):
        """Muestra el mensaje. Si es de éxito se oculta solo a los 5 s."""
        fondo, texto = _TIPOS_ALERTA[tipo]
        self._banda.configure(fg_color=fondo)
        self._texto.configure(text=mensaje, text_color=texto)
        self._banda.pack(fill="x", pady=(0, e.ESPACIO))
        if self._pendiente:
            self.after_cancel(self._pendiente)
            self._pendiente = None
        if segundos is None and tipo == "ok":
            segundos = 5
        if segundos:
            self._pendiente = self.after(int(segundos * 1000), self.ocultar)

    def ocultar(self):
        if self._pendiente:
            self.after_cancel(self._pendiente)
            self._pendiente = None
        self._banda.pack_forget()
        self.configure(height=0)   # Tk no encoge solo el contenedor


# ---------------------------------------------------------------- ventanas
class _Dialogo(ctk.CTkToplevel):
    """Ventana modal centrada sobre la ventana que la abre."""

    def __init__(self, padre, titulo, mensaje, botones):
        """botones: lista de (texto, tipo, resultado)."""
        super().__init__(padre)
        self.resultado = False
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text=titulo, anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(cuerpo, text=mensaje, anchor="w", justify="left",
                     wraplength=380, text_color=e.COLOR_TEXTO_SUAVE
                     ).pack(fill="x", padx=18, pady=(0, 14))
        fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=(0, 16))
        for texto, tipo, resultado in reversed(botones):
            boton(fila, texto, lambda r=resultado: self._cerrar(r),
                  tipo=tipo, ancho=110).pack(side="right", padx=(8, 0))
        self.protocol("WM_DELETE_WINDOW", lambda: self._cerrar(False))
        self.bind("<Escape>", lambda _ev: self._cerrar(False))
        self._centrar(padre)

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

    def _cerrar(self, resultado):
        self.resultado = resultado
        self.grab_release()
        self.destroy()


def aviso(padre, titulo, mensaje):
    """Ventana con un mensaje y un botón Aceptar."""
    dialogo = _Dialogo(padre, titulo, mensaje, [("Aceptar", "principal", True)])
    padre.wait_window(dialogo)


def confirmar(padre, titulo, mensaje, texto_si="Aceptar", peligro=False):
    """Pregunta Sí/No. Devuelve True si el usuario confirma."""
    dialogo = _Dialogo(padre, titulo, mensaje, [
        ("Cancelar", "secundario", False),
        (texto_si, "peligro" if peligro else "principal", True)])
    padre.wait_window(dialogo)
    return dialogo.resultado