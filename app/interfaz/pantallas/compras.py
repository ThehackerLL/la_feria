"""Pantalla Compras: registrar la mercadería que llega.

Si el producto ya existe se SUMA el stock y se recalcula el costo promedio.
Si no existe, se crea. El proveedor es opcional al contado y obligatorio a
crédito (hay que saber a quién se le debe): se marca en la lista y se
acepta, o se crea uno nuevo. Se paga al contado (con su forma de pago) o a
crédito (en cuotas).

La mercadería puede llegar en unidades, paquetes o docenas: aquí se convierte
a UNIDADES (lo que se vende) y el resto del programa solo conoce unidades.
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import (Alerta, Campo, CampoLista, Tabla, aviso,
                                      boton)
from app.interfaz.dialogo_credito import fecha_corta, plan_credito
from app.interfaz.dialogo_proveedor import crear_proveedor_nuevo
from app.servicios import compras, inventario, paquetes, proveedores
from app.utilidades.formato import entero, moneda
from app.utilidades.validaciones import a_entero, a_numero

COLUMNAS_LINEAS = [
    ("n", "#", 40, "center"),
    ("codigo", "Código", 90, "w"),
    ("nombre", "Producto", 180, "w", True),   # la que se estira
    ("accion", "Qué pasa", 90, "w"),
    ("cantidad", "Cantidad", 80, "e"),
    ("costo", "Costo unid.", 100, "e"),
    ("subtotal", "Subtotal", 110, "e"),
]
COLUMNAS_SUGERENCIAS = [
    ("codigo", "Código", 80, "w"),
    ("nombre", "Producto", 160, "w", True),
    ("stock", "Stock", 60, "e"),
]
COLUMNAS_PROVEEDORES = [
    ("nombre", "Nombre", 170, "w", True),   # la que se estira
    ("telefono", "Teléfono", 100, "w"),
    ("rubro", "Rubro", 150, "w"),
]
MAX_SUGERENCIAS = 5
UNIDADES, PAQUETES, DOCENAS = "Unidades", "Paquetes", "Docenas"
LLEGA_EN = (UNIDADES, PAQUETES, DOCENAS)
TAMANO_DOCENA = 12
TAMANO_PAQUETE = "12"      # el que aparece de entrada; se puede cambiar
ANCHO_PANEL = 580          # columna izquierda con la ventana bien ancha
ANCHO_PANEL_MIN = 470      # y lo mínimo, con la ventana más angosta
PROPORCION_PANEL = 0.36    # parte del ancho de la ventana que ocupa


class PantallaCompras(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._lineas = []          # productos agregados a la compra actual
        self._mostrar_sugerencias = True
        self._proveedor = None     # el Proveedor elegido para esta compra
        self._tamano_de = None     # producto cuyo paquete ya se propuso solo
        self._ancho = ANCHO_PANEL_MIN
        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)
        # Columna izquierda con barra de desplazamiento: en pantallas bajas
        # (laptops) el formulario no cabe entero junto a los proveedores.
        self._izquierda = ctk.CTkScrollableFrame(
            cuerpo, fg_color="transparent", width=self._ancho)
        self._izquierda.grid(row=0, column=0, sticky="ns", padx=(0, e.MARGEN))
        izquierda = self._izquierda
        self._crear_proveedores(izquierda)
        self._crear_formulario(izquierda)
        self._crear_compra(cuerpo)
        self._limpiar_formulario()
        self._dibujar_lineas()
        self.bind("<Configure>", self._ajustar_ancho)

    def _ajustar_ancho(self, _evento=None):
        """La columna izquierda crece con la ventana (sin pasar de su tope) y
        deja el resto a la lista de la compra, para que nada quede cortado."""
        ancho = self.winfo_width() / self._get_widget_scaling()
        nuevo = int(max(ANCHO_PANEL_MIN, min(ANCHO_PANEL,
                                             ancho * PROPORCION_PANEL)))
        if nuevo != self._ancho:
            self._ancho = nuevo
            self._izquierda.configure(width=nuevo)
            self._lbl_proveedor.configure(wraplength=nuevo - 60)

    # ------------------------------------------------------------ proveedores
    def _crear_proveedores(self, cuerpo):
        panel = ctk.CTkFrame(cuerpo, width=self._ancho, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.pack(fill="x")

        cabecera = ctk.CTkFrame(panel, fg_color="transparent")
        cabecera.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(cabecera, text="Añadir proveedor", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(side="left")
        boton(cabecera, "Crear proveedor", self._crear_proveedor, "principal",
              ancho=140).pack(side="right")

        self.f_buscar = Campo(panel, "Buscar por nombre, teléfono o rubro",
                              ayuda="Escribe para filtrar")
        self.f_buscar.pack(fill="x", padx=16, pady=4)
        self.f_buscar.al_escribir(self._buscar_proveedores)

        self._lista = Tabla(panel, COLUMNAS_PROVEEDORES, alto=4)
        self._lista.pack(fill="x", padx=16, pady=4)
        self._lista.al_doble_clic(lambda _id: self._aceptar_proveedor())

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.pack(fill="x", padx=16, pady=(6, 4))
        boton(botones, "Aceptar proveedor", self._aceptar_proveedor,
              "principal", ancho=150).pack(side="left")
        boton(botones, "A crédito", self._a_credito, "principal",
              ancho=100).pack(side="left", padx=8)
        boton(botones, "Quitar proveedor", self._quitar_proveedor,
              "secundario", ancho=140).pack(side="left")

        self._lbl_proveedor = ctk.CTkLabel(
            panel, text="", anchor="w", justify="left", wraplength=self._ancho - 60,
            font=ctk.CTkFont(weight="bold"))
        self._lbl_proveedor.pack(fill="x", padx=16, pady=(4, 14))
        self._buscar_proveedores()
        self._mostrar_proveedor()

    # ------------------------------------------------------------- formulario
    def _crear_formulario(self, cuerpo):
        panel = ctk.CTkFrame(cuerpo, width=self._ancho, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.pack(fill="x", pady=(e.ESPACIO, 0))
        panel.grid_columnconfigure((0, 1), weight=1, uniform="col")

        ctk.CTkLabel(panel, text="Agregar producto", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, sticky="ew",
                            padx=16, pady=(14, 6))

        self.f_nombre = Campo(panel, "Producto", ayuda="Escribe para buscar")
        self.f_nombre.grid(row=1, column=0, columnspan=2, sticky="ew",
                           padx=16, pady=4)
        self.f_codigo = Campo(panel, "Código", ayuda="Opcional")
        self.f_categoria = CampoLista(panel, "Categoría")
        self.f_codigo.grid(row=2, column=0, sticky="ew", padx=(16, 6), pady=4)
        self.f_categoria.grid(row=2, column=1, sticky="ew", padx=(6, 16),
                              pady=4)

        # Coincidencias del inventario (solo se ven cuando hay)
        self._sugerencias = Tabla(panel, COLUMNAS_SUGERENCIAS,
                                  alto=MAX_SUGERENCIAS)
        self._sugerencias.grid(row=3, column=0, columnspan=2, sticky="ew",
                               padx=16, pady=4)
        self._sugerencias.grid_remove()
        self._sugerencias.al_elegir(self._elegir_sugerencia)

        self._estado = ctk.CTkLabel(panel, text="", anchor="w", justify="left",
                                    wraplength=340,
                                    font=ctk.CTkFont(weight="bold"))
        self._estado.grid(row=4, column=0, columnspan=2, sticky="ew",
                          padx=16, pady=(4, 2))

        # Cómo llegó la mercadería: unidades, paquetes o docenas
        marco_modo = ctk.CTkFrame(panel, fg_color="transparent")
        marco_modo.grid(row=5, column=0, sticky="ew", padx=(16, 6), pady=4)
        ctk.CTkLabel(marco_modo, text="Llegó en", anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_PEQUENO)).pack(fill="x")
        self._modo = ctk.CTkOptionMenu(
            marco_modo, values=list(LLEGA_EN), height=e.ALTO_CONTROL,
            font=ctk.CTkFont(weight="bold"),
            dropdown_font=ctk.CTkFont(size=e.TAM_TEXTO),
            command=lambda _valor: self._cambio_modo())
        self._modo.set(UNIDADES)
        self._modo.pack(fill="x", pady=(2, 0))
        self.f_tamano = Campo(panel, "Unidades por paquete", ayuda="12")
        self.f_tamano.grid(row=5, column=1, sticky="ew", padx=(6, 16), pady=4)
        self.f_tamano.grid_remove()              # solo se ve con «Paquetes»

        self.f_cantidad = Campo(panel, "Cantidad que llegó", ayuda="0")
        self.f_costo = Campo(panel, "Costo por unidad", ayuda="0.00")
        self.f_unidad = Campo(panel, "Precio unidad", ayuda="0.00")
        self.f_mayor = Campo(panel, "Precio por mayor", ayuda="0.00")
        pares = [(self.f_cantidad, self.f_costo), (self.f_unidad, self.f_mayor)]
        for fila, (izq, der) in enumerate(pares, start=6):
            izq.grid(row=fila, column=0, sticky="ew", padx=(16, 6), pady=4)
            der.grid(row=fila, column=1, sticky="ew", padx=(6, 16), pady=4)

        # Resumen de la conversión (solo con paquetes o docenas)
        self._conversion = ctk.CTkLabel(
            panel, text="", anchor="w", justify="left", wraplength=340,
            text_color=e.COLOR_PRIMARIO, font=ctk.CTkFont(weight="bold"))
        self._conversion.grid(row=8, column=0, columnspan=2, sticky="ew",
                              padx=16, pady=(4, 2))
        self._conversion.grid_remove()

        for campo in (self.f_cantidad, self.f_costo, self.f_unidad,
                      self.f_mayor, self.f_tamano):
            campo.al_enter(self._agregar)
        for campo in (self.f_cantidad, self.f_costo, self.f_tamano):
            campo.al_escribir(self._actualizar_conversion)
        self.f_nombre.al_escribir(self._al_escribir)
        self.f_codigo.al_escribir(self._al_escribir)

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.grid(row=9, column=0, columnspan=2, sticky="ew", padx=16,
                     pady=(12, 16))
        boton(botones, "Agregar a la compra", self._agregar, "principal",
              ancho=190).pack(side="left")
        boton(botones, "Limpiar", self._limpiar_formulario, "secundario",
              ancho=90).pack(side="left", padx=8)

    def _limpiar_formulario(self):
        for campo in (self.f_nombre, self.f_codigo, self.f_categoria,
                      self.f_cantidad, self.f_costo, self.f_unidad,
                      self.f_mayor):
            campo.limpiar()
        self._sugerencias.grid_remove()
        self._estado.configure(text="")
        self._tamano_de = None
        if self._modo.get() == PAQUETES:        # cada producto trae el suyo
            self.f_tamano.poner(TAMANO_PAQUETE)
        self._actualizar_conversion()
        self.f_nombre.foco()

    # ------------------------------------------------ unidades / paquetes / docenas
    @staticmethod
    def _poner_etiqueta(campo, texto):
        """Cambia el título de un Campo (su etiqueta es lo primero que tiene)."""
        campo.winfo_children()[0].configure(text=texto)

    def _nombre_envase(self, cantidad=2):
        """'paquete(s)' o 'docena(s)' según lo elegido y la cantidad."""
        paquete = self._modo.get() == PAQUETES
        if cantidad == 1:
            return "paquete" if paquete else "docena"
        return "paquetes" if paquete else "docenas"

    def _cambio_modo(self):
        modo = self._modo.get()
        if modo == UNIDADES:
            self._poner_etiqueta(self.f_cantidad, "Cantidad que llegó")
            self._poner_etiqueta(self.f_costo, "Costo por unidad")
        else:
            nombre = self._nombre_envase()
            self._poner_etiqueta(self.f_cantidad, f"Cantidad de {nombre}")
            self._poner_etiqueta(self.f_costo, f"Costo por {self._nombre_envase(1)}")
        if modo == PAQUETES:
            if not self.f_tamano.obtener():
                self.f_tamano.poner(TAMANO_PAQUETE)
            self._proponer_paquete()
            self.f_tamano.grid()
        else:
            self.f_tamano.grid_remove()
        self._actualizar_conversion()

    def _paquete_guardado(self):
        """Unidades por paquete que ya se anotaron del producto escrito, o None."""
        existente = self._buscar_existente() if (
            self.f_nombre.obtener() or self.f_codigo.obtener()) else None
        return paquetes.obtener(existente.id) if existente else None

    def _proponer_paquete(self):
        """Si el producto ya tenía su paquete anotado, lo pone solo."""
        if self._modo.get() != PAQUETES:
            return
        existente = self._buscar_existente() if (
            self.f_nombre.obtener() or self.f_codigo.obtener()) else None
        if existente is None or self._tamano_de == existente.id:
            return
        self._tamano_de = existente.id
        guardado = paquetes.obtener(existente.id)
        if guardado:
            self.f_tamano.poner(guardado)

    def _tamano(self):
        """Unidades que trae cada paquete/docena (1 si llegó en unidades)."""
        modo = self._modo.get()
        if modo == DOCENAS:
            return TAMANO_DOCENA
        if modo == PAQUETES:
            tamano = a_entero(self.f_tamano.obtener(), "Unidades por paquete",
                              minimo=1)
            if tamano < 1:
                raise ValueError("Unidades por paquete: escribe cuántas "
                                 "unidades trae cada paquete.")
            return tamano
        return 1

    def _actualizar_conversion(self):
        """Muestra, mientras escribes, cuántas unidades entran y a qué costo."""
        if self._modo.get() == UNIDADES:
            self._conversion.grid_remove()
            return
        try:
            tamano = self._tamano()
            envases = a_entero(self.f_cantidad.obtener(), "Cantidad", minimo=0)
            costo = a_numero(self.f_costo.obtener(), "Costo")
        except ValueError:
            self._conversion.grid_remove()
            return
        if envases < 1:
            self._conversion.grid_remove()
            return
        texto = (f"{entero(envases)} {self._nombre_envase(envases)} × "
                 f"{entero(tamano)} = {entero(envases * tamano)} unidades")
        if costo > 0:
            texto += (f" · {moneda(costo / tamano)} cada una"
                      f" · total {moneda(envases * costo)}")
        guardado = self._paquete_guardado() if self._modo.get() == PAQUETES else None
        if guardado and guardado != tamano:
            texto += f"\nOjo: este producto tenía paquete de {entero(guardado)}."
        self._conversion.configure(text=texto)
        self._conversion.grid()

    def refrescar(self):
        """Se llama al abrir la pestaña: actualiza las categorías."""
        self.f_categoria.cambiar_valores(inventario.listar_categorias())
        self._buscar_proveedores()

    # ------------------------------------------------------- búsqueda y estado
    def _al_escribir(self):
        self._mostrar_sugerencias = True
        self._actualizar_estado()

    def _buscar_existente(self):
        return inventario.buscar_existente(
            self.f_codigo.obtener(), self.f_nombre.obtener(),
            incluir_inactivos=True)

    def _actualizar_estado(self):
        """Dice qué va a pasar con lo que está escrito y sugiere productos."""
        nombre, codigo = self.f_nombre.obtener(), self.f_codigo.obtener()
        existente = self._buscar_existente() if (nombre or codigo) else None
        self._proponer_paquete()
        self._actualizar_conversion()
        if existente:
            extra = "" if existente.activo else " (estaba quitado, se reactivará)"
            self._estado.configure(
                text=f"Ya existe {existente.codigo}{extra}: stock actual "
                     f"{entero(existente.stock)}. Se SUMARÁN las unidades.",
                text_color=e.COLOR_PRIMARIO)
        elif nombre:
            self._estado.configure(
                text="Producto nuevo: se creará al registrar la compra.",
                text_color=e.COLOR_OK)
        else:
            self._estado.configure(text="")

        texto = nombre or codigo
        coincidencias = []
        if self._mostrar_sugerencias and len(texto) >= 2:
            coincidencias = inventario.buscar_productos(texto)[:MAX_SUGERENCIAS]
        if coincidencias:
            self._sugerencias.cargar([
                (p.id, (p.codigo, p.nombre, entero(p.stock)), "")
                for p in coincidencias])
            self._sugerencias.grid()
        else:
            self._sugerencias.grid_remove()

    def _elegir_sugerencia(self, id_):
        """Rellena el formulario con el producto elegido de la lista."""
        producto = inventario.obtener_producto(int(id_))
        if producto is None:
            return
        self._mostrar_sugerencias = False
        self.f_nombre.poner(producto.nombre)
        self.f_codigo.poner(producto.codigo)
        self.f_categoria.poner(producto.categoria)
        if self._modo.get() == UNIDADES:      # con paquetes, el costo es por paquete
            self.f_costo.poner(self._texto_numero(producto.costo))
        self.f_unidad.poner(self._texto_numero(producto.precio_unidad))
        self.f_mayor.poner(self._texto_numero(producto.precio_mayor))
        self._actualizar_estado()
        self.f_cantidad.foco()

    @staticmethod
    def _texto_numero(valor):
        return f"{valor:.2f}".rstrip("0").rstrip(".")

    # ---------------------------------------------------------- lista de compra
    def _crear_compra(self, cuerpo):
        derecha = ctk.CTkFrame(cuerpo, fg_color="transparent")
        derecha.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(derecha, text="Lista de la compra", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", pady=(0, e.ESPACIO))
        self.tabla = Tabla(derecha, COLUMNAS_LINEAS, alto=12)
        self.tabla.pack(fill="both", expand=True)
        self.tabla.al_elegir(lambda _id: self._boton_quitar.configure(
            state="normal"))

        pie = ctk.CTkFrame(derecha, border_width=1, border_color=e.COLOR_BORDE)
        pie.pack(fill="x", pady=(e.ESPACIO, 0))
        pie.grid_columnconfigure(1, weight=1)
        pie.grid_columnconfigure(2, weight=1)

        # Cómo se paga (solo en compra al contado)
        marco_forma = ctk.CTkFrame(pie, fg_color="transparent")
        marco_forma.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(16, 8),
                         pady=(12, 4))
        ctk.CTkLabel(marco_forma, text="Pagado por", anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_PEQUENO)).pack(fill="x")
        self._forma = ctk.CTkOptionMenu(
            marco_forma, values=list(compras.FORMAS_PAGO_COMPRA), width=150,
            height=e.ALTO_CONTROL, font=ctk.CTkFont(weight="bold"),
            dropdown_font=ctk.CTkFont(size=e.TAM_TEXTO))
        self._forma.set(compras.FORMAS_PAGO_COMPRA[0])
        self._forma.pack(pady=(2, 0))

        self._total = ctk.CTkLabel(pie, text=moneda(0), anchor="e",
                                   font=ctk.CTkFont(size=e.TAM_CIFRA,
                                                    weight="bold"))
        self._total.grid(row=0, column=2, sticky="e", padx=16, pady=(12, 0))
        self._resumen = ctk.CTkLabel(pie, text="", anchor="e",
                                     text_color=e.COLOR_TEXTO_SUAVE)
        self._resumen.grid(row=1, column=2, sticky="e", padx=16, pady=(0, 4))

        botones = ctk.CTkFrame(pie, fg_color="transparent")
        botones.grid(row=2, column=0, columnspan=3, sticky="e", padx=16,
                     pady=(4, 14))
        self._boton_quitar = boton(botones, "Quitar línea", self._quitar_linea,
                                   "secundario", ancho=110)
        self._boton_quitar.pack(side="left", padx=(0, 8))
        self._boton_registrar = boton(botones, "Registrar compra",
                                      self._registrar, "ok", ancho=170)
        self._boton_registrar.pack(side="left")

    def _dibujar_lineas(self):
        filas = []
        for i, linea in enumerate(self._lineas):
            filas.append((i, (
                i + 1, linea["codigo"] or "(automático)", linea["nombre"],
                "Nuevo" if linea["accion"] == "nuevo" else "Suma stock",
                entero(linea["cantidad"]), moneda(linea["costo"]),
                moneda(linea["cantidad"] * linea["costo"])), ""))
        self.tabla.cargar(filas)
        total = sum(l["cantidad"] * l["costo"] for l in self._lineas)
        unidades = sum(l["cantidad"] for l in self._lineas)
        self._total.configure(text=moneda(total))
        self._resumen.configure(
            text=f"{len(self._lineas)} productos · {entero(unidades)} unidades"
            if self._lineas else "Todavía no agregaste productos")
        self._boton_quitar.configure(state="disabled")
        self._boton_registrar.configure(
            state="normal" if self._lineas else "disabled")

    # ------------------------------------------------------------------ acciones
    def _agregar(self):
        """Pasa lo escrito en el formulario a la lista de la compra."""
        try:
            nombre = " ".join(self.f_nombre.obtener().split())
            codigo = self.f_codigo.obtener().upper()
            if not nombre and not codigo:
                raise ValueError("Escribe el nombre o el código del producto.")
            modo = self._modo.get()
            tamano = self._tamano()
            if not self.f_cantidad.obtener():
                raise ValueError(
                    "Cantidad: escribe cuántas unidades llegaron." if modo == UNIDADES
                    else f"Cantidad: escribe cuántos {self._nombre_envase()} llegaron.")
            envases = a_entero(self.f_cantidad.obtener(), "Cantidad", minimo=1)
            cantidad = envases * tamano                  # siempre en UNIDADES
            costo_escrito = a_numero(self.f_costo.obtener(), "Costo")
            # Costo por unidad exacto (100 por 12 = 8.3333…): así el total de la
            # compra coincide con lo que se paga.
            costo = costo_escrito / tamano
            unidad = a_numero(self.f_unidad.obtener(), "Precio unidad")
            mayor = a_numero(self.f_mayor.obtener(), "Precio por mayor")
            conocido = self._producto_conocido(codigo, nombre)
            if conocido is None:
                if not nombre:
                    raise ValueError("Ese código no existe. Escribe también "
                                     "el nombre para crear el producto.")
                if not self.f_categoria.obtener():
                    raise ValueError("Producto nuevo: escribe su categoría.")
                if costo <= 0:
                    raise ValueError("Producto nuevo: escribe el costo por "
                                     "unidad.")
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        self.alerta.ocultar()
        if conocido is None:
            linea_codigo, linea_nombre, accion = codigo, nombre, "nuevo"
        else:
            linea_codigo, linea_nombre, accion = (
                conocido["codigo"], conocido["nombre"], "suma")
            if costo <= 0:
                costo = conocido["costo"]       # costo vacío: usa el actual
        self._lineas.append({
            "codigo": linea_codigo, "nombre": linea_nombre,
            "categoria": self.f_categoria.obtener(),
            "cantidad": cantidad, "costo": costo,
            "precio_unidad": unidad, "precio_mayor": mayor, "accion": accion,
            "tamano_paquete": tamano if modo == PAQUETES else None})
        self._dibujar_lineas()
        self._limpiar_formulario()
        if modo != UNIDADES:
            self.alerta.mostrar(
                f"Agregado: {entero(envases)} {self._nombre_envase(envases)} × "
                f"{entero(tamano)} = {entero(cantidad)} unidades.", "ok")

    def _producto_conocido(self, codigo, nombre):
        """Datos del producto si ya existe en el inventario o ya está en la
        lista de esta compra; None si es nuevo."""
        existente = inventario.buscar_existente(codigo, nombre,
                                                incluir_inactivos=True)
        if existente:
            return {"codigo": existente.codigo, "nombre": existente.nombre,
                    "costo": existente.costo}
        return self._buscar_en_lineas(codigo, nombre)

    def _buscar_en_lineas(self, codigo, nombre):
        """Si el mismo producto ya está en la lista, lo reutiliza."""
        clave = inventario.normalizar(nombre)
        for linea in self._lineas:
            if (codigo and linea["codigo"] == codigo) or (
                    clave and inventario.normalizar(linea["nombre"]) == clave):
                return linea
        return None

    def _quitar_linea(self):
        elegido = self.tabla.seleccionado()
        if elegido is None:
            return
        del self._lineas[int(elegido)]
        self._dibujar_lineas()

    # ---------------------------------------------------------------- proveedor
    def _buscar_proveedores(self):
        """Llena la lista con los proveedores que coinciden con la búsqueda."""
        encontrados = proveedores.buscar_proveedores(self.f_buscar.obtener(),
                                                     limite=50)
        self._lista.cargar([(p.id, (p.nombre, p.telefono or "—",
                                    p.vende or "—"), "")
                            for p in encontrados])

    def _marcado(self):
        """El proveedor marcado en la lista, o None."""
        id_ = self._lista.seleccionado()
        return proveedores.obtener_proveedor(int(id_)) if id_ else None

    def _mostrar_proveedor(self):
        if self._proveedor is None:
            self._lbl_proveedor.configure(
                text="Sin proveedor (opcional al contado). Para elegir uno, "
                     "márcalo en la lista y pulsa Aceptar proveedor.",
                text_color=e.COLOR_TEXTO_SUAVE)
        else:
            self._lbl_proveedor.configure(
                text=f"Proveedor elegido: {self._proveedor.nombre} · "
                     f"{self._proveedor.telefono}", text_color=e.COLOR_OK)

    def _elegir(self, proveedor):
        self._proveedor = proveedor
        self._mostrar_proveedor()
        self.alerta.ocultar()

    def _aceptar_proveedor(self):
        proveedor = self._marcado()
        if proveedor is None:
            self.alerta.mostrar("Marca un proveedor de la lista.", "error")
            return
        self._elegir(proveedor)

    def _quitar_proveedor(self):
        """Deja la compra sin proveedor (no borra al proveedor guardado)."""
        self._proveedor = None
        self._lista.quitar_seleccion()
        self._mostrar_proveedor()

    def _crear_proveedor(self):
        nuevo = crear_proveedor_nuevo(self)
        if nuevo is not None:
            self._buscar_proveedores()
            self._elegir(nuevo)

    def _exigir_proveedor(self):
        """A crédito hace falta un proveedor: hay que saber a quién se le debe."""
        if self._proveedor is not None:
            return True
        self.alerta.mostrar("Para comprar a crédito elige un proveedor: "
                            "márcalo en la lista (o crea uno nuevo).", "error")
        return False

    # ------------------------------------------------------------- registrar
    def _items(self):
        return [{k: l[k] for k in ("codigo", "nombre", "categoria", "cantidad",
                                   "costo", "precio_unidad", "precio_mayor")}
                for l in self._lineas]

    def _registrar(self):
        """Compra al contado: se paga todo al recibir, con la forma elegida.
        El proveedor es opcional."""
        items = self._items()
        proveedor_id = self._proveedor.id if self._proveedor else None
        forma = self._forma.get()
        try:
            total = compras.total_compra(items)
            resultado = compras.registrar_compra(
                items, pagos=[{"forma_pago": forma, "monto": total}],
                proveedor_id=proveedor_id)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        self._terminar(resultado, f"Pagado por {forma}.")

    def _a_credito(self):
        """Compra a crédito: abono al recibir (puede ser 0) y el resto en
        cuotas con fechas."""
        if not self._lineas:
            self.alerta.mostrar("Agrega productos a la compra primero.",
                                "error")
            return
        marcado = self._marcado()
        if marcado is not None:        # lo marcado en la lista se acepta solo
            self._elegir(marcado)
        if not self._exigir_proveedor():
            return
        items = self._items()
        try:
            total = compras.total_compra(items)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        if total <= 0:
            self.alerta.mostrar("El total de la compra es 0: escribe el costo "
                                "de los productos.", "error")
            return
        plan = plan_credito(self, total, self._proveedor, self._forma.get(),
                            compra=True)
        if plan is None:
            return
        pagos = ([{"forma_pago": plan["forma"], "monto": plan["abono"]}]
                 if plan["abono"] > 0 else [])
        try:
            resultado = compras.registrar_compra(
                items, pagos=pagos, proveedor_id=self._proveedor.id,
                credito={"cuotas": plan["cuotas"], "dias": plan["dias"]})
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        credito = resultado["credito"]
        cuotas = credito["cuotas"]
        pago = (f"Pagado al recibir {moneda(credito['abono'])} por "
                f"{plan['forma']}. " if credito["abono"] > 0
                else "No se pagó nada al recibir. ")
        self._terminar(
            resultado,
            f"{pago}Quedan {moneda(credito['saldo'])} por pagar en "
            f"{len(cuotas)} {'cuota' if len(cuotas) == 1 else 'cuotas'}; la "
            f"primera vence el {fecha_corta(cuotas[0]['vence'])}.")

    def _terminar(self, resultado, texto_pago):
        """Limpia la pantalla y cuenta cómo quedó la compra."""
        proveedor = self._proveedor
        for linea, hecha in zip(self._lineas, resultado["lineas"]):
            if linea.get("tamano_paquete"):        # recuerda el paquete del producto
                producto = inventario.buscar_existente(hecha["codigo"], "")
                if producto is not None:
                    paquetes.guardar(producto.id, linea["tamano_paquete"])
        self._lineas.clear()
        self._dibujar_lineas()
        self._quitar_proveedor()
        self.f_buscar.limpiar()
        self._buscar_proveedores()
        self._forma.set(compras.FORMAS_PAGO_COMPRA[0])
        self._modo.set(UNIDADES)
        self._cambio_modo()
        self._limpiar_formulario()
        self.refrescar()
        a_quien = f" a {proveedor.nombre}" if proveedor else ""
        self.alerta.mostrar(
            f"Compra registrada por {moneda(resultado['total'])}{a_quien}. "
            f"{texto_pago}", "ok", segundos=10)
        detalle = []
        for l in resultado["lineas"][:8]:
            if l["accion"] == "creado":
                detalle.append(f"• {l['codigo']} {l['nombre']}: nuevo, "
                               f"stock {entero(l['stock_despues'])}")
            else:
                detalle.append(
                    f"• {l['codigo']} {l['nombre']}: stock "
                    f"{entero(l['stock_antes'])} → {entero(l['stock_despues'])}"
                    f", costo {moneda(l['costo_antes'])} → "
                    f"{moneda(l['costo_despues'])}")
        if len(resultado["lineas"]) > 8:
            detalle.append(f"… y {len(resultado['lineas']) - 8} más")
        detalle.append("")
        detalle.append(f"Proveedor: {proveedor.nombre} · {proveedor.telefono}"
                       if proveedor else "Proveedor: sin proveedor")
        detalle.append(texto_pago)
        aviso(self, "Compra registrada", "\n".join(detalle))