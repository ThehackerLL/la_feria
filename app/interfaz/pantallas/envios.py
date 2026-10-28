"""Pestaña Envíos: a quién se le mandó un paquete (Olva, Shalom o a domicilio)
y qué productos llevaba.

Un envío sale de Ventas: antes de cobrar se pulsa «Envío», se llenan los datos
y, al cobrar, el envío queda ligado a esa venta. Aquí se ve la lista de
clientes y, al elegir uno, los productos que se le mandaron. El envío lo paga
el cliente, así que no hay dinero en esta pestaña.
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import (Alerta, Campo, CampoLista, Tabla,
                                      TarjetaResumen, boton, confirmar)
from app.interfaz.dialogo_credito import fecha_corta
from app.servicios import anulaciones, clientes, envios
from app.utilidades.formato import moneda

COLUMNAS = [
    ("fecha", "Fecha", 85, "w"),
    ("nombre", "Recibe", 150, "w", True),
    ("servicio", "Servicio", 80, "w"),
    ("destino", "Destino", 190, "w"),
    ("guia", "Guía", 90, "w"),
    ("venta", "Venta", 85, "w"),
]
COLUMNAS_PRODUCTOS = [
    ("producto", "Producto", 150, "w", True),
    ("tipo", "Tipo", 60, "w"),
    ("cant", "Cant.", 50, "e"),
    ("precio", "Precio", 75, "e"),
    ("subtotal", "Subtotal", 85, "e"),
]
COLUMNAS_CLIENTES = [
    ("nombre", "Cliente", 170, "w", True),
    ("telefono", "Teléfono", 100, "w"),
    ("direccion", "Dirección", 170, "w"),
]


class DialogoEnvio(ctk.CTkToplevel):
    """Datos de un envío. resultado = dict de datos, o None si se cancela.

    envio: datos ya escritos (para editarlos). cliente: el cliente de la venta,
    para sugerir sus datos. con_venta=False oculta el campo «Venta» (cuando se
    abre desde Ventas, la venta todavía no existe: se liga sola al cobrar).
    """

    def __init__(self, padre, envio=None, cliente=None, con_venta=True):
        super().__init__(padre)
        self.resultado = None
        self._con_venta = con_venta
        self._cliente_id = (envio or {}).get("cliente_id") or (
            cliente.id if cliente else None)
        self._clientes = {}
        self.title("Editar envío" if envio else "Nuevo envío")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text="Editar envío" if envio else "Nuevo envío",
                     anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 8))

        if not envio:
            self.buscar = Campo(cuerpo, "Buscar cliente guardado (opcional)",
                                ancho=460, ayuda="Nombre, teléfono o dirección")
            self.buscar.pack(fill="x", padx=18, pady=(0, 4))
            self.buscar.al_escribir(self._buscar)
            self.lista = Tabla(cuerpo, COLUMNAS_CLIENTES, alto=3)
            for hijo in self.lista.winfo_children():
                if isinstance(hijo, ctk.CTkScrollbar):
                    hijo.configure(height=50)
            self.lista.pack(fill="x", padx=18, pady=(0, 8))
            self.lista.al_elegir(self._elegir_cliente)
            self._buscar()

        self.nombre = Campo(cuerpo, "Nombre de quien recibe", ancho=460)
        self.nombre.pack(fill="x", padx=18, pady=(0, 8))
        fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=(0, 8))
        self.telefono = Campo(fila, "Teléfono", ancho=150)
        self.telefono.pack(side="left")
        self.dni = Campo(fila, "DNI (lo piden en agencia)", ancho=150)
        self.dni.pack(side="left", padx=(12, 0))
        self.servicio = CampoLista(fila, "Servicio", valores=envios.SERVICIOS,
                                   ancho=130)
        self.servicio.pack(side="left", padx=(12, 0))
        self.servicio.poner(envios.SERVICIOS[0])
        self.destino = Campo(cuerpo, "Destino (ciudad y agencia, o dirección)",
                             ancho=460)
        self.destino.pack(fill="x", padx=18, pady=(0, 8))
        fila2 = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila2.pack(fill="x", padx=18, pady=(0, 8))
        self.guia = Campo(fila2, "N.º de guía (si ya lo tienes)", ancho=220)
        self.guia.pack(side="left")
        self.venta = Campo(fila2, "Venta (opcional)", ancho=220,
                           ayuda="Ej.: V-000012")
        if con_venta:
            self.venta.pack(side="left", padx=(12, 0))
        self.nota = Campo(cuerpo, "Nota (opcional)", ancho=460)
        self.nota.pack(fill="x", padx=18, pady=(0, 6))
        self.error = ctk.CTkLabel(cuerpo, text="", anchor="w", justify="left",
                                  text_color=e.COLOR_PELIGRO, wraplength=460)
        self.error.pack(fill="x", padx=18)
        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.pack(fill="x", padx=18, pady=(6, 16))
        boton(pie, "Guardar", self._aceptar, tipo="principal",
              ancho=130).pack(side="right", padx=(8, 0))
        boton(pie, "Cancelar", self._cerrar, tipo="secundario",
              ancho=110).pack(side="right")

        if envio:
            self.nombre.poner(envio["nombre"])
            self.telefono.poner(envio.get("telefono", ""))
            self.dni.poner(envio.get("dni", ""))
            self.servicio.poner(envio["servicio"])
            self.destino.poner(envio["destino"])
            self.guia.poner(envio.get("guia", ""))
            self.venta.poner(envio.get("venta", ""))
            self.nota.poner(envio.get("nota", ""))
        elif cliente is not None:            # sugerencia: se puede cambiar
            self.nombre.poner(cliente.nombre)
            self.telefono.poner(cliente.telefono)
            self.dni.poner(cliente.dni)
            self.destino.poner(cliente.direccion)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.bind("<Escape>", lambda _ev: self._cerrar())
        self._centrar(padre)
        (self.nombre if envio else self.buscar).foco()

    def _buscar(self):
        encontrados = clientes.buscar_clientes(self.buscar.obtener(), limite=30)
        self._clientes = {c.id: c for c in encontrados}
        self.lista.cargar([(c.id, (c.nombre, c.telefono, c.direccion), "")
                           for c in encontrados])

    def _elegir_cliente(self, id_):
        c = self._clientes.get(int(id_))
        if c is None:
            return
        self._cliente_id = c.id
        self.nombre.poner(c.nombre)
        self.telefono.poner(c.telefono)
        self.dni.poner(c.dni)
        self.destino.poner(c.direccion)      # sugerido: se puede cambiar
        self.destino.foco()

    def _aceptar(self):
        datos = {"cliente_id": self._cliente_id, "nombre": self.nombre.obtener(),
                 "telefono": self.telefono.obtener(), "dni": self.dni.obtener(),
                 "servicio": self.servicio.obtener(),
                 "destino": self.destino.obtener(), "guia": self.guia.obtener(),
                 "venta": self.venta.obtener(), "nota": self.nota.obtener()}
        if not self._con_venta:
            datos.pop("venta")
        try:     # se valida aquí para avisar sin cerrar la ventana
            envios.validar(datos)
        except ValueError as error:
            self.error.configure(text=str(error))
            return
        self.resultado = datos
        self._cerrar()

    def _cerrar(self):
        self.grab_release()
        self.destroy()

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


class PantallaEnvios(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._envio = None

        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(0, e.ESPACIO))
        self._total = TarjetaResumen(barra, "Envíos", "0")
        self._total.pack(side="left", padx=(0, e.ESPACIO))
        self.buscar = Campo(barra, "Buscar por nombre, destino, guía o venta",
                            ancho=320)
        self.buscar.pack(side="left", anchor="s")
        self.buscar.al_escribir(self.refrescar)
        boton(barra, "Nuevo envío", self._nuevo, tipo="principal",
              ancho=130).pack(side="right", anchor="s")

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=1)
        cuerpo.grid_columnconfigure(1, weight=0)
        cuerpo.grid_rowconfigure(0, weight=1)

        self.tabla = Tabla(cuerpo, COLUMNAS, alto=12)
        self.tabla.grid(row=0, column=0, sticky="nsew", padx=(0, e.ESPACIO))
        self.tabla.al_elegir(self._elegir)
        self.tabla.al_doble_clic(lambda _id: self._editar())

        self._panel = ctk.CTkFrame(cuerpo, width=440)
        self._panel.grid(row=0, column=1, sticky="ns")
        self._panel.grid_propagate(False)
        self._crear_panel()
        self.refrescar()

    # --------------------------------------------------------------- panel
    def _crear_panel(self):
        d = self._panel
        self._titulo = ctk.CTkLabel(
            d, text="Elige un cliente de la lista", anchor="w",
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._titulo.pack(fill="x", padx=14, pady=(12, 0))
        self._sub = ctk.CTkLabel(d, text="", anchor="w", justify="left",
                                 text_color=e.COLOR_TEXTO_SUAVE, wraplength=410)
        self._sub.pack(fill="x", padx=14)
        self.t_productos = Tabla(d, COLUMNAS_PRODUCTOS, alto=7)
        self.t_productos.pack(fill="x", padx=14, pady=(8, 6))
        self._total_venta = ctk.CTkLabel(d, text="", anchor="e",
                                         font=ctk.CTkFont(weight="bold"))
        self._total_venta.pack(fill="x", padx=14)
        self._nota = ctk.CTkLabel(d, text="", anchor="w", justify="left",
                                  text_color=e.COLOR_TEXTO_SUAVE, wraplength=410)
        self._nota.pack(fill="x", padx=14, pady=(6, 0))
        pie = ctk.CTkFrame(d, fg_color="transparent")
        pie.pack(side="bottom", fill="x", padx=14, pady=14)
        self.b_quitar = boton(pie, "Quitar", self._quitar, tipo="peligro",
                              ancho=100)
        self.b_quitar.pack(side="right")
        self.b_editar = boton(pie, "Editar", self._editar, tipo="secundario",
                              ancho=100)
        self.b_editar.pack(side="right", padx=(0, 8))
        self._botones(False)

    def _botones(self, activo):
        for b in (self.b_editar, self.b_quitar):
            b.configure(state="normal" if activo else "disabled")

    def _mostrar(self, env):
        self._envio = env
        self._botones(True)
        self._titulo.configure(text=env["nombre"])
        partes = [env["servicio"]]
        if env["telefono"]:
            partes.append(f"Tel. {env['telefono']}")
        if env["dni"]:
            partes.append(f"DNI {env['dni']}")
        sub = "  ·  ".join(partes) + f"\n{env['destino']}"
        if env["guia"]:
            sub += f"\nGuía: {env['guia']}"
        self._sub.configure(text=sub)
        self._nota.configure(text=f"Nota: {env['nota']}" if env["nota"] else "")
        venta = (anulaciones.detalle_venta(env["venta_id"])
                 if env["venta_id"] else None)
        if venta is None:
            self.t_productos.vaciar()
            self._total_venta.configure(text="")
            sin = "Este envío no está ligado a una venta."
            self._nota.configure(
                text=(self._nota.cget("text") + "\n" if env["nota"] else "") + sin)
            return
        self.t_productos.cargar([
            (l["id"], (l["nombre"], "Mayor" if l["tipo"] == "mayor" else "Unidad",
                       f"{l['cantidad']:g}", moneda(l["precio_unitario"]),
                       moneda(l["subtotal"])), "")
            for l in venta["lineas"]])
        self._total_venta.configure(
            text=f"Venta {venta['numero']} · Total {moneda(venta['total'])}")
        if venta["estado"] != "activa":
            self._nota.configure(
                text=(self._nota.cget("text") + "\n" if env["nota"] else "")
                + "OJO: esa venta fue anulada.")

    def _limpiar_panel(self):
        self._envio = None
        self._botones(False)
        self._titulo.configure(text="Elige un cliente de la lista")
        self._sub.configure(text="")
        self._nota.configure(text="")
        self._total_venta.configure(text="")
        self.t_productos.vaciar()

    def refrescar(self):
        """Vuelve a leer la lista (se llama al entrar a la pestaña)."""
        lista = envios.listar(self.buscar.obtener())
        elegido = self._envio["id"] if self._envio else None
        self.tabla.cargar([
            (f["id"], (fecha_corta(f["fecha"]), f["nombre"], f["servicio"],
                       f["destino"], f["guia"] or "—", f["venta"] or "—"), "")
            for f in lista])
        self._total.actualizar(str(envios.contar()))
        if elegido is not None and self.tabla.arbol.exists(str(elegido)):
            self.tabla.arbol.selection_set(str(elegido))
        else:
            self._limpiar_panel()

    # ------------------------------------------------------------ acciones
    def _elegir(self, id_):
        env = envios.obtener(int(id_))
        if env:
            self._mostrar(env)

    def _nuevo(self):
        dialogo = DialogoEnvio(self)
        self.wait_window(dialogo)
        if not dialogo.resultado:
            return
        try:
            id_ = envios.crear(dialogo.resultado)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error", 6)
            return
        self.alerta.mostrar("Envío registrado.", "ok", 5)
        self.buscar.limpiar()
        self._envio = {"id": id_}
        self.refrescar()
        self._elegir(id_)

    def _editar(self):
        if not self._envio:
            return
        dialogo = DialogoEnvio(self, self._envio)
        self.wait_window(dialogo)
        if not dialogo.resultado:
            return
        try:
            envios.actualizar(self._envio["id"], dialogo.resultado)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error", 6)
            return
        self.alerta.mostrar("Cambios guardados.", "ok", 4)
        self.refrescar()
        self._elegir(self._envio["id"])

    def _quitar(self):
        if not self._envio:
            return
        if not confirmar(self, "Quitar envío",
                         f"¿Quitar el envío de {self._envio['nombre']}? "
                         "Se borra de la lista (la venta no se toca).",
                         "Quitar", peligro=True):
            return
        try:
            envios.quitar(self._envio["id"])
        except ValueError as error:
            self.alerta.mostrar(str(error), "error", 6)
            return
        self._envio = None
        self.alerta.mostrar("Envío quitado.", "ok", 4)
        self.refrescar()