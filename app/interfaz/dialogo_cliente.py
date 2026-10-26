"""Ventana para elegir el cliente de una venta o crear uno nuevo.

Un cliente solo se guarda con nombre Y teléfono juntos. Si falta uno, se
avisa y no se guarda: la venta sigue como "Público general". El DNI y la
dirección son opcionales.
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Alerta, Campo, Tabla, boton
from app.servicios import clientes

COLUMNAS = [
    ("nombre", "Nombre", 250, "w", True),   # la que se estira
    ("telefono", "Teléfono", 130, "w"),
]


class _DialogoCliente(ctk.CTkToplevel):
    def __init__(self, padre):
        super().__init__(padre)
        self.resultado = None          # el Cliente elegido, o None
        self._clientes = {}            # id (texto) -> Cliente de la lista
        self.title("Cliente de la venta")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)

        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        cuerpo.grid_columnconfigure((0, 1), weight=1, uniform="col")

        ctk.CTkLabel(cuerpo, text="Elegir cliente guardado", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, sticky="ew",
                            padx=18, pady=(16, 4))
        self.f_buscar = Campo(cuerpo, "Buscar por nombre o teléfono",
                              ayuda="Escribe para filtrar", ancho=460)
        self.f_buscar.grid(row=1, column=0, columnspan=2, sticky="ew",
                           padx=18, pady=4)
        self.f_buscar.al_escribir(self._buscar)
        self.f_buscar.al_enter(self._elegir_seleccionado)

        self._lista = Tabla(cuerpo, COLUMNAS, alto=6)
        self._lista.grid(row=2, column=0, columnspan=2, sticky="ew",
                         padx=18, pady=4)
        self._lista.al_elegir(lambda _id: self._boton_elegir.configure(
            state="normal"))
        self._lista.al_doble_clic(lambda _id: self._elegir_seleccionado())

        self._vacio = ctk.CTkLabel(cuerpo, text="", anchor="w",
                                   text_color=e.COLOR_TEXTO_SUAVE)
        self._vacio.grid(row=3, column=0, sticky="w", padx=18)
        self._boton_elegir = boton(cuerpo, "Elegir cliente",
                                   self._elegir_seleccionado, "principal",
                                   ancho=150)
        self._boton_elegir.grid(row=3, column=1, sticky="e", padx=18, pady=4)

        ctk.CTkFrame(cuerpo, height=1, fg_color=e.COLOR_BORDE
                     ).grid(row=4, column=0, columnspan=2, sticky="ew",
                            padx=18, pady=(12, 8))

        ctk.CTkLabel(cuerpo, text="Cliente nuevo", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=5, column=0, columnspan=2, sticky="ew",
                            padx=18, pady=(0, 4))
        self.f_nombre = Campo(cuerpo, "Nombre", ayuda="Nombre y apellido")
        self.f_telefono = Campo(cuerpo, "Teléfono", ayuda="999111222")
        self.f_nombre.grid(row=6, column=0, sticky="ew", padx=(18, 6), pady=4)
        self.f_telefono.grid(row=6, column=1, sticky="ew", padx=(6, 18), pady=4)
        self.f_dni = Campo(cuerpo, "DNI (opcional)", ayuda="8 números")
        self.f_direccion = Campo(cuerpo, "Dirección (opcional)",
                                 ayuda="Ciudad, calle…")
        self.f_dni.grid(row=7, column=0, sticky="ew", padx=(18, 6), pady=4)
        self.f_direccion.grid(row=7, column=1, sticky="ew", padx=(6, 18), pady=4)
        for campo in (self.f_nombre, self.f_telefono):
            campo.al_escribir(self._revisar_nuevo)
        for campo in (self.f_nombre, self.f_telefono, self.f_dni,
                      self.f_direccion):
            campo.al_enter(self._guardar)

        self._nota = ctk.CTkLabel(
            cuerpo, text="", anchor="w", justify="left", wraplength=440,
            font=ctk.CTkFont(weight="bold"))
        self._nota.grid(row=8, column=0, columnspan=2, sticky="ew", padx=18)

        self.alerta = Alerta(cuerpo)
        self.alerta.grid(row=9, column=0, columnspan=2, sticky="ew", padx=18,
                         pady=(4, 0))

        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.grid(row=10, column=0, columnspan=2, sticky="ew", padx=18,
                 pady=(8, 16))
        self._boton_guardar = boton(pie, "Guardar y elegir", self._guardar,
                                    "ok", ancho=160)
        self._boton_guardar.pack(side="right")
        boton(pie, "Cancelar", self._cancelar, "secundario",
              ancho=110).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _ev: self._cancelar())
        self._buscar()
        self._revisar_nuevo()
        self._centrar(padre)
        self.f_buscar.foco()

    # --------------------------------------------------------------- ventana
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

    def _cerrar(self, cliente):
        self.resultado = cliente
        self.grab_release()
        self.destroy()

    def _cancelar(self):
        self._cerrar(None)

    # ------------------------------------------------------- clientes guardados
    def _buscar(self):
        texto = self.f_buscar.obtener()
        encontrados = clientes.buscar_clientes(texto, limite=50)
        self._clientes = {str(c.id): c for c in encontrados}
        self._lista.cargar([(c.id, (c.nombre, c.telefono or "—"), "")
                            for c in encontrados])
        self._boton_elegir.configure(state="disabled")
        if encontrados:
            self._vacio.configure(text="")
        elif texto:
            self._vacio.configure(text="Ningún cliente coincide.")
        else:
            self._vacio.configure(text="Todavía no hay clientes guardados.")

    def _elegir_seleccionado(self):
        """Elige la fila marcada; si no hay, la primera de la lista."""
        id_ = self._lista.seleccionado()
        if id_ is None and len(self._clientes) >= 1:
            id_ = next(iter(self._clientes))
        if id_ is not None:
            self._cerrar(self._clientes[id_])

    # ---------------------------------------------------------- cliente nuevo
    def _revisar_nuevo(self):
        """Avisa si falta el nombre o el teléfono. Solo con los dos se guarda."""
        nombre, telefono = self.f_nombre.obtener(), self.f_telefono.obtener()
        if nombre and not telefono:
            self._nota.configure(
                text="Para guardar al cliente escribe también su teléfono.",
                text_color=e.COLOR_AVISO)
        elif telefono and not nombre:
            self._nota.configure(
                text="Para guardar al cliente escribe también su nombre.",
                text_color=e.COLOR_AVISO)
        else:
            self._nota.configure(
                text="Nombre y teléfono son obligatorios; DNI y dirección no.",
                text_color=e.COLOR_TEXTO_SUAVE)
        self._boton_guardar.configure(
            state="normal" if (nombre and telefono) else "disabled")

    def _guardar(self):
        if not (self.f_nombre.obtener() and self.f_telefono.obtener()):
            return
        try:
            cliente = clientes.crear_cliente(
                self.f_nombre.obtener(), self.f_telefono.obtener(),
                self.f_dni.obtener(), self.f_direccion.obtener())
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        self._cerrar(cliente)


def elegir_cliente(padre):
    """Abre la ventana. Devuelve el Cliente elegido o creado, o None si
    se cancela (la venta sigue como Público general)."""
    dialogo = _DialogoCliente(padre)
    padre.wait_window(dialogo)
    return dialogo.resultado