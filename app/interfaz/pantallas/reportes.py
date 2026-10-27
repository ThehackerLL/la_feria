"""Sección Reportes (dentro de Caja y reportes).

Se elige el periodo (Hoy, Semana, Mes o Año) y se ve: total vendido, número de
ventas y ganancia bruta con su comparación contra el periodo anterior, el
dinero cobrado y pagado, y la tabla día por día (o mes por mes en el año).
La ganancia está oculta hasta pulsar «Mostrar ganancia».
"""
import os
from datetime import date

import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Alerta, Tabla, TarjetaResumen, boton, confirmar
from app.interfaz.dialogo_credito import fecha_corta
from app.servicios import excel, reportes, respaldos
from app.utilidades.formato import entero, moneda

_MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
          "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
_ANTES = {"hoy": "Ayer", "semana": "Semana pasada", "mes": "Mes pasado",
          "año": "Año pasado"}
OCULTO = "••••"

COLUMNAS_COMPARACION = [
    ("concepto", "", 120, "w", True),
    ("ahora", "Ahora", 105, "e"),
    ("antes", "Antes", 105, "e"),
    ("cambio", "Cambio", 90, "e"),
]
COLUMNAS_DINERO = [
    ("concepto", "", 200, "w", True),
    ("monto", "Monto", 110, "e"),
]
COLUMNAS_DIAS = [
    ("fecha", "Fecha", 110, "w", True),
    ("ventas", "Ventas", 75, "e"),
    ("vendido", "Vendido", 105, "e"),
    ("ganancia", "Ganancia", 105, "e"),
]


def _sin_barra(tabla):
    """Quita la barra de desplazamiento de una tabla corta (pide 200 px de alto)."""
    for hijo in tabla.winfo_children():
        if isinstance(hijo, ctk.CTkScrollbar):
            hijo.grid_remove()


def _cambio(valor):
    if valor is None:
        return "—"
    if valor == 0:
        return "0%"
    return f"+{valor:.1f}%" if valor > 0 else f"−{abs(valor):.1f}%"


class PantallaReportes(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._periodo = "hoy"
        self._ver_ganancia = False
        self._crear_barra()
        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")
        self._crear_tarjetas()
        self._cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self._cuerpo.pack(fill="both", expand=True)
        self._cuerpo.grid_columnconfigure(0, weight=1, uniform="col")
        self._cuerpo.grid_columnconfigure(1, weight=1, uniform="col")
        self._cuerpo.grid_rowconfigure(0, weight=1)
        self._crear_izquierda()
        self._crear_derecha()
        self.refrescar()

    # ----------------------------------------------------------------- barra
    def _crear_barra(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._b_periodo = {}
        for p in reportes.PERIODOS:
            b = ctk.CTkButton(fila, text=p.capitalize(), width=100,
                              height=e.ALTO_CONTROL, font=ctk.CTkFont(weight="bold"),
                              command=lambda x=p: self._elegir(x))
            b.pack(side="left", padx=(0, 8))
            self._b_periodo[p] = b
        self._rango = ctk.CTkLabel(fila, text="", text_color=e.COLOR_TEXTO_SUAVE)
        self._rango.pack(side="left", padx=(8, 0))
        self._b_ojo = ctk.CTkButton(
            fila, text="Mostrar ganancia", width=140, height=e.ALTO_CONTROL,
            fg_color=e.COLOR_NEUTRO, hover_color=e.COLOR_NEUTRO_HOVER,
            text_color=e.COLOR_TEXTO, font=ctk.CTkFont(weight="bold"),
            command=self._alternar_ganancia)
        self._b_ojo.pack(side="right")
        boton(fila, "Exportar a Excel", self._exportar, "ok", ancho=150
              ).pack(side="right", padx=(0, 8))

    def _elegir(self, periodo):
        self._periodo = periodo
        self.refrescar()

    def _exportar(self):
        """Guarda el periodo elegido en un Excel (en la carpeta de Drive elegida
        en Configuración, o en «reportes»). Lleva la
        ganancia y los costos solo si la ganancia está visible en pantalla."""
        try:
            ruta = excel.exportar_reporte(self._periodo,
                                          con_costos=self._ver_ganancia)
        except (ValueError, OSError) as error:
            self.alerta.mostrar(str(error), "error")
            return
        elegida = respaldos.carpeta_excel()
        if elegida is not None and ruta.parent == elegida:
            self.alerta.mostrar(f"Excel guardado en Google Drive: {ruta.name}",
                                "ok", segundos=10)
            copia = ""
        elif elegida is not None:             # Drive no estaba disponible
            self.alerta.mostrar(
                f"Google Drive no está disponible: el Excel se guardó en esta PC "
                f"({ruta.name}). Abre Google Drive y exporta de nuevo si lo quieres allí.",
                "aviso", segundos=12)
            copia = "\nOjo: Google Drive no estaba disponible, por eso quedó en la PC.\n"
        else:
            self.alerta.mostrar(f"Excel guardado: {ruta.name}", "ok", segundos=10)
            copia = ""
        if confirmar(self, "Excel listo",
                     f"Se guardó en:\n{ruta}\n{copia}\n"
                     + ("Incluye costos y ganancia." if self._ver_ganancia else
                        "No incluye costos ni ganancia.") + "\n\n¿Abrirlo ahora?",
                     texto_si="Abrir"):
            try:
                os.startfile(ruta)            # solo existe en Windows
            except (AttributeError, OSError):
                pass

    def _alternar_ganancia(self):
        self._ver_ganancia = not self._ver_ganancia
        self.refrescar()

    # -------------------------------------------------------------- tarjetas
    def _crear_tarjetas(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._tarjetas = {}
        for i, (clave, titulo) in enumerate([
                ("vendido", "Total vendido"), ("ventas", "Número de ventas"),
                ("ganancia", "Ganancia bruta"), ("ticket", "Venta promedio")]):
            fila.grid_columnconfigure(i, weight=1, uniform="tarjeta")
            t = TarjetaResumen(fila, titulo)
            t.grid(row=0, column=i, sticky="ew",
                   padx=(0 if i == 0 else e.ESPACIO // 2,
                         0 if i == 3 else e.ESPACIO // 2))
            self._tarjetas[clave] = t

    # ------------------------------------------------------------- izquierda
    def _crear_izquierda(self):
        izq = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(izq, text="Comparación con el periodo anterior", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", pady=(0, 6))
        self.t_comparacion = Tabla(izq, COLUMNAS_COMPARACION, alto=3)
        self.t_comparacion.pack(fill="x")
        _sin_barra(self.t_comparacion)
        ctk.CTkLabel(izq, text="Dinero cobrado y pagado", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", pady=(e.MARGEN, 6))
        self.t_dinero = Tabla(izq, COLUMNAS_DINERO, alto=6)
        self.t_dinero.pack(fill="x")
        _sin_barra(self.t_dinero)
        for t in (self.t_comparacion, self.t_dinero):
            t.arbol.tag_configure("suave", foreground=e.COLOR_TEXTO_SUAVE)

    # --------------------------------------------------------------- derecha
    def _crear_derecha(self):
        der = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        der.grid(row=0, column=1, sticky="nsew", padx=(e.MARGEN, 0))
        self._titulo_der = ctk.CTkLabel(
            der, text="", anchor="w",
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._titulo_der.pack(fill="x", pady=(0, 6))
        self.t_dias = Tabla(der, COLUMNAS_DIAS, alto=10)
        self.t_dias.pack(fill="both", expand=True)
        self.t_dias.arbol.tag_configure("suave", foreground=e.COLOR_TEXTO_SUAVE)

    # -------------------------------------------------------------- refrescar
    def refrescar(self):
        hoy = date.today()
        p = self._periodo
        r = reportes.resumen_periodo(p, hoy)
        gan = (lambda v: moneda(v)) if self._ver_ganancia else (lambda v: OCULTO)

        for clave, b in self._b_periodo.items():
            activo = clave == p
            b.configure(fg_color=e.COLOR_PRIMARIO if activo else e.COLOR_NEUTRO,
                        hover_color=e.COLOR_PRIMARIO_HOVER if activo else e.COLOR_NEUTRO_HOVER,
                        text_color="#FFFFFF" if activo else e.COLOR_TEXTO)
        self._b_ojo.configure(text="Ocultar ganancia" if self._ver_ganancia
                              else "Mostrar ganancia")
        self._rango.configure(
            text=(fecha_corta(r["desde"].isoformat()) if r["desde"] == r["hasta"] else
                  f"Del {fecha_corta(r['desde'].isoformat())} al "
                  f"{fecha_corta(r['hasta'].isoformat())}"))

        self._tarjetas["vendido"].actualizar(moneda(r["vendido"]))
        self._tarjetas["ventas"].actualizar(entero(r["ventas"]))
        self._tarjetas["ganancia"].actualizar(
            ("S/ " + OCULTO) if not self._ver_ganancia else moneda(r["ganancia"]))
        self._tarjetas["ticket"].actualizar(moneda(r["ticket_promedio"]))

        # comparación
        self.t_comparacion.arbol.heading("antes", text=_ANTES[p])
        a, c = r["anterior"], r["cambio"]
        self.t_comparacion.cargar([
            ("v", ("Total vendido", moneda(r["vendido"]), moneda(a["vendido"]),
                   _cambio(c["vendido"])), ""),
            ("n", ("Número de ventas", entero(r["ventas"]), entero(a["ventas"]),
                   _cambio(c["ventas"])), ""),
            ("g", ("Ganancia bruta", gan(r["ganancia"]), gan(a["ganancia"]),
                   _cambio(c["ganancia"]) if self._ver_ganancia else OCULTO), "")])

        # dinero cobrado y pagado
        self.t_dinero.cargar([
            ("1", ("Efectivo recibido", moneda(r["efectivo_cobrado"])), ""),
            ("2", ("Cobros digitales (Yape, Plin, transf., tarjeta)",
                   moneda(r["digital_cobrado"])), ""),
            ("3", ("Total cobrado", moneda(r["cobrado_total"])), ""),
            ("4", ("   de eso: abonos y cuotas de clientes",
                   moneda(r["abonos_cobrados"])), "suave"),
            ("5", ("Pagos efectuados (compras y cuotas)", moneda(r["pagado_total"])), ""),
            ("6", ("   de eso: cuotas a proveedores", moneda(r["cuotas_pagadas"])), "suave")])

        # día por día, o mes por mes en el año
        if p == "año":
            self._titulo_der.configure(text="Mes por mes")
            self.t_dias.arbol.heading("fecha", text="Mes")
            filas = []
            for m in reversed(reportes.meses_del_año(hoy.year)[:hoy.month]):
                filas.append((m["mes"], (
                    _MESES[m["mes"] - 1], entero(m["ventas"]), moneda(m["vendido"]),
                    gan(m["ganancia"])), "" if m["ventas"] else "suave"))
        else:
            self._titulo_der.configure(text="Día por día")
            self.t_dias.arbol.heading("fecha", text="Fecha")
            filas = [(d["fecha"], (
                fecha_corta(d["fecha"]), entero(d["ventas"]), moneda(d["vendido"]),
                gan(d["ganancia"])), "" if d["ventas"] else "suave")
                for d in reportes.dias_del_periodo(p, hoy)]
        self.t_dias.cargar(filas)