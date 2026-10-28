"""Sección «Ventas hechas» (dentro de Caja y reportes).

Lista las ventas (también las anuladas), muestra el detalle de la que se elige
y permite anularla o devolver solo un producto. Anular devuelve el stock y el
dinero cobrado; la venta no se borra: queda marcada como anulada con su motivo.
Devolver un producto (o parte de sus unidades) deja la venta con el resto.
"""
from datetime import date, timedelta

import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Alerta, Campo, CampoLista, Tabla, boton, confirmar
from app.interfaz.dialogo_credito import fecha_corta
from app.servicios import anulaciones
from app.servicios.ventas import FORMAS_PAGO
from app.utilidades.formato import moneda

PERIODOS = ["Hoy", "7 días", "Este mes", "Todas"]

COLUMNAS_VENTAS = [
    ("numero", "Venta", 85, "w"),
    ("fecha", "Fecha", 90, "w"),
    ("cliente", "Cliente", 120, "w", True),
    ("total", "Total", 90, "e"),
    ("estado", "Estado", 80, "w"),
]
COLUMNAS_LINEAS = [
    ("producto", "Producto", 150, "w", True),
    ("cant", "Cant.", 50, "e"),
    ("precio", "Precio", 75, "e"),
    ("subtotal", "Subtotal", 85, "e"),
]


def _rango(periodo):
    hoy = date.today()
    if periodo == "Hoy":
        return hoy.isoformat(), hoy.isoformat()
    if periodo == "7 días":
        return (hoy - timedelta(days=6)).isoformat(), hoy.isoformat()
    if periodo == "Este mes":
        return hoy.replace(day=1).isoformat(), hoy.isoformat()
    return None, None


class _DialogoAnular(ctk.CTkToplevel):
    """Pide el motivo y muestra lo que va a pasar.

    resultado = (motivo, volver_al_stock) o None si se canceló.
    """

    def __init__(self, padre, venta):
        super().__init__(padre)
        self.resultado = None
        self.title("Anular venta")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text=f"Anular la venta {venta['numero']}", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 4))
        self._unidades = sum(l["cantidad"] for l in venta["lineas"])
        texto = []
        if venta["pagado"] > 0:
            formas = ", ".join(f"{moneda(m)} en {f}" for f, m in
                               venta["por_forma"])
            texto.append(f"• Se devuelve {moneda(venta['pagado'])} al cliente "
                         f"({formas}). Sale de la caja de hoy.")
        if venta["debe"] > 0:
            texto.append(f"• La deuda de {moneda(venta['debe'])} se cancela.")
        texto.append("• La venta queda en el historial como anulada.")
        self._stock = ctk.CTkLabel(cuerpo, anchor="w", justify="left",
                                   wraplength=400, text_color=e.COLOR_TEXTO_SUAVE)
        self._stock.pack(fill="x", padx=18, pady=(0, 0))
        ctk.CTkLabel(cuerpo, text="\n".join(texto), anchor="w", justify="left",
                     wraplength=400, text_color=e.COLOR_TEXTO_SUAVE
                     ).pack(fill="x", padx=18, pady=(0, 10))
        self.danado = ctk.CTkCheckBox(
            cuerpo, text="No volver al stock (mercadería dañada)",
            command=self._actualizar_stock)
        self.danado.pack(anchor="w", padx=18, pady=(0, 10))
        self._actualizar_stock()
        self.campo = Campo(cuerpo, "Motivo (obligatorio)", ancho=400,
                           ayuda="Ej.: el cliente devolvió todo, error al cobrar")
        self.campo.pack(fill="x", padx=18, pady=(0, 6))
        self.error = ctk.CTkLabel(cuerpo, text="", anchor="w",
                                  text_color=e.COLOR_PELIGRO)
        self.error.pack(fill="x", padx=18)
        fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=(6, 16))
        boton(fila, "Anular venta", self._aceptar, tipo="peligro",
              ancho=130).pack(side="right", padx=(8, 0))
        boton(fila, "Cancelar", self._cerrar, tipo="secundario",
              ancho=110).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.bind("<Escape>", lambda _ev: self._cerrar())
        self.campo.al_enter(self._aceptar)
        self._centrar(padre)
        self.campo.foco()

    def _actualizar_stock(self):
        if self.danado.get():
            texto = "• Las unidades NO vuelven al stock."
        else:
            texto = f"• {self._unidades:g} unidades vuelven al stock."
        self._stock.configure(text=texto)

    def _aceptar(self):
        motivo = self.campo.obtener()
        if len(motivo) < 3:
            self.error.configure(text="Escribe el motivo de la anulación.")
            return
        self.resultado = (motivo, not self.danado.get())
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


class _DialogoDevolver(ctk.CTkToplevel):
    """Devolución de un producto. resultado = (unidades, forma, al_stock) o None."""

    def __init__(self, padre, venta, linea):
        super().__init__(padre)
        self.resultado = None
        self._venta, self._linea = venta, linea
        self.title("Devolver producto")
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)
        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        ctk.CTkLabel(cuerpo, text=f"Devolver «{linea['nombre']}»", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(cuerpo, text=f"Venta {venta['numero']}  ·  se vendieron "
                     f"{linea['cantidad']:g} a {moneda(linea['precio_unitario'])}",
                     anchor="w", text_color=e.COLOR_TEXTO_SUAVE
                     ).pack(fill="x", padx=18, pady=(0, 10))
        self.unidades = Campo(cuerpo, "Unidades que devuelve", ancho=400)
        self.unidades.pack(fill="x", padx=18, pady=(0, 8))
        self.unidades.poner(f"{linea['cantidad']:g}")
        self.unidades.al_escribir(self._actualizar)
        self.unidades.al_enter(self._aceptar)
        self.resumen = ctk.CTkLabel(cuerpo, text="", anchor="w", justify="left",
                                    wraplength=400, text_color=e.COLOR_TEXTO_SUAVE)
        self.resumen.pack(fill="x", padx=18, pady=(0, 8))
        self.forma = CampoLista(cuerpo, "El dinero se devuelve en",
                                valores=FORMAS_PAGO, ancho=400)
        self.forma.pack(fill="x", padx=18, pady=(0, 8))
        usada = venta["por_forma"][0][0] if venta["por_forma"] else FORMAS_PAGO[0]
        self.forma.poner(usada)
        self.danado = ctk.CTkCheckBox(
            cuerpo, text="No volver al stock (mercadería dañada)")
        self.danado.pack(anchor="w", padx=18, pady=(0, 6))
        self.error = ctk.CTkLabel(cuerpo, text="", anchor="w",
                                  text_color=e.COLOR_PELIGRO, wraplength=400,
                                  justify="left")
        self.error.pack(fill="x", padx=18)
        fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=(6, 16))
        boton(fila, "Devolver", self._aceptar, tipo="peligro",
              ancho=130).pack(side="right", padx=(8, 0))
        boton(fila, "Cancelar", self._cerrar, tipo="secundario",
              ancho=110).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.bind("<Escape>", lambda _ev: self._cerrar())
        self._actualizar()
        self._centrar(padre)
        self.unidades.foco()

    def _actualizar(self):
        try:
            p = anulaciones.vista_previa_devolucion(
                self._venta["id"], self._linea["id"], self.unidades.obtener())
        except ValueError as error:
            self.resumen.configure(text="")
            self.error.configure(text=str(error))
            return
        self.error.configure(text="")
        lineas = [f"• El producto vale {moneda(p['valor'])}."]
        if p["baja_deuda"] > 0:
            lineas.append(f"• Baja la deuda del cliente en {moneda(p['baja_deuda'])}.")
        if p["dinero"] > 0:
            lineas.append(f"• Se le devuelve {moneda(p['dinero'])}. "
                          "Sale de la caja de hoy.")
        self.resumen.configure(text="\n".join(lineas))

    def _aceptar(self):
        try:
            p = anulaciones.vista_previa_devolucion(
                self._venta["id"], self._linea["id"], self.unidades.obtener())
        except ValueError as error:
            self.error.configure(text=str(error))
            return
        forma = self.forma.obtener()
        if p["dinero"] > 0 and forma not in FORMAS_PAGO:
            self.error.configure(text="Elige en qué forma se devuelve el dinero.")
            return
        self.resultado = (p["cantidad"], forma, not self.danado.get())
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


class PantallaVentasHechas(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._venta = None
        self._periodo = "Hoy"

        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(0, e.ESPACIO))
        self.buscar = Campo(barra, "Buscar por cliente o número (V-000012)", ancho=280)
        self.buscar.pack(side="left")
        self.buscar.al_escribir(self.refrescar)
        self.selector = ctk.CTkSegmentedButton(
            barra, values=PERIODOS, command=self._cambiar_periodo,
            height=e.ALTO_CONTROL)
        self.selector.set(self._periodo)
        self.selector.pack(side="right", anchor="s")

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=1)
        cuerpo.grid_columnconfigure(1, weight=0)
        cuerpo.grid_rowconfigure(0, weight=1)

        self.tabla = Tabla(cuerpo, COLUMNAS_VENTAS, alto=12)
        self.tabla.grid(row=0, column=0, sticky="nsew", padx=(0, e.ESPACIO))
        self.tabla.al_elegir(self._elegir)

        self._detalle = ctk.CTkFrame(cuerpo, width=420)
        self._detalle.grid(row=0, column=1, sticky="ns")
        self._detalle.grid_propagate(False)
        self._crear_detalle()
        self.refrescar()

    # ------------------------------------------------------------ detalle
    def _crear_detalle(self):
        d = self._detalle
        self._titulo = ctk.CTkLabel(
            d, text="Elige una venta de la lista", anchor="w",
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._titulo.pack(fill="x", padx=14, pady=(12, 0))
        self._sub = ctk.CTkLabel(d, text="", anchor="w", justify="left",
                                 text_color=e.COLOR_TEXTO_SUAVE, wraplength=390)
        self._sub.pack(fill="x", padx=14)
        self.t_lineas = Tabla(d, COLUMNAS_LINEAS, alto=6)
        self.t_lineas.pack(fill="x", padx=14, pady=(8, 8))
        self._pagos = ctk.CTkLabel(d, text="", anchor="w", justify="left",
                                   wraplength=390)
        self._pagos.pack(fill="x", padx=14)
        self._nota = ctk.CTkLabel(d, text="", anchor="w", justify="left",
                                  wraplength=390, text_color=e.COLOR_PELIGRO)
        self._nota.pack(fill="x", padx=14, pady=(6, 0))
        pie = ctk.CTkFrame(d, fg_color="transparent")
        pie.pack(side="bottom", fill="x", padx=14, pady=14)
        self.b_anular = boton(pie, "Anular venta", self._anular, tipo="peligro",
                              ancho=150)
        self.b_anular.pack(side="right")
        self.b_devolver = boton(pie, "Devolver producto", self._devolver,
                                tipo="secundario", ancho=160)
        self.b_devolver.pack(side="right", padx=(0, 8))
        self.b_anular.configure(state="disabled")
        self.b_devolver.configure(state="disabled")
        self._ayuda = ctk.CTkLabel(
            d, text="", anchor="w", justify="left", wraplength=390,
            text_color=e.COLOR_TEXTO_SUAVE, font=ctk.CTkFont(size=e.TAM_PEQUENO))
        self._ayuda.pack(side="bottom", fill="x", padx=14)
        self.t_lineas.al_elegir(self._elegir_linea)

    def _mostrar(self, v):
        self._venta = v
        self._titulo.configure(text=f"Venta {v['numero']}")
        sub = f"{fecha_corta(v['fecha'])} {v['fecha'][11:16]}  ·  {v['cliente']}"
        sub += f"\nTotal {moneda(v['total'])}"
        if v["descuento"]:
            sub += f"  (con descuento de {moneda(v['descuento'])})"
        self._sub.configure(text=sub)
        self.t_lineas.cargar([
            (l["id"], (f"{l['nombre']}", f"{l['cantidad']:g}",
                       moneda(l["precio_unitario"]), moneda(l["subtotal"])), "")
            for l in v["lineas"]])
        if v["pagos"]:
            lineas = [f"{fecha_corta(p['fecha'])}  {p['forma_pago']}: "
                      f"{moneda(p['monto'])}" for p in v["pagos"]]
            texto = "Pagos:\n" + "\n".join(lineas)
        else:
            texto = "Sin pagos registrados."
        if v["devoluciones"]:
            texto += "\n\nDevoluciones:\n" + "\n".join(
                f"{fecha_corta(x['fecha'])}  {x['cantidad']:g} × {x['nombre']}"
                f" ({moneda(x['valor'])})" for x in v["devoluciones"])
        if v["estado"] == "activa" and v["debe"] > 0:
            texto += f"\n\nTodavía debe: {moneda(v['debe'])}"
        self._pagos.configure(text=texto)
        if v["anulacion"]:
            self._nota.configure(
                text=f"ANULADA el {fecha_corta(v['anulacion']['fecha'])}.\n"
                     f"Motivo: {v['anulacion']['motivo']}\n"
                     + ("Las unidades volvieron al stock."
                        if v["anulacion"]["al_stock"]
                        else "Las unidades NO volvieron al stock (dañadas)."))
        else:
            self._nota.configure(text="")
        activa = v["estado"] == "activa"
        self.b_anular.configure(state="normal" if activa else "disabled")
        self.b_devolver.configure(state="disabled")
        self._ayuda.configure(
            text="Para devolver solo un producto, elígelo en la lista de arriba."
            if activa else "")

    def _elegir_linea(self, _id):
        if self._venta and self._venta["estado"] == "activa":
            self.b_devolver.configure(state="normal")
            self._ayuda.configure(text="")

    def _limpiar_detalle(self):
        self._venta = None
        self._titulo.configure(text="Elige una venta de la lista")
        for et in (self._sub, self._pagos, self._nota):
            et.configure(text="")
        self.t_lineas.vaciar()
        self.b_anular.configure(state="disabled")
        self.b_devolver.configure(state="disabled")
        self._ayuda.configure(text="")

    # ------------------------------------------------------------ acciones
    def _cambiar_periodo(self, periodo):
        self._periodo = periodo
        self.refrescar()

    def _elegir(self, id_):
        v = anulaciones.detalle_venta(int(id_))
        if v:
            self._mostrar(v)

    def _anular(self):
        v = self._venta
        if not v or v["estado"] != "activa":
            return
        dialogo = _DialogoAnular(self, v)
        self.wait_window(dialogo)
        if not dialogo.resultado:
            return
        motivo, al_stock = dialogo.resultado
        try:
            r = anulaciones.anular_venta(v["id"], motivo, volver_al_stock=al_stock)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error", 6)
            return
        msg = (f"Venta {r['numero']} anulada. " + (
            "Las unidades volvieron al stock." if r["volvio_al_stock"]
            else "Las unidades no volvieron al stock."))
        if r["total_devuelto"] > 0:
            msg += f" Devuelve {moneda(r['total_devuelto'])} al cliente."
        self.alerta.mostrar(msg, "ok", 8)
        self.refrescar()
        self._elegir(v["id"])

    def _devolver(self):
        v, id_linea = self._venta, self.t_lineas.seleccionado()
        if not v or id_linea is None or v["estado"] != "activa":
            return
        linea = next((l for l in v["lineas"] if str(l["id"]) == str(id_linea)), None)
        if linea is None:
            return
        dialogo = _DialogoDevolver(self, v, linea)
        self.wait_window(dialogo)
        if not dialogo.resultado:
            return
        unidades, forma, al_stock = dialogo.resultado
        try:
            r = anulaciones.devolver_producto(
                v["id"], linea["id"], unidades, forma_pago=forma,
                volver_al_stock=al_stock)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error", 6)
            return
        msg = (f"Devolución registrada: {r['cantidad']:g} × {r['producto']}. "
               + ("Volvió al stock." if r["volvio_al_stock"]
                  else "No volvió al stock."))
        if r["baja_deuda"] > 0:
            msg += f" La deuda bajó {moneda(r['baja_deuda'])}."
        if r["dinero"] > 0:
            msg += f" Devuelve {moneda(r['dinero'])} al cliente."
        self.alerta.mostrar(msg, "ok", 8)
        self.refrescar()
        self._elegir(v["id"])

    def refrescar(self):
        """Vuelve a leer la lista (se llama al entrar y al filtrar)."""
        desde, hasta = _rango(self._periodo)
        filas = anulaciones.listar_ventas(desde, hasta, self.buscar.obtener())
        elegida = self._venta["id"] if self._venta else None
        self.tabla.cargar([
            (f["id"], (f["numero"], fecha_corta(f["fecha"]), f["cliente"],
                       moneda(f["total"]),
                       "Anulada" if f["estado"] == "anulada"
                       else ("Debe" if f["debe"] > 0 else "Pagada")),
             "peligro" if f["estado"] == "anulada"
             else ("aviso" if f["debe"] > 0 else ""))
            for f in filas])
        if elegida is not None and self.tabla.arbol.exists(str(elegida)):
            self.tabla.arbol.selection_set(str(elegida))
        elif elegida is not None:
            self._limpiar_detalle()