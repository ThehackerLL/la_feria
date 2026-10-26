"""Pantalla Crédito: quién debe, cuándo vence cada cuota y cobrar las cuotas.

A la izquierda, una fila por crédito pendiente (rojo = tiene cuotas vencidas,
amarillo = vence en 3 días o menos). Al elegir uno, a la derecha se ven sus
cuotas, se cobra la cuota elegida (completa o una parte) y los pagos hechos.
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Alerta, Campo, Tabla, TarjetaResumen, boton
from app.interfaz.dialogo_credito import fecha_corta
from app.servicios import creditos, ventas
from app.utilidades.formato import entero, moneda
from app.utilidades.validaciones import a_numero

COLUMNAS = [
    ("fecha", "Pidió el", 85, "w"),
    ("nombre", "Cliente", 130, "w", True),     # la que se estira
    ("telefono", "Teléfono", 90, "w"),
    ("total", "Total", 80, "e"),
    ("debe", "Debe", 80, "e"),
    ("cuotas", "Pendientes", 95, "center"),
    ("proxima", "Próxima cuota", 180, "w"),
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
ESTADO_TEXTO = {"pagada": "Pagada", "vencida": "Vencida",
                "por_vencer": "Por vencer", "pendiente": "Pendiente"}
ESTADO_FILA = {"pagada": "ok", "vencida": "peligro", "por_vencer": "aviso",
               "pendiente": ""}


class PantallaCreditos(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._venta_id = None        # crédito elegido (None = ninguno)
        self._cuota = None           # cuota elegida para cobrar (diccionario)
        self._crear_resumen()
        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")
        self._cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self._cuerpo.pack(fill="both", expand=True)
        self._cuerpo.grid_columnconfigure(0, weight=1)
        self._cuerpo.grid_rowconfigure(0, weight=1)
        self._crear_lista()
        self._crear_detalle()
        self.tabla.al_elegir(lambda id_: self._mostrar_detalle(int(id_)))
        self.refrescar()

    # ---------------------------------------------------------------- resumen
    def _crear_resumen(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._tarjetas = {}
        for i, (clave, titulo) in enumerate([
                ("por_cobrar", "Total por cobrar"),
                ("vencido", "Total vencido"),
                ("creditos", "Créditos pendientes")]):
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
                              ayuda="Nombre o teléfono")
        self.buscador.pack(side="left")
        self.buscador.al_escribir(self.refrescar)
        self._contador = ctk.CTkLabel(barra, text="",
                                      text_color=e.COLOR_TEXTO_SUAVE)
        self._contador.pack(side="right", pady=(18, 0))

        self.tabla = Tabla(izquierda, COLUMNAS, alto=14)
        self.tabla.pack(fill="both", expand=True)

    def refrescar(self):
        """Vuelve a leer la base de datos y dibuja tarjetas, lista y detalle."""
        resumen = creditos.resumen_creditos()
        self._tarjetas["por_cobrar"].actualizar(moneda(resumen["por_cobrar"]))
        self._tarjetas["vencido"].actualizar(
            moneda(resumen["vencido"]),
            e.COLOR_PELIGRO if resumen["vencido"] else None)
        self._tarjetas["creditos"].actualizar(entero(resumen["creditos"]))

        lista = creditos.listar_creditos(self.buscador.obtener())
        filas = []
        for c in lista:
            p = c["proxima"]
            sufijo = {"vencida": "  (vencida)",
                      "por_vencer": "  (por vencer)"}.get(p["estado"], "")
            estado = ("peligro" if c["vencidas"] else
                      "aviso" if p["estado"] == "por_vencer" else "")
            filas.append((c["venta_id"], (
                fecha_corta(c["fecha"]), c["nombre"] or "—",
                c["telefono"] or "—", moneda(c["total"]), moneda(c["debe"]),
                f"{c['pendientes']} de {c['cuotas']}",
                fecha_corta(p["vence"]) + sufijo), estado))
        self.tabla.cargar(filas)
        if self.buscador.obtener():
            self._contador.configure(
                text=f"Mostrando {len(filas)} de {resumen['creditos']}")
        elif resumen["creditos"] == 0:
            self._contador.configure(text="No hay créditos pendientes")
        else:
            self._contador.configure(text="")
        ids = {f[0] for f in filas}
        if self._venta_id in ids:
            self.tabla.arbol.selection_set(str(self._venta_id))
            self._mostrar_detalle(self._venta_id)
        else:
            self._limpiar_detalle()

    # ---------------------------------------------------------------- detalle
    def _crear_detalle(self):
        panel = ctk.CTkFrame(self._cuerpo, border_width=1,
                             border_color=e.COLOR_BORDE)
        panel.grid(row=0, column=1, sticky="ns", padx=(e.MARGEN, 0))
        self._panel = panel

        self._vacio = ctk.CTkLabel(
            panel, text="Elige un crédito de la lista\npara ver sus cuotas.",
            text_color=e.COLOR_TEXTO_SUAVE, justify="center", width=440)
        self._vacio.pack(padx=16, pady=60)

        self._detalle = ctk.CTkFrame(panel, fg_color="transparent")
        self._titulo = ctk.CTkLabel(
            self._detalle, text="", anchor="w",
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._titulo.pack(fill="x", padx=16, pady=(12, 0))
        self._sub = ctk.CTkLabel(self._detalle, text="", anchor="w",
                                 text_color=e.COLOR_TEXTO_SUAVE)
        self._sub.pack(fill="x", padx=16, pady=(0, 6))

        self.t_cuotas = Tabla(self._detalle, COLUMNAS_CUOTAS, alto=5)
        self.t_cuotas.arbol.tag_configure(
            "ok", background=e.COLOR_OK_FONDO, foreground=e.COLOR_OK)
        self.t_cuotas.pack(fill="x", padx=16)
        self.t_cuotas.al_elegir(lambda id_: self._elegir_cuota(int(id_)))

        # Cobrar la cuota elegida
        self._cobro = ctk.CTkFrame(self._detalle, fg_color="transparent")
        self._cobro.pack(fill="x", padx=16, pady=(10, 0))
        self._cobro.grid_columnconfigure((0, 1), weight=1, uniform="col")
        self.f_monto = Campo(self._cobro, "Monto que paga", ayuda="0.00")
        self.f_monto.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.f_monto.al_enter(self._pagar)
        marco = ctk.CTkFrame(self._cobro, fg_color="transparent")
        marco.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(marco, text="Forma de pago", anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_PEQUENO)).pack(fill="x")
        self._forma = ctk.CTkOptionMenu(
            marco, values=list(ventas.FORMAS_PAGO), height=e.ALTO_CONTROL,
            font=ctk.CTkFont(weight="bold"),
            dropdown_font=ctk.CTkFont(size=e.TAM_TEXTO))
        self._forma.set(ventas.FORMAS_PAGO[0])
        self._forma.pack(fill="x", pady=(2, 0))
        self._b_pagar = boton(self._cobro, "Pagar cuota", self._pagar, "ok")
        self._b_pagar.grid(row=1, column=0, columnspan=2, sticky="ew",
                           pady=(8, 0))

        ctk.CTkLabel(self._detalle, text="Pagos recibidos", anchor="w",
                     font=ctk.CTkFont(weight="bold")
                     ).pack(fill="x", padx=16, pady=(12, 2))
        self.t_pagos = Tabla(self._detalle, COLUMNAS_PAGOS, alto=3)
        self.t_pagos.pack(fill="x", padx=16, pady=(0, 14))

    def _limpiar_detalle(self):
        self._venta_id = None
        self._cuota = None
        self._detalle.pack_forget()
        self._vacio.pack(padx=16, pady=60)

    def _mostrar_detalle(self, venta_id):
        """Dibuja las cuotas y pagos del crédito; deja elegida la cuota que
        toca cobrar (la misma de antes si sigue pendiente, o la primera)."""
        d = creditos.detalle_credito(venta_id)
        if d is None or d["estado"] != "activa" or d["debe"] == 0:
            self._limpiar_detalle()
            return
        antes = self._cuota["numero"] if (
            self._cuota and self._venta_id == venta_id) else None
        self._venta_id = venta_id
        self._vacio.pack_forget()
        self._detalle.pack(fill="both", expand=True)
        self._titulo.configure(text=f"{d['numero']} · {d['nombre']}")
        self._sub.configure(
            text=f"Total {moneda(d['total'])} · pagado {moneda(d['pagado'])} "
                 f"· debe {moneda(d['debe'])}")
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
        """Deja lista la cuota para cobrar: monto = lo que aún debe."""
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

    # ------------------------------------------------------------------ cobrar
    def _pagar(self):
        """Cobra lo escrito de la cuota elegida (completo o una parte)."""
        if self._cuota is None or self._cuota["estado"] == "pagada":
            return
        try:
            monto = a_numero(self.f_monto.obtener(), "Monto")
            r = creditos.registrar_pago_cuota(self._cuota["id"], monto,
                                              self._forma.get())
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        if r["debe_venta"]:
            texto = (f"Cobrado {moneda(r['monto'])} de la cuota {r['cuota']} "
                     f"({r['forma_pago']}). {r['cliente']} aún debe "
                     f"{moneda(r['debe_venta'])}.")
        else:
            texto = (f"Cobrado {moneda(r['monto'])} ({r['forma_pago']}). "
                     f"{r['cliente']} terminó de pagar el crédito "
                     f"{r['numero']}.")
        self.refrescar()
        self.alerta.mostrar(texto, "ok", segundos=8)