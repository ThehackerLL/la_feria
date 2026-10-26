"""Pantalla Inventario: resumen, búsqueda, tabla y formulario de productos."""
import customtkinter as ctk

from app import config
from app.interfaz import estilos as e
from app.interfaz.componentes import (Alerta, Campo, CampoLista, Tabla,
                                      TarjetaResumen, boton, confirmar)
from app.servicios import inventario
from app.utilidades.formato import entero, moneda
from app.utilidades.validaciones import a_entero, a_numero

COLUMNAS = [
    ("codigo", "Código", 80, "w"),
    ("categoria", "Categoría", 110, "w"),
    ("nombre", "Producto", 160, "w", True),   # la que se estira
    ("costo", "Costo", 85, "e"),
    ("unidad", "P. unidad", 90, "e"),
    ("mayor", "P. mayor", 90, "e"),
    ("stock", "Stock", 60, "e"),
    ("valor", "Valor stock", 110, "e"),
]


class PantallaProductos(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._crear_resumen()
        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")
        self._cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self._cuerpo.pack(fill="both", expand=True)
        self._cuerpo.grid_columnconfigure(0, weight=1)
        self._cuerpo.grid_rowconfigure(0, weight=1)
        self._crear_lista()
        self._crear_formulario()
        self.tabla.al_elegir(self._cargar_en_formulario)
        self._producto_id = None          # None = producto nuevo
        self.nuevo()
        self.refrescar()

    # ---------------------------------------------------------------- resumen
    def _crear_resumen(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._tarjetas = {}
        for i, (clave, titulo) in enumerate([
                ("productos", "Productos"), ("unidades", "Unidades en stock"),
                ("valor", "Valor del stock (a costo)"),
                ("bajo", "Con stock bajo")]):
            fila.grid_columnconfigure(i, weight=1, uniform="tarjeta")
            tarjeta = TarjetaResumen(fila, titulo)
            tarjeta.grid(row=0, column=i, sticky="ew",
                         padx=(0 if i == 0 else e.ESPACIO // 2,
                               0 if i == 3 else e.ESPACIO // 2))
            self._tarjetas[clave] = tarjeta

    # ------------------------------------------------------------------ lista
    def _crear_lista(self):
        izquierda = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        izquierda.grid(row=0, column=0, sticky="nsew")

        barra = ctk.CTkFrame(izquierda, fg_color="transparent")
        barra.pack(fill="x", pady=(0, e.ESPACIO))
        self.buscador = Campo(barra, "Buscar", ancho=320,
                              ayuda="Código, nombre o categoría")
        self.buscador.pack(side="left")
        self.buscador.al_escribir(self.refrescar)
        self._solo_bajo = ctk.CTkCheckBox(
            barra, text="Solo stock bajo", command=self.refrescar)
        self._solo_bajo.pack(side="left", padx=e.MARGEN, pady=(18, 0))
        self._contador = ctk.CTkLabel(barra, text="",
                                      text_color=e.COLOR_TEXTO_SUAVE)
        self._contador.pack(side="right", pady=(18, 0))

        self.tabla = Tabla(izquierda, COLUMNAS, alto=14)
        self.tabla.pack(fill="both", expand=True)

    # --------------------------------------------------------------- refrescar
    def refrescar(self):
        """Vuelve a leer la base de datos y dibuja resumen y tabla."""
        resumen = inventario.resumen_stock()
        self._tarjetas["productos"].actualizar(entero(resumen["productos"]))
        self._tarjetas["unidades"].actualizar(entero(resumen["unidades"]))
        self._tarjetas["valor"].actualizar(moneda(resumen["valor"]))
        self._tarjetas["bajo"].actualizar(
            entero(resumen["bajo_stock"]),
            e.COLOR_AVISO if resumen["bajo_stock"] else None)

        productos = inventario.buscar_productos(
            self.buscador.obtener(), solo_bajo_stock=bool(self._solo_bajo.get()))
        filas = []
        for p in productos:
            estado = "peligro" if p.stock == 0 else (
                "aviso" if p.bajo_stock else "")
            filas.append((p.id, (
                p.codigo, p.categoria, p.nombre, moneda(p.costo),
                moneda(p.precio_unidad), moneda(p.precio_mayor),
                entero(p.stock), moneda(p.valor_stock)), estado))
        seleccionado = self.tabla.seleccionado()
        self.tabla.cargar(filas)
        if seleccionado is not None and self.tabla.arbol.exists(seleccionado):
            self.tabla.arbol.selection_set(seleccionado)
        self._contador.configure(
            text=f"Mostrando {len(filas)} de {resumen['productos']}")

    # ------------------------------------------------------------- formulario
    def _crear_formulario(self):
        panel = ctk.CTkFrame(self._cuerpo, width=360, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.grid(row=0, column=1, sticky="ns", padx=(e.MARGEN, 0))
        panel.grid_propagate(False)
        panel.grid_columnconfigure((0, 1), weight=1, uniform="col")

        self._titulo_form = ctk.CTkLabel(
            panel, text="", anchor="w",
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._titulo_form.grid(row=0, column=0, columnspan=2, sticky="ew",
                               padx=16, pady=(14, 6))

        self.f_categoria = CampoLista(panel, "Categoría")
        self.f_categoria.grid(row=1, column=0, columnspan=2, sticky="ew",
                              padx=16, pady=4)
        self.f_nombre = Campo(panel, "Producto")
        self.f_nombre.grid(row=2, column=0, columnspan=2, sticky="ew",
                           padx=16, pady=4)
        self.f_codigo = Campo(panel, "Código", ayuda="Automático")
        self.f_costo = Campo(panel, "Costo", ayuda="0.00")
        self.f_unidad = Campo(panel, "Precio unidad", ayuda="0.00")
        self.f_mayor = Campo(panel, "Precio por mayor", ayuda="0.00")
        self.f_stock = Campo(panel, "Stock", ayuda="0")
        self.f_minimo = Campo(panel, "Stock mínimo", ayuda="12")
        pares = [(self.f_codigo, self.f_minimo), (self.f_costo, self.f_unidad),
                 (self.f_mayor, self.f_stock)]
        for fila, (izq, der) in enumerate(pares, start=3):
            izq.grid(row=fila, column=0, sticky="ew", padx=(16, 6), pady=4)
            der.grid(row=fila, column=1, sticky="ew", padx=(6, 16), pady=4)

        self._campos = [self.f_nombre, self.f_codigo, self.f_costo,
                        self.f_unidad, self.f_mayor, self.f_stock,
                        self.f_minimo]
        for campo in self._campos:
            campo.al_enter(self.guardar)

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.grid(row=6, column=0, columnspan=2, sticky="ew",
                     padx=16, pady=(14, 0))
        boton(botones, "Guardar", self.guardar, "ok", ancho=110
              ).pack(side="left")
        boton(botones, "Nuevo", self.nuevo, "secundario", ancho=90
              ).pack(side="left", padx=8)
        self._boton_quitar = boton(botones, "Quitar", self.quitar, "peligro",
                                   ancho=90)
        self._boton_quitar.pack(side="right")

    def _actualizar_categorias(self):
        self.f_categoria.cambiar_valores(inventario.listar_categorias())

    @staticmethod
    def _texto_numero(valor):
        """18.0 -> '18', 12.5 -> '12.5' (como lo escribiría una persona)."""
        return f"{valor:.2f}".rstrip("0").rstrip(".")

    def nuevo(self):
        """Deja el formulario vacío para crear un producto."""
        self._producto_id = None
        self.tabla.quitar_seleccion()
        self._titulo_form.configure(text="Nuevo producto")
        self._actualizar_categorias()
        self.f_categoria.limpiar()
        for campo in self._campos:
            campo.limpiar()
        self.f_minimo.poner(config.STOCK_MINIMO_DEFECTO)
        self._boton_quitar.configure(state="disabled")
        self.f_nombre.foco()

    def _cargar_en_formulario(self, id_):
        """Se llama al elegir una fila de la tabla."""
        producto = inventario.obtener_producto(int(id_))
        if producto is None:
            return
        self._producto_id = producto.id
        self.alerta.ocultar()
        self._titulo_form.configure(text=f"Editando {producto.codigo}")
        self._actualizar_categorias()
        self.f_categoria.poner(producto.categoria)
        self.f_nombre.poner(producto.nombre)
        self.f_codigo.poner(producto.codigo)
        self.f_costo.poner(self._texto_numero(producto.costo))
        self.f_unidad.poner(self._texto_numero(producto.precio_unidad))
        self.f_mayor.poner(self._texto_numero(producto.precio_mayor))
        self.f_stock.poner(producto.stock)
        self.f_minimo.poner(producto.stock_minimo)
        self._boton_quitar.configure(state="normal")

    def guardar(self):
        """Crea el producto, o guarda los cambios si se está editando uno."""
        try:
            datos = dict(
                nombre=self.f_nombre.obtener(),
                categoria=self.f_categoria.obtener(),
                costo=a_numero(self.f_costo.obtener(), "Costo"),
                precio_unidad=a_numero(self.f_unidad.obtener(), "Precio unidad"),
                precio_mayor=a_numero(self.f_mayor.obtener(), "Precio por mayor"),
                stock=a_entero(self.f_stock.obtener(), "Stock"),
                stock_minimo=a_entero(self.f_minimo.obtener(), "Stock mínimo"),
                codigo=self.f_codigo.obtener())
            if self._producto_id is None:
                producto = inventario.crear_producto(**datos)
                verbo = "creado"
            else:
                producto = inventario.actualizar_producto(
                    self._producto_id, **datos)
                verbo = "actualizado"
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        self.nuevo()
        self.refrescar()
        self.alerta.mostrar(
            f"Producto {verbo}: {producto.codigo} - {producto.nombre}", "ok")

    def quitar(self):
        """Quita el producto elegido del inventario (queda oculto)."""
        if self._producto_id is None:
            return
        nombre = self.f_nombre.obtener()
        if not confirmar(
                self, "Quitar producto",
                f"¿Quitar \"{nombre}\" del inventario?\n"
                "Si lo vuelves a comprar, reaparece con su código.",
                texto_si="Quitar", peligro=True):
            return
        inventario.desactivar_producto(self._producto_id)
        self.nuevo()
        self.refrescar()
        self.alerta.mostrar(f"Producto quitado: {nombre}", "ok")