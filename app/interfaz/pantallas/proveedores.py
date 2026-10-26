"""Pestaña Proveedores: todos los proveedores, lo que les debemos y lo que
les hemos comprado.

A la izquierda, TODOS los proveedores guardados: primero los que tienen deuda
(rojo = cuotas vencidas, amarillo = vence en 3 días o menos) y debajo los que
no se les debe nada ("Sin deuda"). Al elegir uno, a la derecha se ven sus datos
(con Editar y Quitar) y dos vistas: «Deuda» (cuotas y pagar) y «Compras
realizadas» (qué productos se le han comprado).
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import (Alerta, Campo, Tabla, TarjetaResumen,
                                      aviso, boton, confirmar)
from app.interfaz.dialogo_credito import fecha_corta
from app.interfaz.dialogo_proveedor import (crear_proveedor_nuevo,
                                            editar_proveedor)
from app.servicios import compras, por_pagar, proveedores
from app.utilidades.formato import entero, moneda
from app.utilidades.validaciones import a_numero

ANCHO_DETALLE = 540
VISTA_DEUDA = "Deuda"
VISTA_COMPRAS = "Compras realizadas"

# Proveedor, Rubro y Dirección se estiran juntas cuando la ventana es ancha:
# así el espacio sobrante se reparte y ninguna queda enorme ni cortada.
COLUMNAS = [
    ("nombre", "Proveedor", 170, "w", True),
    ("telefono", "Teléfono", 95, "w"),
    ("vende", "Rubro", 130, "w", True),
    ("direccion", "Dirección", 120, "w", True),
    ("debe", "Debe", 95, "e"),
]
COLUMNAS_DEUDAS = [
    ("numero", "Compra", 80, "w"),
    ("fecha", "Fecha", 90, "w"),
    ("total", "Total", 85, "e"),
    ("debe", "Debe", 85, "e"),
    ("proxima", "Próxima cuota", 130, "w", True),   # la que se estira
]
COLUMNAS_CUOTAS = [
    ("n", "Cuota", 55, "center"),
    ("vence", "Vence", 95, "w"),
    ("monto", "Monto", 85, "e"),
    ("debe", "Debe", 85, "e"),
    ("estado", "Estado", 100, "w", True),      # la que se estira
]
COLUMNAS_PAGOS = [
    ("fecha", "Fecha", 95, "w"),
    ("forma", "Forma de pago", 120, "w", True),  # la que se estira
    ("monto", "Monto", 90, "e"),
]
COLUMNAS_COMPRADO = [
    ("fecha", "Fecha", 85, "w"),
    ("numero", "Compra", 80, "w"),
    ("producto", "Producto", 110, "w", True),   # la que se estira
    ("cantidad", "Cant.", 50, "e"),
    ("costo", "Costo", 75, "e"),
    ("subtotal", "Subtotal", 85, "e"),
]
ESTADO_TEXTO = {"pagada": "Pagada", "vencida": "Vencida",
                "por_vencer": "Por vencer", "pendiente": "Pendiente"}
ESTADO_FILA = {"pagada": "ok", "vencida": "peligro", "por_vencer": "aviso",
               "pendiente": ""}
SUFIJO_ESTADO = {"vencida": "  (vencida)", "por_vencer": "  (por vencer)"}


class PantallaProveedores(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._prov_id = None         # proveedor elegido (None = ninguno)
        self._prov = None            # su ficha (Proveedor)
        self._deudas = []            # sus compras a crédito pendientes
        self._compra_id = None       # compra a crédito elegida
        self._cuota = None           # cuota elegida para pagar (diccionario)
        self._crear_resumen()
        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")
        self._cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self._cuerpo.pack(fill="both", expand=True)
        self._cuerpo.grid_columnconfigure(0, weight=1)
        self._cuerpo.grid_rowconfigure(0, weight=1)
        self._crear_lista()
        self._crear_detalle()
        self.tabla.al_elegir(lambda id_: self._mostrar_proveedor(int(id_)))
        self.refrescar()

    # ---------------------------------------------------------------- resumen
    def _crear_resumen(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._tarjetas = {}
        for i, (clave, titulo) in enumerate([
                ("por_pagar", "Total que debemos"),
                ("vencido", "Total vencido"),
                ("con_deuda", "Proveedores con deuda")]):
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
                              ayuda="Nombre, teléfono o rubro")
        self.buscador.pack(side="left")
        self.buscador.al_escribir(self.refrescar)
        boton(barra, "Proveedor nuevo", self._nuevo, "principal",
              ancho=150).pack(side="right", pady=(18, 0))
        self._contador = ctk.CTkLabel(barra, text="",
                                      text_color=e.COLOR_TEXTO_SUAVE)
        self._contador.pack(side="right", padx=14, pady=(18, 0))

        self.tabla = Tabla(izquierda, COLUMNAS, alto=14)
        self.tabla.arbol.tag_configure("suave", foreground=e.COLOR_TEXTO_SUAVE)
        self.tabla.pack(fill="both", expand=True)

    def refrescar(self):
        """Vuelve a leer la base de datos y dibuja tarjetas, lista y detalle."""
        resumen = por_pagar.resumen_deudas()
        todos = por_pagar.resumen_por_proveedor()
        texto = self.buscador.obtener()
        lista = por_pagar.resumen_por_proveedor(texto) if texto else todos
        self._tarjetas["por_pagar"].actualizar(moneda(resumen["por_pagar"]))
        self._tarjetas["vencido"].actualizar(
            moneda(resumen["vencido"]),
            e.COLOR_PELIGRO if resumen["vencido"] else None)
        self._tarjetas["con_deuda"].actualizar(
            entero(sum(1 for r in todos if r["debe"] > 0)))

        filas = []
        for r in lista:
            if r["debe"] > 0:
                estado = ("peligro" if r["vencidas"] else
                          "aviso" if r["proxima"]["estado"] == "por_vencer"
                          else "")
                debe = moneda(r["debe"])
            else:
                estado, debe = "suave", "Sin deuda"
            filas.append((r["id"], (r["nombre"], r["telefono"] or "—",
                                    r["vende"] or "—", r["direccion"] or "—",
                                    debe), estado))
        self.tabla.cargar(filas)
        if texto:
            self._contador.configure(
                text=f"Mostrando {len(filas)} de {len(todos)}")
        elif not todos:
            self._contador.configure(
                text="Todavía no hay proveedores: crea el primero")
        else:
            self._contador.configure(text="")
        ids = {f[0] for f in filas}
        if self._prov_id in ids:
            self.tabla.arbol.selection_set(str(self._prov_id))
            self._mostrar_proveedor(self._prov_id)
        else:
            self._limpiar_detalle()

    # ---------------------------------------------------------------- detalle
    def _crear_detalle(self):
        panel = ctk.CTkScrollableFrame(
            self._cuerpo, width=ANCHO_DETALLE, fg_color=e.COLOR_TARJETA,
            border_width=1, border_color=e.COLOR_BORDE)
        panel.grid(row=0, column=1, sticky="ns", padx=(e.MARGEN, 0))

        self._vacio = ctk.CTkLabel(
            panel, text="Elige un proveedor de la lista para ver sus datos,\n"
                        "su deuda y lo que le hemos comprado.",
            text_color=e.COLOR_TEXTO_SUAVE, justify="center")
        self._vacio.pack(padx=16, pady=60)

        self._detalle = ctk.CTkFrame(panel, fg_color="transparent")
        self._titulo = ctk.CTkLabel(
            self._detalle, text="", anchor="w", justify="left", wraplength=500,
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._titulo.pack(fill="x", padx=8, pady=(4, 0))
        self._datos = ctk.CTkLabel(self._detalle, text="", anchor="w",
                                   justify="left", wraplength=500,
                                   text_color=e.COLOR_TEXTO_SUAVE)
        self._datos.pack(fill="x", padx=8, pady=(0, 6))
        acciones = ctk.CTkFrame(self._detalle, fg_color="transparent")
        acciones.pack(fill="x", padx=8, pady=(0, 10))
        boton(acciones, "Editar", self._editar, "secundario",
              ancho=90).pack(side="left")
        boton(acciones, "Quitar proveedor", self._quitar, "secundario",
              ancho=150).pack(side="left", padx=8)

        # Las dos vistas del proveedor: botones tipo pestaña
        self._vista = VISTA_DEUDA
        marco_vistas = ctk.CTkFrame(self._detalle, fg_color="transparent")
        marco_vistas.pack(fill="x", padx=8, pady=(0, 8))
        marco_vistas.grid_columnconfigure((0, 1), weight=1, uniform="vista")
        self._b_vistas = {}
        for col, nombre in enumerate((VISTA_DEUDA, VISTA_COMPRAS)):
            b = ctk.CTkButton(
                marco_vistas, text=nombre, height=e.ALTO_CONTROL,
                font=ctk.CTkFont(weight="bold"),
                command=lambda n=nombre: self._cambiar_vista(n))
            b.grid(row=0, column=col, sticky="ew",
                   padx=(0, 4) if col == 0 else (4, 0))
            self._b_vistas[nombre] = b

        self._crear_vista_deuda()
        self._crear_vista_compras()

    def _crear_vista_deuda(self):
        self._v_deuda = ctk.CTkFrame(self._detalle, fg_color="transparent")

        self._sin_deuda = ctk.CTkLabel(
            self._v_deuda, text="No le debes nada a este proveedor.",
            text_color=e.COLOR_TEXTO_SUAVE)
        self._con_deuda = ctk.CTkFrame(self._v_deuda, fg_color="transparent")

        ctk.CTkLabel(self._con_deuda, text="Compras a crédito que debes",
                     anchor="w", font=ctk.CTkFont(weight="bold")
                     ).pack(fill="x", padx=8, pady=(0, 2))
        self.t_deudas = Tabla(self._con_deuda, COLUMNAS_DEUDAS, alto=3)
        self.t_deudas.pack(fill="x", padx=8)
        self.t_deudas.al_elegir(lambda id_: self._mostrar_compra(int(id_)))

        self._sub = ctk.CTkLabel(self._con_deuda, text="", anchor="w",
                                 text_color=e.COLOR_TEXTO_SUAVE)
        self._sub.pack(fill="x", padx=8, pady=(10, 2))
        self.t_cuotas = Tabla(self._con_deuda, COLUMNAS_CUOTAS, alto=4)
        self.t_cuotas.arbol.tag_configure(
            "ok", background=e.COLOR_OK_FONDO, foreground=e.COLOR_OK)
        self.t_cuotas.pack(fill="x", padx=8)
        self.t_cuotas.al_elegir(lambda id_: self._elegir_cuota(int(id_)))

        # Pagar la cuota elegida
        self._pago = ctk.CTkFrame(self._con_deuda, fg_color="transparent")
        self._pago.pack(fill="x", padx=8, pady=(10, 0))
        self._pago.grid_columnconfigure((0, 1), weight=1, uniform="col")
        self.f_monto = Campo(self._pago, "Monto que pagas", ayuda="0.00")
        self.f_monto.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.f_monto.al_enter(self._pagar)
        marco = ctk.CTkFrame(self._pago, fg_color="transparent")
        marco.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(marco, text="Forma de pago", anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_PEQUENO)).pack(fill="x")
        self._forma = ctk.CTkOptionMenu(
            marco, values=list(compras.FORMAS_PAGO_COMPRA),
            height=e.ALTO_CONTROL, font=ctk.CTkFont(weight="bold"),
            dropdown_font=ctk.CTkFont(size=e.TAM_TEXTO))
        self._forma.set(compras.FORMAS_PAGO_COMPRA[0])
        self._forma.pack(fill="x", pady=(2, 0))
        self._b_pagar = boton(self._pago, "Pagar cuota", self._pagar, "ok")
        self._b_pagar.grid(row=1, column=0, columnspan=2, sticky="ew",
                           pady=(8, 0))

        ctk.CTkLabel(self._con_deuda, text="Pagos hechos", anchor="w",
                     font=ctk.CTkFont(weight="bold")
                     ).pack(fill="x", padx=8, pady=(12, 2))
        self.t_pagos = Tabla(self._con_deuda, COLUMNAS_PAGOS, alto=3)
        self.t_pagos.pack(fill="x", padx=8, pady=(0, 8))

    def _crear_vista_compras(self):
        self._v_compras = ctk.CTkFrame(self._detalle, fg_color="transparent")
        self._resumen_compras = ctk.CTkLabel(
            self._v_compras, text="", anchor="w",
            text_color=e.COLOR_TEXTO_SUAVE)
        self._resumen_compras.pack(fill="x", padx=8, pady=(0, 4))
        self.t_comprado = Tabla(self._v_compras, COLUMNAS_COMPRADO, alto=10)
        self.t_comprado.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(
            self._v_compras, anchor="w", justify="left", wraplength=500,
            text="Aquí salen las compras hechas con este proveedor guardado.",
            text_color=e.COLOR_TEXTO_SUAVE, font=ctk.CTkFont(size=e.TAM_PEQUENO)
        ).pack(fill="x", padx=8, pady=(0, 8))

    def _limpiar_detalle(self):
        self._prov_id = self._prov = self._compra_id = self._cuota = None
        self._deudas = []
        self._detalle.pack_forget()
        self._vacio.pack(padx=16, pady=60)

    def _mostrar_proveedor(self, prov_id):
        """Dibuja la ficha del proveedor con su deuda y sus compras. Al
        cambiar de proveedor abre «Deuda» si se le debe algo, y si no,
        «Compras realizadas»; al refrescar el mismo, deja la vista actual."""
        prov = proveedores.obtener_proveedor(prov_id)
        if prov is None or not prov.activo:
            self._limpiar_detalle()
            return
        cambio = self._prov_id != prov_id
        self._prov_id, self._prov = prov_id, prov
        self._deudas = [d for d in por_pagar.listar_deudas()
                        if d["proveedor_id"] == prov_id]
        self._vacio.pack_forget()
        self._detalle.pack(fill="both", expand=True)

        self._titulo.configure(text=prov.nombre)
        lineas = [f"Teléfono: {prov.telefono}"]
        if prov.vende:
            lineas.append(f"Rubro: {prov.vende}")
        if prov.direccion:
            lineas.append(f"Dirección: {prov.direccion}")
        self._datos.configure(text="\n".join(lineas))

        self._dibujar_compras(por_pagar.historial_compras(prov_id))
        self._dibujar_deuda()
        if cambio:
            self._vista = VISTA_DEUDA if self._deudas else VISTA_COMPRAS
        self._cambiar_vista(self._vista)

    def _cambiar_vista(self, vista):
        """Muestra «Deuda» o «Compras realizadas» y marca el botón activo."""
        self._vista = vista
        self._v_deuda.pack_forget()
        self._v_compras.pack_forget()
        (self._v_deuda if vista == VISTA_DEUDA else self._v_compras).pack(
            fill="x")
        for nombre, b in self._b_vistas.items():
            activo = nombre == vista
            b.configure(
                fg_color=e.COLOR_PRIMARIO if activo else e.COLOR_NEUTRO,
                hover_color=(e.COLOR_PRIMARIO_HOVER if activo
                             else e.COLOR_NEUTRO_HOVER),
                text_color="#FFFFFF" if activo else e.COLOR_TEXTO)

    # --------------------------------------------------- vista: compras hechas
    def _dibujar_compras(self, historial):
        filas, total = [], 0.0
        n = 0
        for compra in historial:
            total += compra["total"]
            for linea in compra["lineas"]:
                filas.append((n, (
                    fecha_corta(compra["fecha"]), compra["numero"],
                    linea["nombre"], entero(linea["cantidad"]),
                    moneda(linea["costo"]),
                    moneda(linea["cantidad"] * linea["costo"])), ""))
                n += 1
        self.t_comprado.cargar(filas)
        if historial:
            self._resumen_compras.configure(
                text=f"{len(historial)} "
                     f"{'compra' if len(historial) == 1 else 'compras'} · "
                     f"{moneda(total)} en total")
        else:
            self._resumen_compras.configure(
                text="Todavía no le has comprado nada.")

    # --------------------------------------------------------- vista: la deuda
    def _dibujar_deuda(self):
        if not self._deudas:
            self._compra_id = self._cuota = None
            self._con_deuda.pack_forget()
            self._sin_deuda.pack(padx=8, pady=24)
            return
        self._sin_deuda.pack_forget()
        self._con_deuda.pack(fill="x")
        filas = []
        for d in self._deudas:
            p = d["proxima"]
            estado = ("peligro" if d["vencidas"] else
                      "aviso" if p["estado"] == "por_vencer" else "")
            filas.append((d["compra_id"], (
                d["numero"], fecha_corta(d["fecha"]), moneda(d["total"]),
                moneda(d["debe"]),
                fecha_corta(p["vence"]) + SUFIJO_ESTADO.get(p["estado"], "")),
                estado))
        self.t_deudas.cargar(filas)
        ids = {d["compra_id"] for d in self._deudas}
        elegida = self._compra_id if self._compra_id in ids else \
            self._deudas[0]["compra_id"]
        self.t_deudas.arbol.selection_set(str(elegida))
        self._mostrar_compra(elegida)

    def _mostrar_compra(self, compra_id):
        """Dibuja las cuotas y pagos de la compra; deja elegida la cuota que
        toca pagar (la misma de antes si sigue pendiente, o la primera)."""
        d = por_pagar.detalle_deuda(compra_id)
        if d is None or d["debe"] == 0:
            return
        antes = self._cuota["numero"] if (
            self._cuota and self._compra_id == compra_id) else None
        self._compra_id = compra_id
        self._sub.configure(
            text=f"{d['numero']} · Total {moneda(d['total'])} · pagado "
                 f"{moneda(d['pagado'])} · debes {moneda(d['debe'])}")
        self._cuotas = {q["id"]: q for q in d["cuotas"]}
        self.t_cuotas.cargar([
            (q["id"], (q["numero"], fecha_corta(q["vence"]), moneda(q["monto"]),
                       moneda(q["debe"]), ESTADO_TEXTO[q["estado"]]),
             ESTADO_FILA[q["estado"]]) for q in d["cuotas"]])
        self.t_pagos.cargar([
            (i, (fecha_corta(p["fecha"]), p["forma_pago"], moneda(p["monto"])),
             "") for i, p in enumerate(d["pagos"])])
        sin_pagar = [q for q in d["cuotas"] if q["estado"] != "pagada"]
        elegida = next((q for q in sin_pagar if q["numero"] == antes),
                       sin_pagar[0])
        self.t_cuotas.arbol.selection_set(str(elegida["id"]))
        self._elegir_cuota(elegida["id"])

    def _elegir_cuota(self, cuota_id):
        """Deja lista la cuota para pagar: monto = lo que aún debes."""
        q = self._cuotas.get(cuota_id)
        if q is None:
            return
        self._cuota = q
        self.f_monto.desactivar(False)     # un campo apagado no deja escribir
        if q["estado"] == "pagada":
            self.f_monto.limpiar()
            self.f_monto.desactivar()
            self._b_pagar.configure(state="disabled",
                                    text=f"La cuota {q['numero']} ya está pagada")
            return
        self.f_monto.poner(f"{q['debe']:.2f}")
        self._b_pagar.configure(state="normal",
                                text=f"Pagar cuota {q['numero']}")

    def _pagar(self):
        """Paga lo escrito de la cuota elegida (completo o una parte)."""
        if self._cuota is None or self._cuota["estado"] == "pagada":
            return
        try:
            monto = a_numero(self.f_monto.obtener(), "Monto")
            r = por_pagar.registrar_pago_cuota(self._cuota["id"], monto,
                                               self._forma.get())
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        a_quien = r["proveedor"] or "el proveedor"
        if r["debe_compra"]:
            texto = (f"Pagado {moneda(r['monto'])} de la cuota {r['cuota']} "
                     f"({r['forma_pago']}). Aún le debes "
                     f"{moneda(r['debe_compra'])} a {a_quien}.")
        else:
            texto = (f"Pagado {moneda(r['monto'])} ({r['forma_pago']}). "
                     f"Terminaste de pagar la compra {r['numero']} a "
                     f"{a_quien}.")
        self.refrescar()
        self.alerta.mostrar(texto, "ok", segundos=8)

    # ---------------------------------------------------- crear, editar, quitar
    def _nuevo(self):
        nuevo = crear_proveedor_nuevo(self)
        if nuevo is None:
            return
        self.buscador.limpiar()
        self._prov_id = None            # que se abra como proveedor nuevo
        self.refrescar()
        self.tabla.arbol.selection_set(str(nuevo.id))
        self.tabla.arbol.see(str(nuevo.id))
        self._mostrar_proveedor(nuevo.id)
        self.alerta.mostrar(f"Proveedor «{nuevo.nombre}» guardado.", "ok",
                            segundos=6)

    def _editar(self):
        if self._prov is None:
            return
        editado = editar_proveedor(self, self._prov)
        if editado is None:
            return
        self.refrescar()
        self.alerta.mostrar(f"Datos de «{editado.nombre}» actualizados.", "ok",
                            segundos=6)

    def _quitar(self):
        """Quita al proveedor de la lista. Si se le debe algo, no se puede:
        primero hay que pagarle (así la deuda nunca queda escondida)."""
        if self._prov is None:
            return
        debe = por_pagar.resumen_por_proveedor(self._prov.nombre)
        debe = next((r["debe"] for r in debe if r["id"] == self._prov.id), 0)
        if debe > 0:
            aviso(self, "No se puede quitar",
                  f"Todavía le debes {moneda(debe)} a {self._prov.nombre}.\n"
                  "Págale primero y después lo puedes quitar.")
            return
        if not confirmar(
                self, "Quitar proveedor",
                f"¿Quitar a {self._prov.nombre} de la lista?\n"
                "Sus compras anteriores se conservan.",
                texto_si="Quitar", peligro=True):
            return
        nombre = self._prov.nombre
        proveedores.desactivar_proveedor(self._prov.id)
        self._prov_id = None
        self.refrescar()
        self.alerta.mostrar(f"«{nombre}» ya no aparece en la lista.", "ok",
                            segundos=6)