"""Ventana para crear un proveedor nuevo o corregir los datos de uno.

Se guarda con nombre Y teléfono (obligatorios); la dirección y el rubro (a
qué se dedica) son opcionales. Se usa desde la pantalla de Compras (el nuevo
queda creado y elegido) y desde la pestaña Proveedores (crear y editar).
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Alerta, Campo, boton
from app.servicios import proveedores


class _DialogoProveedorNuevo(ctk.CTkToplevel):
    def __init__(self, padre, proveedor=None):
        super().__init__(padre)
        self.resultado = None          # el Proveedor creado o editado, o None
        self._editado = proveedor      # None = proveedor nuevo
        titulo = "Editar proveedor" if proveedor else "Proveedor nuevo"
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)

        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        cuerpo.grid_columnconfigure((0, 1), weight=1, uniform="col")

        ctk.CTkLabel(cuerpo, text=titulo, anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, sticky="ew",
                            padx=18, pady=(16, 4))
        self.f_nombre = Campo(cuerpo, "Nombre", ayuda="Nombre o empresa",
                              ancho=240)
        self.f_telefono = Campo(cuerpo, "Teléfono", ayuda="999111222",
                                ancho=240)
        self.f_direccion = Campo(cuerpo, "Dirección (opcional)",
                                 ayuda="Ciudad, calle…", ancho=240)
        self.f_rubro = Campo(cuerpo, "Rubro (a qué se dedica, opcional)",
                             ayuda="Ropa de mujer, jeans…", ancho=240)
        self.f_nombre.grid(row=1, column=0, sticky="ew", padx=(18, 6), pady=4)
        self.f_telefono.grid(row=1, column=1, sticky="ew", padx=(6, 18), pady=4)
        self.f_direccion.grid(row=2, column=0, sticky="ew", padx=(18, 6), pady=4)
        self.f_rubro.grid(row=2, column=1, sticky="ew", padx=(6, 18), pady=4)
        for campo in (self.f_nombre, self.f_telefono, self.f_direccion,
                      self.f_rubro):
            campo.al_escribir(self._revisar)
            campo.al_enter(self._guardar)

        self._nota = ctk.CTkLabel(
            cuerpo, text="", anchor="w", justify="left", wraplength=480,
            font=ctk.CTkFont(weight="bold"))
        self._nota.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18,
                        pady=(4, 0))
        self.alerta = Alerta(cuerpo)
        self.alerta.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18,
                         pady=(4, 0))

        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.grid(row=5, column=0, columnspan=2, sticky="ew", padx=18,
                 pady=(8, 16))
        self._boton_guardar = boton(
            pie, "Guardar cambios" if proveedor else "Guardar y elegir",
            self._guardar, "ok", ancho=160)
        self._boton_guardar.pack(side="right")
        boton(pie, "Cancelar", self._cancelar, "secundario",
              ancho=110).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _ev: self._cancelar())
        if proveedor:
            self.f_nombre.poner(proveedor.nombre)
            self.f_telefono.poner(proveedor.telefono)
            self.f_direccion.poner(proveedor.direccion)
            self.f_rubro.poner(proveedor.vende)
        self._revisar()
        self._centrar(padre)
        self.f_nombre.foco()

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

    def _cerrar(self, proveedor):
        self.resultado = proveedor
        self.grab_release()
        self.destroy()

    def _cancelar(self):
        self._cerrar(None)

    def _revisar(self):
        """Avisa si falta el nombre o el teléfono. Solo con los dos se guarda."""
        nombre, telefono = self.f_nombre.obtener(), self.f_telefono.obtener()
        if nombre and not telefono:
            self._nota.configure(
                text="Para guardar al proveedor escribe también su teléfono.",
                text_color=e.COLOR_AVISO)
        elif telefono and not nombre:
            self._nota.configure(
                text="Para guardar al proveedor escribe también su nombre.",
                text_color=e.COLOR_AVISO)
        else:
            self._nota.configure(text="Nombre y teléfono son obligatorios.",
                                 text_color=e.COLOR_TEXTO_SUAVE)
        self._boton_guardar.configure(
            state="normal" if (nombre and telefono) else "disabled")

    def _guardar(self):
        if not (self.f_nombre.obtener() and self.f_telefono.obtener()):
            return
        datos = (self.f_nombre.obtener(), self.f_telefono.obtener(),
                 self.f_direccion.obtener(), self.f_rubro.obtener())
        try:
            if self._editado:
                proveedor = proveedores.actualizar_proveedor(
                    self._editado.id, *datos)
            else:
                proveedor = proveedores.crear_proveedor(*datos)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        self._cerrar(proveedor)


def crear_proveedor_nuevo(padre):
    """Abre la ventana. Devuelve el Proveedor creado, o None si se cancela."""
    dialogo = _DialogoProveedorNuevo(padre)
    padre.wait_window(dialogo)
    return dialogo.resultado


def editar_proveedor(padre, proveedor):
    """Abre la ventana con los datos del proveedor. Devuelve el Proveedor ya
    actualizado, o None si se cancela."""
    dialogo = _DialogoProveedorNuevo(padre, proveedor)
    padre.wait_window(dialogo)
    return dialogo.resultado