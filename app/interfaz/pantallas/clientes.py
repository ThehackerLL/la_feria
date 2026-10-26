"""Pantalla Clientes: los clientes guardados y el ranking de quién compró más.

Un cliente solo se guarda con nombre Y teléfono juntos (DNI y dirección son
opcionales).
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import (Alerta, Campo, Tabla, TarjetaResumen,
                                      boton, confirmar)
from app.servicios import clientes
from app.servicios.ranking_clientes import ranking_clientes
from app.utilidades.formato import entero, moneda

# Nombre y Dirección se estiran juntas cuando la ventana es ancha.
COLUMNAS = [
    ("puesto", "Puesto", 65, "center"),
    ("nombre", "Nombre", 150, "w", True),
    ("direccion", "Dirección", 130, "w", True),
    ("dni", "DNI", 80, "w"),
    ("telefono", "Teléfono", 95, "w"),
    ("compras", "Compras", 70, "e"),
    ("total", "Total comprado", 110, "e"),
    ("ultima", "Última compra", 105, "e"),
]


def _fecha(texto):
    """'2026-10-17 15:04:45' -> '17/10/2026'. Sin fecha: '—'."""
    if not texto:
        return "—"
    dia = str(texto)[:10].split("-")
    return f"{dia[2]}/{dia[1]}/{dia[0]}" if len(dia) == 3 else str(texto)


class PantallaClientes(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._cliente_id = None          # None = cliente nuevo
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
        self.nuevo()
        self.refrescar()

    # ---------------------------------------------------------------- resumen
    def _crear_resumen(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._tarjetas = {}
        for i, (clave, titulo) in enumerate([
                ("guardados", "Clientes guardados"),
                ("con_compras", "Con compras"),
                ("total", "Total comprado por todos")]):
            fila.grid_columnconfigure(i, weight=1, uniform="tarjeta")
            tarjeta = TarjetaResumen(fila, titulo)
            tarjeta.grid(row=0, column=i, sticky="ew",
                         padx=(0 if i == 0 else e.ESPACIO // 2,
                               0 if i == 2 else e.ESPACIO // 2))
            self._tarjetas[clave] = tarjeta

    # ------------------------------------------------------------------ lista
    def _crear_lista(self):
        izquierda = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        izquierda.grid(row=0, column=0, sticky="nsew")

        barra = ctk.CTkFrame(izquierda, fg_color="transparent")
        barra.pack(fill="x", pady=(0, e.ESPACIO))
        self.buscador = Campo(barra, "Buscar", ancho=320,
                              ayuda="Nombre, teléfono, DNI o dirección")
        self.buscador.pack(side="left")
        self.buscador.al_escribir(self.refrescar)
        self._contador = ctk.CTkLabel(barra, text="",
                                      text_color=e.COLOR_TEXTO_SUAVE)
        self._contador.pack(side="right", pady=(18, 0))

        self.tabla = Tabla(izquierda, COLUMNAS, alto=14)
        self.tabla.pack(fill="both", expand=True)

    # --------------------------------------------------------------- refrescar
    def refrescar(self):
        """Vuelve a leer la base de datos y dibuja resumen y tabla."""
        todos = ranking_clientes()
        texto = self.buscador.obtener()
        mostrados = ranking_clientes(texto) if texto else todos
        con_compras = [c for c in todos if c["compras"] > 0]
        self._tarjetas["guardados"].actualizar(entero(len(todos)))
        self._tarjetas["con_compras"].actualizar(entero(len(con_compras)))
        self._tarjetas["total"].actualizar(
            moneda(sum(c["total"] for c in todos)))

        filas = [(c["id"], (
            c["puesto"] if c["puesto"] else "—", c["nombre"],
            c["direccion"] or "—", c["dni"] or "—",
            c["telefono"] or "—", entero(c["compras"]), moneda(c["total"]),
            _fecha(c["ultima"])), "") for c in mostrados]
        seleccionado = self.tabla.seleccionado()
        self.tabla.cargar(filas)
        if seleccionado is not None and self.tabla.arbol.exists(seleccionado):
            self.tabla.arbol.selection_set(seleccionado)
        if not todos:
            self._contador.configure(text="Todavía no hay clientes guardados")
        else:
            self._contador.configure(
                text=f"Mostrando {len(filas)} de {len(todos)}")

    # ------------------------------------------------------------- formulario
    def _crear_formulario(self):
        panel = ctk.CTkFrame(self._cuerpo, width=360, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.grid(row=0, column=1, sticky="ns", padx=(e.MARGEN, 0))
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)

        self._titulo_form = ctk.CTkLabel(
            panel, text="", anchor="w",
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._titulo_form.grid(row=0, column=0, sticky="ew", padx=16,
                               pady=(14, 6))

        self.f_nombre = Campo(panel, "Nombre", ayuda="Nombre y apellido")
        self.f_nombre.grid(row=1, column=0, sticky="ew", padx=16, pady=4)
        self.f_telefono = Campo(panel, "Teléfono", ayuda="999111222")
        self.f_telefono.grid(row=2, column=0, sticky="ew", padx=16, pady=4)
        self.f_dni = Campo(panel, "DNI (opcional)", ayuda="8 números")
        self.f_dni.grid(row=3, column=0, sticky="ew", padx=16, pady=4)
        self.f_direccion = Campo(panel, "Dirección (opcional)",
                                 ayuda="Ciudad, calle…")
        self.f_direccion.grid(row=4, column=0, sticky="ew", padx=16, pady=4)
        for campo in (self.f_nombre, self.f_telefono):
            campo.al_escribir(self._revisar)
        for campo in (self.f_nombre, self.f_telefono, self.f_dni,
                      self.f_direccion):
            campo.al_enter(self.guardar)

        self._nota = ctk.CTkLabel(
            panel, text="", anchor="w", justify="left", wraplength=320,
            font=ctk.CTkFont(weight="bold"))
        self._nota.grid(row=5, column=0, sticky="ew", padx=16, pady=(2, 0))

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.grid(row=6, column=0, sticky="ew", padx=16, pady=(14, 0))
        self._boton_guardar = boton(botones, "Guardar", self.guardar, "ok",
                                    ancho=110)
        self._boton_guardar.pack(side="left")
        boton(botones, "Nuevo", self.nuevo, "secundario", ancho=90
              ).pack(side="left", padx=8)
        self._boton_quitar = boton(botones, "Quitar", self.quitar, "peligro",
                                   ancho=90)
        self._boton_quitar.pack(side="right")

    def _revisar(self):
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

    def nuevo(self):
        """Deja el formulario vacío para crear un cliente."""
        self._cliente_id = None
        self.tabla.quitar_seleccion()
        self._titulo_form.configure(text="Nuevo cliente")
        self.f_nombre.limpiar()
        self.f_telefono.limpiar()
        self.f_dni.limpiar()
        self.f_direccion.limpiar()
        self._boton_quitar.configure(state="disabled")
        self._revisar()
        self.f_nombre.foco()

    def _cargar_en_formulario(self, id_):
        """Se llama al elegir una fila de la tabla."""
        cliente = clientes.obtener_cliente(int(id_))
        if cliente is None:
            return
        self._cliente_id = cliente.id
        self.alerta.ocultar()
        self._titulo_form.configure(text="Editando cliente")
        self.f_nombre.poner(cliente.nombre)
        self.f_telefono.poner(cliente.telefono)
        self.f_dni.poner(cliente.dni)
        self.f_direccion.poner(cliente.direccion)
        self._boton_quitar.configure(state="normal")
        self._revisar()

    def guardar(self):
        """Crea el cliente, o guarda los cambios si se está editando uno."""
        if not (self.f_nombre.obtener() and self.f_telefono.obtener()):
            return
        try:
            if self._cliente_id is None:
                cliente = clientes.crear_cliente(
                    self.f_nombre.obtener(), self.f_telefono.obtener(),
                    self.f_dni.obtener(), self.f_direccion.obtener())
                verbo = "guardado"
            else:
                cliente = clientes.actualizar_cliente(
                    self._cliente_id, self.f_nombre.obtener(),
                    self.f_telefono.obtener(), self.f_dni.obtener(),
                    self.f_direccion.obtener())
                verbo = "actualizado"
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        self.nuevo()
        self.refrescar()
        self.alerta.mostrar(f"Cliente {verbo}: {cliente.nombre}", "ok")

    def quitar(self):
        """Quita al cliente elegido de la lista (sus ventas se conservan)."""
        if self._cliente_id is None:
            return
        nombre = self.f_nombre.obtener()
        if not confirmar(
                self, "Quitar cliente",
                f"¿Quitar a \"{nombre}\" de tus clientes?\n"
                "Sus ventas anteriores se conservan.",
                texto_si="Quitar", peligro=True):
            return
        clientes.desactivar_cliente(self._cliente_id)
        self.nuevo()
        self.refrescar()
        self.alerta.mostrar(f"Cliente quitado: {nombre}", "ok")