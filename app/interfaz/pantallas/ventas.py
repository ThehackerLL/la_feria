"""Pantalla Ventas: armar la venta y cobrarla.

Se busca el producto, se elige Unidad o Por mayor (el precio se llena solo y
se puede cambiar solo para esta venta), se pone la cantidad y se agrega a la
lista. La cantidad puede ir en unidades, docenas o paquetes: se convierte a
UNIDADES (el precio es siempre por unidad y el stock se descuenta en unidades). Abajo: cliente (opcional), descuento, forma de pago y COBRAR.
«A crédito» vende a un cliente guardado con abono inicial y cuotas.
Se puede poner una venta en espera (solo en memoria) para atender a otra
persona. Si el cliente pide envío, «Envío» guarda los datos antes de cobrar y
al cobrar queda en la pestaña Envíos, ligado a la venta. Atajos: F2 busca un
producto y F9 cobra.
"""
from datetime import datetime

import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import (Alerta, Campo, Tabla, _Dialogo, aviso,
                                      boton, confirmar)
from app.interfaz.dialogo_cliente import elegir_cliente
from app.interfaz.dialogo_credito import fecha_corta, plan_credito
from app.interfaz.indicadores_dia import FranjaIndicadores
from app.interfaz.pantallas.envios import DialogoEnvio
from app.servicios import clientes, envios, inventario, paquetes, ventas
from app.utilidades.formato import entero, moneda
from app.utilidades.validaciones import a_entero, a_numero

COLUMNAS_BUSQUEDA = [
    ("codigo", "Código", 70, "w"),
    ("nombre", "Producto", 120, "w", True),   # la que se estira
    ("stock", "Stock", 60, "e"),
    ("unidad", "Unidad", 70, "e"),
    ("mayor", "Mayor", 70, "e"),
]
COLUMNAS_LINEAS = [
    ("n", "#", 40, "center"),
    ("codigo", "Código", 80, "w"),
    ("nombre", "Producto", 180, "w", True),   # la que se estira
    ("tipo", "Tipo", 80, "w"),
    ("cantidad", "Cantidad", 110, "e"),
    ("precio", "Precio", 90, "e"),
    ("subtotal", "Subtotal", 100, "e"),
]
COLUMNAS_ESPERA = [
    ("hora", "Hora", 70, "w"),
    ("cliente", "Cliente", 200, "w", True),   # la que se estira
    ("productos", "Productos", 90, "e"),
    ("subtotal", "Subtotal", 110, "e"),
]
ETIQUETA_TIPO = {"unidad": "Unidad", "mayor": "Por mayor"}
MAX_BUSQUEDA = 60
UNIDADES, DOCENAS, PAQUETES = "Unidades", "Docenas", "Paquetes"
VENDE_EN = (UNIDADES, DOCENAS, PAQUETES)
TAMANO_DOCENA = 12
TAMANO_PAQUETE = "12"      # el que aparece de entrada; se puede cambiar
FILAS_LISTA, FILAS_LISTA_CORTA = 5, 2    # filas de la lista de productos
ALTO_MINIMO_LISTA_COMPLETA = 700         # por debajo, la lista se acorta
ABREVIATURA = {DOCENAS: "doc.", PAQUETES: "paq."}


class _ConfirmarCobro(_Dialogo):
    """«¿Cobrar esta venta?» Todavía NO se ha guardado nada: la X, Esc o
    Cancelar vuelven a la venta (para agregar otro producto, por ejemplo) y
    solo «Cobrar» (o Enter) la registra. Se lee .resultado: True = cobrar."""

    def __init__(self, padre, mensaje):
        super().__init__(padre, "¿Cobrar esta venta?", mensaje,
                         [("Cancelar", "secundario", False),
                          ("Cobrar", "ok", True)])
        self.bind("<Return>", lambda _ev: self._cerrar(True))


class _DialogoEspera(ctk.CTkToplevel):
    """Lista de ventas en espera: recuperar una o descartarla."""

    def __init__(self, padre, espera):
        super().__init__(padre)
        self.elegida = None            # posición de la venta a recuperar
        self._espera = espera          # se modifica si se descarta alguna
        self.title("Ventas en espera")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text="Ventas en espera", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(cuerpo, text="Elige la que quieres recuperar.", anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE
                     ).pack(fill="x", padx=18, pady=(0, 8))
        self._tabla = Tabla(cuerpo, COLUMNAS_ESPERA, alto=6)
        self._tabla.pack(fill="x", padx=18, pady=4)
        self._tabla.al_elegir(lambda _id: self._habilitar(True))
        self._tabla.al_doble_clic(lambda _id: self._recuperar())
        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.pack(fill="x", padx=18, pady=(8, 16))
        self._b_recuperar = boton(pie, "Recuperar", self._recuperar,
                                  "principal", ancho=120)
        self._b_recuperar.pack(side="right")
        self._b_descartar = boton(pie, "Descartar", self._descartar,
                                  "secundario", ancho=110)
        self._b_descartar.pack(side="right", padx=(0, 8))
        boton(pie, "Cerrar", self._cerrar, "secundario",
              ancho=90).pack(side="left")
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.bind("<Escape>", lambda _ev: self._cerrar())
        self._dibujar()
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

    def _habilitar(self, activo):
        estado = "normal" if activo else "disabled"
        self._b_recuperar.configure(state=estado)
        self._b_descartar.configure(state=estado)

    def _dibujar(self):
        self._tabla.cargar([
            (i, (v["hora"],
                 v["cliente"].nombre if v["cliente"] else clientes.PUBLICO_GENERAL,
                 sum(l["cantidad"] for l in v["lineas"]),
                 moneda(sum(l["cantidad"] * l["precio"] for l in v["lineas"]))),
             "")
            for i, v in enumerate(self._espera)])
        self._habilitar(False)

    def _recuperar(self):
        elegido = self._tabla.seleccionado()
        if elegido is not None:
            self.elegida = int(elegido)
            self._cerrar()

    def _descartar(self):
        elegido = self._tabla.seleccionado()
        if elegido is None:
            return
        if confirmar(self, "Descartar venta",
                     "Se borrará esta venta en espera. No se puede deshacer.",
                     texto_si="Descartar", peligro=True):
            del self._espera[int(elegido)]
            if not self._espera:
                self._cerrar()
            else:
                self._dibujar()

    def _cerrar(self):
        self.grab_release()
        self.destroy()


class PantallaVentas(ctk.CTkFrame):
    _precio_manual = False     # True si el usuario escribió el precio a mano
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._lineas = []          # líneas de la venta actual
        self._producto = None      # producto elegido en el buscador
        self._cliente = None       # None = Público general
        self._espera = []          # ventas en espera (solo en memoria)
        self._envio = None         # datos del envío de esta venta (None = sin envío)
        self._franja = FranjaIndicadores(self)     # venta, ganancia, efectivo, digital
        self._franja.pack(fill="x", pady=(0, e.ESPACIO - 4))
        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)
        self._crear_buscador(cuerpo)
        self._crear_venta(cuerpo)
        self._dibujar_lineas()
        self._buscar()
        self._mostrar_cliente()
        self._mostrar_envio()
        self._actualizar_espera()
        # Atajos: solo actúan cuando esta pestaña es la que se está viendo.
        ventana = self.winfo_toplevel()
        ventana.bind("<F2>", lambda _ev: self._atajo(self.f_buscar.foco),
                     add="+")
        ventana.bind("<F9>", lambda _ev: self._atajo(self._cobrar), add="+")

    def _atajo(self, accion):
        if self.winfo_ismapped():
            accion()

    # ---------------------------------------------------------------- buscador
    def _crear_buscador(self, cuerpo):
        panel = ctk.CTkFrame(cuerpo, width=470, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.grid(row=0, column=0, sticky="ns", padx=(0, e.MARGEN))
        panel.grid_propagate(False)
        panel.grid_columnconfigure((0, 1), weight=1, uniform="col")

        ctk.CTkLabel(panel, text="Agregar producto", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, sticky="ew",
                            padx=16, pady=(14, 6))

        self.f_buscar = Campo(panel, "Buscar por código o nombre (F2)",
                              ayuda="Escribe para filtrar")
        self.f_buscar.grid(row=1, column=0, columnspan=2, sticky="ew",
                           padx=16, pady=4)
        self.f_buscar.al_escribir(self._buscar)
        self.f_buscar.al_enter(self._elegir_primero)

        self._lista = Tabla(panel, COLUMNAS_BUSQUEDA, alto=FILAS_LISTA)
        # La barra de desplazamiento pide 200 px de alto: se acorta para que
        # la lista ocupe solo 5 filas y la franja de arriba quepa en pantallas bajas.
        for hijo in self._lista.winfo_children():
            if isinstance(hijo, ctk.CTkScrollbar):
                hijo.configure(height=60)
        self._lista.grid(row=2, column=0, columnspan=2, sticky="ew",
                         padx=16, pady=4)
        self._lista.al_elegir(self._elegir)

        self._elegido = ctk.CTkLabel(panel, text="", anchor="w", justify="left",
                                     wraplength=420,
                                     font=ctk.CTkFont(weight="bold"))
        self._elegido.grid(row=3, column=0, columnspan=2, sticky="ew",
                           padx=16, pady=(8, 2))

        # Unidad / Por mayor: el elegido se ve en azul, el otro en gris
        selector = ctk.CTkFrame(panel, fg_color="transparent")
        selector.grid(row=4, column=0, columnspan=2, sticky="ew", padx=16,
                      pady=4)
        selector.grid_columnconfigure((0, 1), weight=1, uniform="tipo")
        self._botones_tipo = {}
        for columna, tipo in enumerate(("unidad", "mayor")):
            b = boton(selector, ETIQUETA_TIPO[tipo],
                      lambda t=tipo: self._elegir_tipo(t), "secundario")
            b.grid(row=0, column=columna, sticky="ew",
                   padx=(0, 4) if columna == 0 else (4, 0))
            self._botones_tipo[tipo] = b
        self._tipo_elegido = "unidad"
        self._marcar_tipo()

        # Precio (siempre por unidad) · Cantidad · En qué llega: unidades, docenas o paquetes
        fila = ctk.CTkFrame(panel, fg_color="transparent")
        fila.grid(row=5, column=0, columnspan=2, sticky="ew", padx=16, pady=4)
        fila.grid_columnconfigure(0, weight=3, uniform="precio")
        fila.grid_columnconfigure(1, weight=2, uniform="precio")
        self.f_precio = Campo(fila, "Precio de esta venta", ayuda="0.00")
        self.f_cantidad = Campo(fila, "Cantidad", ayuda="1")
        self.f_precio.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.f_cantidad.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        marco_modo = ctk.CTkFrame(fila, fg_color="transparent")
        marco_modo.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(marco_modo, text="En", anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_PEQUENO)).pack(fill="x")
        self._modo = ctk.CTkOptionMenu(
            marco_modo, values=list(VENDE_EN), width=118, height=e.ALTO_CONTROL,
            font=ctk.CTkFont(weight="bold"),
            dropdown_font=ctk.CTkFont(size=e.TAM_TEXTO),
            command=lambda _valor: self._cambio_modo())
        self._modo.set(UNIDADES)
        self._modo.pack(pady=(2, 0))
        self.f_precio.al_enter(self._agregar)
        self.f_cantidad.al_enter(self._agregar)

        # Solo con docenas o paquetes: tamaño del paquete y resumen de la conversión
        self._fila_conversion = ctk.CTkFrame(panel, fg_color="transparent")
        self._fila_conversion.grid(row=6, column=0, columnspan=2, sticky="ew",
                                   padx=16, pady=(0, 2))
        self._fila_conversion.grid_columnconfigure(1, weight=1)
        self.f_tamano = Campo(self._fila_conversion, "Unidades por paquete",
                              ayuda="12", ancho=150)
        self.f_tamano.grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.f_tamano.al_enter(self._agregar)
        self._conversion = ctk.CTkLabel(
            self._fila_conversion, text="", anchor="w", justify="left",
            wraplength=300, text_color=e.COLOR_PRIMARIO,
            font=ctk.CTkFont(weight="bold"))
        self._conversion.grid(row=0, column=1, sticky="ew")
        self.f_precio.al_escribir(self._precio_escrito)
        self.f_cantidad.al_escribir(self._actualizar_conversion)
        self.f_tamano.al_escribir(self._tamano_escrito)
        self._fila_conversion.grid_remove()

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.grid(row=7, column=0, columnspan=2, sticky="ew", padx=16,
                     pady=(12, 16))
        boton(botones, "Agregar a la venta", self._agregar, "principal",
              ancho=190).pack(side="left")
        boton(botones, "Limpiar", self._limpiar_formulario, "secundario",
              ancho=90).pack(side="left", padx=8)

    # ------------------------------------------------ unidades / docenas / paquetes
    @staticmethod
    def _poner_etiqueta(campo, texto):
        """Cambia el título de un Campo (su etiqueta es lo primero que tiene)."""
        campo.winfo_children()[0].configure(text=texto)

    def _nombre_envase(self, cantidad=2):
        """'docena(s)' o 'paquete(s)' según lo elegido y la cantidad."""
        paquete = self._modo.get() == PAQUETES
        if cantidad == 1:
            return "paquete" if paquete else "docena"
        return "paquetes" if paquete else "docenas"

    def _tamano(self):
        """Unidades que trae cada docena/paquete (1 si es por unidades)."""
        modo = self._modo.get()
        if modo == DOCENAS:
            return TAMANO_DOCENA
        if modo == PAQUETES:
            return a_entero(self.f_tamano.obtener(), "Unidades por paquete",
                            minimo=1)
        return 1

    def _aplicar_modo(self):
        """Pone títulos, tamaño y resumen según lo elegido (no toca el precio)."""
        modo = self._modo.get()
        if modo == UNIDADES:
            self._poner_etiqueta(self.f_cantidad, "Cantidad")
            self._poner_etiqueta(self.f_precio, "Precio de esta venta")
            self._fila_conversion.grid_remove()
            self._lista.arbol.configure(height=FILAS_LISTA)
            return
        # Solo en ventanas bajas la lista se acorta (sigue ahí, con su filtro)
        # para que quepa el botón; en pantallas altas se queda como está.
        baja = self.winfo_height() < ALTO_MINIMO_LISTA_COMPLETA
        self._lista.arbol.configure(
            height=FILAS_LISTA_CORTA if baja else FILAS_LISTA)
        self._poner_etiqueta(self.f_cantidad, f"{modo}")
        self._poner_etiqueta(self.f_precio, f"Precio por {self._nombre_envase(1)}")
        if modo == PAQUETES:
            if not self.f_tamano.obtener():
                self.f_tamano.poner(TAMANO_PAQUETE)
            self.f_tamano.grid()
            self._conversion.grid(row=0, column=1, columnspan=1)
        else:
            self.f_tamano.grid_remove()
            self._conversion.grid(row=0, column=0, columnspan=2)
        self._fila_conversion.grid()
        self._actualizar_conversion()

    def _cambio_modo(self):
        """El usuario cambió «En»: docenas y paquetes se venden por mayor."""
        if self._modo.get() == PAQUETES:       # el paquete anotado en Compras, o 12
            guardado = (paquetes.obtener(self._producto.id)
                        if self._producto is not None else None)
            self.f_tamano.poner(guardado or TAMANO_PAQUETE)
        self._aplicar_modo()
        if self._producto is not None:
            self._tipo_elegido = "unidad" if self._modo.get() == UNIDADES else "mayor"
            self._marcar_tipo()
            self._poner_precio_sugerido()

    def _reiniciar_modo(self):
        self._modo.set(UNIDADES)
        self._aplicar_modo()

    def _actualizar_conversion(self):
        """Muestra, mientras escribes, cuántas unidades salen y cuánto cuesta."""
        if self._modo.get() == UNIDADES:
            return
        try:
            tamano = self._tamano()
            envases = a_entero(self.f_cantidad.obtener(), "Cantidad", minimo=0)
            precio = a_numero(self.f_precio.obtener(), "Precio")
        except ValueError:
            self._conversion.configure(text="")
            return
        if envases < 1:
            self._conversion.configure(text="")
            return
        texto = (f"{entero(envases)} {self._nombre_envase(envases)} × "
                 f"{entero(tamano)} = {entero(envases * tamano)} unidades")
        if precio > 0:
            texto += (f" · {moneda(precio / tamano)} cada una"
                      f" · total {moneda(round(envases * precio, 2))}")
        self._conversion.configure(text=texto)

    def _precio_escrito(self):
        self._precio_manual = True
        self._actualizar_conversion()

    def _tamano_escrito(self):
        """Cambió las unidades por paquete: el precio propuesto las acompaña."""
        if not self._precio_manual:
            self._poner_precio_sugerido()
        self._actualizar_conversion()

    @staticmethod
    def _texto_cantidad(linea):
        """'36' o, si se vendió por docenas/paquetes, '36 (3 doc.)'."""
        detalle = linea.get("detalle")
        if not detalle:
            return entero(linea["cantidad"])
        return (f"{entero(linea['cantidad'])} "
                f"({entero(detalle[1])} {ABREVIATURA[detalle[0]]})")

    def refrescar(self):
        """Se llama al abrir la pestaña: el stock pudo cambiar (Compras)."""
        if self._producto is not None:
            self._producto = inventario.obtener_producto(self._producto.id)
            if self._producto is None or not self._producto.activo:
                self._producto = None
        self._buscar()
        self._mostrar_elegido()
        self._franja.refrescar()

    def _buscar(self):
        texto = self.f_buscar.obtener()
        coincidencias = inventario.buscar_productos(texto)[:MAX_BUSQUEDA]
        self._lista.cargar([
            (p.id, (p.codigo, p.nombre, entero(p.stock),
                    moneda(p.precio_unidad), moneda(p.precio_mayor)),
             "peligro" if p.stock <= 0 else ("aviso" if p.bajo_stock else ""))
            for p in coincidencias])

    def _elegir_primero(self):
        """Enter en el buscador: elige la primera coincidencia (o la exacta)."""
        texto = self.f_buscar.obtener().upper()
        productos = inventario.buscar_productos(self.f_buscar.obtener())
        if not productos:
            return
        exacto = [p for p in productos if p.codigo == texto]
        self._tomar((exacto or productos)[0])

    def _elegir(self, id_):
        producto = inventario.obtener_producto(int(id_))
        if producto is not None:
            self._tomar(producto)

    def _tomar(self, producto):
        """Deja el producto listo para agregar."""
        if producto.stock <= 0:
            self.alerta.mostrar(f"{producto.nombre} está agotado: no hay "
                                "unidades para vender.", "error")
            self._producto = None
            self._mostrar_elegido()
            return
        self.alerta.ocultar()
        self._producto = producto
        self._mostrar_elegido()
        self._cambio_modo()      # respeta Unidades/Docenas/Paquetes ya elegido
        self.f_cantidad.poner("1")
        self.f_cantidad.foco()
        self.f_cantidad.caja.select_range(0, "end")

    def _en_la_venta(self, producto_id):
        """Unidades de este producto que ya están en la lista."""
        return sum(l["cantidad"] for l in self._lineas
                   if l["producto_id"] == producto_id)

    def _disponible(self):
        return self._producto.stock - self._en_la_venta(self._producto.id)

    def _mostrar_elegido(self):
        if self._producto is None:
            self._elegido.configure(
                text="Elige un producto de la lista.",
                text_color=e.COLOR_TEXTO_SUAVE)
            return
        p = self._producto
        libres = self._disponible()
        self._elegido.configure(
            text=f"{p.codigo} · {p.nombre}\nStock {entero(p.stock)}"
                 f" · disponible para esta venta: {entero(libres)}",
            text_color=e.COLOR_PRIMARIO)

    def _tipo_actual(self):
        return self._tipo_elegido

    def _marcar_tipo(self):
        """Pinta de azul el tipo elegido y de gris el otro."""
        for tipo, b in self._botones_tipo.items():
            activo = (tipo == self._tipo_elegido)
            fondo, hover, texto = (
                (e.COLOR_PRIMARIO, e.COLOR_PRIMARIO_HOVER, "#FFFFFF") if activo
                else (e.COLOR_NEUTRO, e.COLOR_NEUTRO_HOVER, e.COLOR_TEXTO))
            b.configure(fg_color=fondo, hover_color=hover, text_color=texto)

    def _elegir_tipo(self, tipo):
        self._tipo_elegido = tipo
        self._marcar_tipo()
        self._poner_precio_sugerido()

    def _poner_precio_sugerido(self):
        if self._producto is None:
            return
        precio = ventas.precio_sugerido(self._producto, self._tipo_actual())
        if self._modo.get() != UNIDADES:     # el precio es por paquete/docena
            try:
                precio = round(precio * self._tamano(), 2)
            except ValueError:
                return                        # tamaño aún inválido: no se toca
        self.f_precio.poner(f"{precio:.2f}")
        self._precio_manual = False

    def _limpiar_formulario(self):
        self._producto = None
        self.f_buscar.limpiar()
        self.f_precio.limpiar()
        self.f_cantidad.limpiar()
        self._reiniciar_modo()
        self._tipo_elegido = "unidad"
        self._marcar_tipo()
        self._buscar()
        self._lista.quitar_seleccion()
        self._mostrar_elegido()
        self.f_buscar.foco()

    # -------------------------------------------------------- lista de la venta
    def _crear_venta(self, cuerpo):
        derecha = ctk.CTkFrame(cuerpo, fg_color="transparent")
        derecha.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(derecha, text="Venta actual", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", pady=(0, e.ESPACIO))
        self.tabla = Tabla(derecha, COLUMNAS_LINEAS, alto=6)   # crece si hay espacio
        self.tabla.pack(fill="both", expand=True)
        self.tabla.al_elegir(lambda _id: self._boton_quitar.configure(
            state="normal"))

        pie = ctk.CTkFrame(derecha, border_width=1, border_color=e.COLOR_BORDE)
        pie.pack(fill="x", pady=(e.ESPACIO, 0))
        pie.grid_columnconfigure(2, weight=1)

        # Fila 0: cliente
        fila_cliente = ctk.CTkFrame(pie, fg_color="transparent")
        fila_cliente.grid(row=0, column=0, columnspan=3, sticky="ew",
                          padx=16, pady=(12, 4))
        ctk.CTkLabel(fila_cliente, text="Cliente:",
                     text_color=e.COLOR_TEXTO_SUAVE).pack(side="left")
        self._nombre_cliente = ctk.CTkLabel(fila_cliente, text="",
                                            font=ctk.CTkFont(weight="bold"))
        self._nombre_cliente.pack(side="left", padx=(8, 0))
        self._boton_cliente = boton(fila_cliente, "Elegir o crear cliente",
                                    self._elegir_cliente, "secundario",
                                    ancho=190)
        self._boton_cliente.pack(side="right")
        self._boton_sin_cliente = boton(fila_cliente, "Quitar",
                                        self._quitar_cliente, "secundario",
                                        ancho=80)

        # Fila 1: envío (opcional)
        fila_envio = ctk.CTkFrame(pie, fg_color="transparent")
        fila_envio.grid(row=1, column=0, columnspan=3, sticky="ew",
                        padx=16, pady=(0, 4))
        ctk.CTkLabel(fila_envio, text="Envío:",
                     text_color=e.COLOR_TEXTO_SUAVE).pack(side="left")
        self._texto_envio = ctk.CTkLabel(fila_envio, text="",
                                         font=ctk.CTkFont(weight="bold"))
        self._texto_envio.pack(side="left", padx=(8, 0))
        self._boton_envio = boton(fila_envio, "Envío", self._elegir_envio,
                                  "secundario", ancho=190)
        self._boton_envio.pack(side="right")
        self._boton_sin_envio = boton(fila_envio, "Quitar",
                                      self._quitar_envio, "secundario",
                                      ancho=80)

        # Fila 2: descuento, forma de pago y total
        self.f_descuento = Campo(pie, "Descuento en soles (opcional)",
                                 ancho=170, ayuda="0.00")
        self.f_descuento.grid(row=2, column=0, sticky="w", padx=(16, 8),
                              pady=(8, 4))
        self.f_descuento.al_escribir(self._recalcular)

        ctk.CTkLabel(pie, text="Forma de pago", anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_PEQUENO)
                     ).grid(row=2, column=1, sticky="nw", padx=(8, 8),
                            pady=(8, 0))
        self._pago = ctk.CTkOptionMenu(
            pie, values=list(ventas.FORMAS_PAGO), width=170,
            height=e.ALTO_CONTROL, font=ctk.CTkFont(weight="bold"),
            dropdown_font=ctk.CTkFont(size=e.TAM_TEXTO))
        self._pago.set(ventas.FORMAS_PAGO[0])
        self._pago.grid(row=2, column=1, sticky="sw", padx=(8, 8), pady=(0, 4))

        self._total = ctk.CTkLabel(pie, text=moneda(0), anchor="e",
                                   font=ctk.CTkFont(size=e.TAM_CIFRA,
                                                    weight="bold"))
        self._total.grid(row=2, column=2, sticky="e", padx=16, pady=(8, 0))

        # Fila 3: resumen (o el error del descuento, en rojo)
        self._resumen = ctk.CTkLabel(pie, text="", anchor="w",
                                     text_color=e.COLOR_TEXTO_SUAVE)
        self._resumen.grid(row=3, column=0, columnspan=3, sticky="w",
                           padx=16, pady=(0, 4))

        # Fila 4: botones
        acciones = ctk.CTkFrame(pie, fg_color="transparent")
        acciones.grid(row=4, column=0, columnspan=3, sticky="ew", padx=16,
                      pady=(4, 14))
        self._boton_quitar = boton(acciones, "Quitar línea",
                                   self._quitar_linea, "secundario", ancho=110)
        self._boton_quitar.pack(side="left")
        self._boton_cobrar = boton(acciones, "COBRAR  (F9)", self._cobrar,
                                   "ok", ancho=190)
        self._boton_cobrar.configure(height=44,
                                     font=ctk.CTkFont(size=e.TAM_SUBTITULO,
                                                      weight="bold"))
        self._boton_cobrar.pack(side="right")
        self._boton_credito = boton(acciones, "A crédito", self._a_credito,
                                    "principal", ancho=120)
        self._boton_credito.configure(height=44)
        self._boton_credito.pack(side="right", padx=(0, 8))
        self._boton_poner = boton(acciones, "Poner en espera",
                                  self._poner_en_espera, "secundario",
                                  ancho=150)
        self._boton_poner.pack(side="right", padx=(0, 8))
        self._boton_espera = boton(acciones, "", self._abrir_espera,
                                   "principal", ancho=130)


    def _dibujar_lineas(self):
        self.tabla.cargar([
            (i, (i + 1, l["codigo"], l["nombre"], ETIQUETA_TIPO[l["tipo"]],
                 self._texto_cantidad(l), moneda(l["precio"]),
                 moneda(l["cantidad"] * l["precio"])), "")
            for i, l in enumerate(self._lineas)])
        self._boton_quitar.configure(state="disabled")
        self._recalcular()

    def _subtotal(self):
        return round(sum(l["cantidad"] * l["precio"] for l in self._lineas), 2)

    def _recalcular(self):
        """Actualiza subtotal, descuento y total que se ven abajo."""
        subtotal = self._subtotal()
        unidades = sum(l["cantidad"] for l in self._lineas)
        error = ""
        try:
            descuento = a_numero(self.f_descuento.obtener(), "Descuento")
            if descuento > subtotal:
                raise ValueError("El descuento no puede ser mayor al subtotal "
                                 f"({moneda(subtotal)}).")
            total = round(subtotal - descuento, 2)
        except ValueError as problema:
            error = str(problema)
            descuento, total = 0, subtotal
        self._total.configure(text=moneda(total))
        if error:
            self._resumen.configure(text=error, text_color=e.COLOR_PELIGRO)
            return
        if self._lineas:
            extra = f" · descuento {moneda(descuento)}" if descuento else ""
            texto = (f"{len(self._lineas)} productos · {entero(unidades)} "
                     f"unidades · subtotal {moneda(subtotal)}{extra}")
        else:
            texto = "Todavía no agregaste productos"
        self._resumen.configure(text=texto, text_color=e.COLOR_TEXTO_SUAVE)

    # ------------------------------------------------------------------ acciones
    def _agregar(self):
        """Pasa el producto elegido a la lista de la venta."""
        try:
            if self._producto is None:
                raise ValueError("Primero elige un producto de la lista.")
            modo = self._modo.get()
            tamano = self._tamano()
            envases = a_entero(self.f_cantidad.obtener() or "1", "Cantidad",
                               minimo=1)
            if envases < 1:
                raise ValueError("Cantidad: debe ser al menos 1.")
            cantidad = envases * tamano                  # siempre en UNIDADES
            pedido = (f"{entero(cantidad)} unidades" if modo == UNIDADES else
                      f"{entero(cantidad)} unidades ({entero(envases)} "
                      f"{self._nombre_envase(envases)})")
            precio_escrito = a_numero(self.f_precio.obtener(), "Precio")
            if precio_escrito <= 0:
                raise ValueError("Precio: escribe el precio de esta venta.")
            # Se guarda por UNIDAD (exacto: S/ 100 la docena = 8.3333… c/u)
            precio = precio_escrito / tamano
            libres = self._disponible()
            if cantidad > libres:
                ya = self._en_la_venta(self._producto.id)
                detalle = (f" ({entero(ya)} ya están en la venta)"
                           if ya else "")
                raise ValueError(
                    f"{self._producto.nombre}: solo hay {entero(libres)} "
                    f"disponibles{detalle} y pediste {pedido}.")
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        p, tipo = self._producto, self._tipo_actual()
        detalle = None if modo == UNIDADES else (modo, envases, tamano)
        if modo == PAQUETES:       # si no estaba anotado, se recuerda (Compras manda)
            paquetes.guardar_si_falta(p.id, tamano)
        for linea in self._lineas:      # mismo producto, tipo y precio: suma
            if (linea["producto_id"], linea["tipo"], linea["precio"]) == (
                    p.id, tipo, precio):
                linea["cantidad"] += cantidad
                antes = linea.get("detalle")
                # Se conserva «3 doc.» solo si todo lo sumado fue en docenas/paquetes iguales
                if antes and detalle and antes[0] == modo and antes[2] == tamano:
                    linea["detalle"] = (modo, antes[1] + envases, tamano)
                else:
                    linea["detalle"] = None
                break
        else:
            self._lineas.append({
                "producto_id": p.id, "codigo": p.codigo, "nombre": p.nombre,
                "tipo": tipo, "cantidad": cantidad, "precio": precio,
                "detalle": detalle})
        if precio < p.costo:
            self.alerta.mostrar(
                f"Ojo: el precio de {p.nombre} está por debajo de su costo. "
                "Se agregó igual.", "aviso", segundos=8)
        elif modo != UNIDADES:
            self.alerta.mostrar(
                f"Agregado: {entero(envases)} {self._nombre_envase(envases)} × "
                f"{entero(tamano)} = {entero(cantidad)} unidades.", "ok")
        else:
            self.alerta.ocultar()
        self._dibujar_lineas()
        self._limpiar_formulario()

    def _quitar_linea(self):
        elegido = self.tabla.seleccionado()
        if elegido is None:
            return
        del self._lineas[int(elegido)]
        self._dibujar_lineas()
        self._mostrar_elegido()

    # ------------------------------------------------------------------ envío
    def _mostrar_envio(self):
        if self._envio is None:
            self._texto_envio.configure(text="Sin envío",
                                        text_color=e.COLOR_TEXTO_SUAVE)
            self._boton_envio.configure(text="Envío")
            self._boton_sin_envio.pack_forget()
        else:
            self._texto_envio.configure(
                text=f"{self._envio['servicio']} · {self._envio['nombre']}",
                text_color=e.COLOR_PRIMARIO)
            self._boton_envio.configure(text="Editar envío")
            self._boton_sin_envio.pack(side="right", padx=(0, 8),
                                       before=self._boton_envio)

    def _elegir_envio(self):
        """Pide los datos del envío. Se guarda al cobrar la venta."""
        dialogo = DialogoEnvio(self, self._envio, cliente=self._cliente,
                               con_venta=False)
        self.wait_window(dialogo)
        if dialogo.resultado:
            self._envio = dialogo.resultado
            self._mostrar_envio()
            self.alerta.mostrar("Envío anotado. Se registra al cobrar la venta.",
                                "ok", segundos=4)

    def _quitar_envio(self):
        self._envio = None
        self._mostrar_envio()

    def _guardar_envio(self, numero_venta):
        """Registra el envío ligado a la venta recién cobrada.

        Devuelve None si todo salió bien (o no había envío), o el motivo si no
        se pudo guardar (la venta ya está guardada de todos modos).
        """
        if self._envio is None:
            return None
        try:
            envios.crear(dict(self._envio, venta=numero_venta))
        except ValueError as error:
            return str(error)
        return None

    # ------------------------------------------------------------------ cliente
    def _mostrar_cliente(self):
        if self._cliente is None:
            self._nombre_cliente.configure(text=clientes.PUBLICO_GENERAL,
                                           text_color=e.COLOR_TEXTO_SUAVE)
            self._boton_sin_cliente.pack_forget()
        else:
            self._nombre_cliente.configure(
                text=f"{self._cliente.nombre} · {self._cliente.telefono}",
                text_color=e.COLOR_PRIMARIO)
            self._boton_sin_cliente.pack(side="right", padx=(0, 8),
                                         before=self._boton_cliente)

    def _elegir_cliente(self):
        cliente = elegir_cliente(self)
        if cliente is not None:
            self._cliente = cliente
            self._mostrar_cliente()

    def _quitar_cliente(self):
        self._cliente = None
        self._mostrar_cliente()

    # ------------------------------------------------------------------ cobrar
    def datos_venta(self):
        """Lo que necesita ventas.registrar_venta: items, descuento y forma
        de pago elegida."""
        items = [{k: l[k] for k in ("producto_id", "cantidad", "tipo", "precio")}
                 for l in self._lineas]
        return items, self.f_descuento.obtener(), self._pago.get()

    def _limpiar_venta(self):
        """Deja la pantalla lista para la siguiente venta."""
        self._lineas.clear()
        self._cliente = None
        self._envio = None
        self.f_descuento.limpiar()
        self._pago.set(ventas.FORMAS_PAGO[0])
        self._mostrar_cliente()
        self._mostrar_envio()
        self._dibujar_lineas()
        self._limpiar_formulario()

    def _cobrar(self):
        """Guarda la venta: descuenta el stock y deja todo listo para otra."""
        items, texto_descuento, forma = self.datos_venta()
        try:
            if not items:
                raise ValueError("Agrega al menos un producto a la venta.")
            descuento = a_numero(texto_descuento, "Descuento")
            total = ventas.calcular_totales(
                ventas.leer_lineas(items), descuento)["total"]
            if total <= 0:
                raise ValueError("El total no puede ser 0: el descuento cubre "
                                 "todo el subtotal.")
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        # Antes de guardar se pregunta: X, Esc o Cancelar no registran nada y la
        # venta sigue en pantalla (por si se adelantó y falta un producto).
        cliente = self._cliente.nombre if self._cliente else clientes.PUBLICO_GENERAL
        unidades = sum(int(i["cantidad"]) for i in items)
        resumen = [f"Total: {moneda(total)}"]
        if descuento:
            resumen.append(f"Descuento: {moneda(descuento)}")
        resumen += [f"Forma de pago: {forma}", f"Cliente: {cliente}"]
        if self._envio:
            resumen.append(f"Envío: {self._envio['servicio']} a "
                           f"{self._envio['nombre']}")
        resumen += [
                    f"{len(items)} {'producto' if len(items) == 1 else 'productos'}"
                    f" · {entero(unidades)} {'unidad' if unidades == 1 else 'unidades'}",
                    "", " "]
        if not self._confirmar_cobro("\n".join(resumen)):
            self.f_buscar.foco()
            return
        try:
            resultado = ventas.registrar_venta(
                items, [{"forma_pago": forma, "monto": total}],
                cliente_id=self._cliente.id if self._cliente else None,
                descuento=descuento)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            self.refrescar()           # el stock pudo haber cambiado
            return
        con_envio = self._envio is not None
        fallo_envio = self._guardar_envio(resultado["numero"])
        self._limpiar_venta()
        self._franja.refrescar()
        # Ya está guardada: un mensaje que se quita solo, sin botón que confunda.
        mensaje = (f"Venta {resultado['numero']} registrada · Total "
                   f"{moneda(resultado['total'])} · {forma} · {resultado['cliente']}")
        if fallo_envio:
            self.alerta.mostrar(
                f"{mensaje}. PERO el envío no se guardó ({fallo_envio}) "
                "Regístralo en la pestaña Envíos.", "aviso", segundos=12)
        else:
            self.alerta.mostrar(mensaje + (" · envío registrado" if con_envio
                                           else ""), "ok", segundos=6)
        if resultado["stock_bajo"]:
            lineas = ["Stock bajo:"]
            for p in resultado["stock_bajo"]:
                cuando = ("se agotó" if p["stock"] <= 0
                          else f"quedan {entero(p['stock'])}")
                lineas.append(f"• {p['nombre']}: {cuando}")
            aviso(self, "Stock bajo", "\n".join(lineas))
        self.f_buscar.foco()

    def _confirmar_cobro(self, mensaje):
        """True si el usuario confirma el cobro (Cobrar o Enter)."""
        dialogo = _ConfirmarCobro(self, mensaje)
        self.wait_window(dialogo)
        return dialogo.resultado

    def _a_credito(self):
        """Vende a crédito: abono inicial (puede ser 0) y el resto en cuotas.

        Solo para clientes guardados: si no hay uno elegido, se pide.
        """
        items, texto_descuento, forma = self.datos_venta()
        try:
            if not items:
                raise ValueError("Agrega al menos un producto a la venta.")
            descuento = a_numero(texto_descuento, "Descuento")
            total = ventas.calcular_totales(
                ventas.leer_lineas(items), descuento)["total"]
            if total <= 0:
                raise ValueError("El total no puede ser 0: el descuento cubre "
                                 "todo el subtotal.")
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        if self._cliente is None:
            self._elegir_cliente()
            if self._cliente is None:
                self.alerta.mostrar(
                    "Para vender a crédito elige un cliente guardado (nombre "
                    "y teléfono).", "error")
                return
        self.alerta.ocultar()
        plan = plan_credito(self, total, self._cliente, forma)
        if plan is None:
            return
        pagos = ([{"forma_pago": plan["forma"], "monto": plan["abono"]}]
                 if plan["abono"] > 0 else [])
        try:
            resultado = ventas.registrar_venta(
                items, pagos, cliente_id=self._cliente.id,
                descuento=descuento,
                credito={"cuotas": plan["cuotas"], "dias": plan["dias"]})
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            self.refrescar()           # el stock pudo haber cambiado
            return
        con_envio = self._envio is not None
        fallo_envio = self._guardar_envio(resultado["numero"])
        self._limpiar_venta()
        self.alerta.ocultar()
        credito = resultado["credito"]
        lineas = [f"Cliente: {resultado['cliente']}",
                  f"Total: {moneda(resultado['total'])}",
                  f"Abono inicial: {moneda(credito['abono'])}"
                  + (f" ({plan['forma']})" if credito["abono"] else ""),
                  f"Queda por pagar: {moneda(credito['saldo'])}", "",
                  "Cuotas:"]
        for c in credito["cuotas"]:
            lineas.append(f"• {c['numero']}. {fecha_corta(c['vence'])}: "
                          f"{moneda(c['monto'])}")
        if fallo_envio:
            lineas += ["", f"OJO: el envío no se guardó ({fallo_envio}). "
                       "Regístralo en la pestaña Envíos."]
        elif con_envio:
            lineas += ["", "Envío registrado en la pestaña Envíos."]
        if resultado["stock_bajo"]:
            lineas.append("")
            lineas.append("Stock bajo:")
            for p in resultado["stock_bajo"]:
                cuando = ("se agotó" if p["stock"] <= 0
                          else f"quedan {entero(p['stock'])}")
                lineas.append(f"• {p['nombre']}: {cuando}")
        self._franja.refrescar()
        aviso(self, f"Venta a crédito {resultado['numero']} registrada",
              "\n".join(lineas))
        self.f_buscar.foco()

    # ------------------------------------------------------------ venta en espera
    def tiene_pendientes(self):
        """True si hay una venta armada o ventas en espera (se perderían al
        cerrar el programa)."""
        return bool(self._lineas or self._espera)

    def _estado_actual(self):
        return {"lineas": [dict(l) for l in self._lineas],
                "cliente": self._cliente, "envio": self._envio,
                "descuento": self.f_descuento.obtener(),
                "pago": self._pago.get(),
                "hora": datetime.now().strftime("%H:%M")}

    def _cargar_estado(self, estado):
        self._lineas = [dict(l) for l in estado["lineas"]]
        self._cliente = estado["cliente"]
        self._envio = estado.get("envio")
        self.f_descuento.poner(estado["descuento"])
        self._pago.set(estado["pago"])
        self._mostrar_cliente()
        self._mostrar_envio()
        self._dibujar_lineas()
        self._limpiar_formulario()

    def _actualizar_espera(self):
        """Muestra el botón «En espera (n)» solo si hay ventas guardadas."""
        if self._espera:
            self._boton_espera.configure(text=f"En espera ({len(self._espera)})")
            self._boton_espera.pack(side="right", padx=(0, 8),
                                    before=self._boton_poner)
        else:
            self._boton_espera.pack_forget()

    def _poner_en_espera(self):
        if not self._lineas:
            self.alerta.mostrar("No hay nada que poner en espera: agrega "
                                "productos primero.", "error")
            return
        self._espera.append(self._estado_actual())
        self._limpiar_venta()
        self._actualizar_espera()
        self.alerta.mostrar("Venta puesta en espera. La recuperas con el botón "
                            "«En espera».", "ok")

    def _abrir_espera(self):
        if not self._espera:
            return
        dialogo = _DialogoEspera(self, self._espera)
        self.wait_window(dialogo)
        self._actualizar_espera()
        if dialogo.elegida is None:
            return
        actual = self._estado_actual() if self._lineas else None
        if actual and not confirmar(
                self, "Venta en curso",
                "Tienes una venta armada. Se pondrá en espera para recuperar "
                "la otra.", texto_si="Cambiar"):
            return
        estado = self._espera.pop(dialogo.elegida)
        if actual:
            self._espera.append(actual)
        self._actualizar_espera()
        self._cargar_estado(estado)
        self.alerta.ocultar()