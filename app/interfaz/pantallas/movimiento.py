"""Sección Productos (dentro de Caja y reportes): qué se vende y qué no.

Se elige el periodo (Hoy, Semana, Mes o Año). A la izquierda, los 10 productos
más vendidos. A la derecha, los productos parados: los que tienen stock y casi
no se venden (rojo = no vendió nada, amarillo = vendió muy poco). El dinero
parado en ellos (stock x costo) es dato de costos: sale oculto hasta pulsar
«Mostrar costos».
"""
from datetime import date

import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Tabla
from app.servicios import reportes
from app.utilidades.formato import entero, moneda

OCULTO = "••••"
COLUMNAS_MAS_VENDIDOS = [
    ("nombre", "Producto", 150, "w", True),
    ("unidades", "Unidades", 85, "e"),
    ("vendido", "Vendido", 100, "e"),
    ("stock", "Stock", 70, "e"),
]
COLUMNAS_PARADOS = [
    ("nombre", "Producto", 140, "w", True),
    ("stock", "Stock", 65, "e"),
    ("vendio", "Vendió", 75, "e"),
    ("ultima", "Última venta", 115, "w"),
    ("valor", "Dinero parado", 115, "e"),
]


def _hace(dias):
    if dias is None:
        return "Nunca"
    if dias == 0:
        return "Hoy"
    return "Ayer" if dias == 1 else f"Hace {dias} días"


class PantallaMovimiento(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._periodo = "mes"
        self._ver_costos = False
        self._crear_barra()
        self._cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self._cuerpo.pack(fill="both", expand=True)
        for col in (0, 1):
            self._cuerpo.grid_columnconfigure(col, weight=1, uniform="col")
        self._cuerpo.grid_rowconfigure(0, weight=1)
        self._crear_mas_vendidos()
        self._crear_parados()
        self.refrescar()

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
        self._b_ojo = ctk.CTkButton(
            fila, text="Mostrar costos", width=140, height=e.ALTO_CONTROL,
            fg_color=e.COLOR_NEUTRO, hover_color=e.COLOR_NEUTRO_HOVER,
            text_color=e.COLOR_TEXTO, font=ctk.CTkFont(weight="bold"),
            command=self._alternar_costos)
        self._b_ojo.pack(side="right")

    def _elegir(self, periodo):
        self._periodo = periodo
        self.refrescar()

    def _alternar_costos(self):
        self._ver_costos = not self._ver_costos
        self.refrescar()

    def _crear_mas_vendidos(self):
        izq = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(izq, text="Los 10 más vendidos", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", pady=(0, 6))
        self.t_mas = Tabla(izq, COLUMNAS_MAS_VENDIDOS, alto=10)
        self.t_mas.pack(fill="both", expand=True)
        self._vacio_mas = ctk.CTkLabel(izq, text="", anchor="w",
                                       text_color=e.COLOR_TEXTO_SUAVE)
        self._vacio_mas.pack(fill="x", pady=(6, 0))

    def _crear_parados(self):
        der = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        der.grid(row=0, column=1, sticky="nsew", padx=(e.MARGEN, 0))
        ctk.CTkLabel(der, text="Productos parados", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x")
        self._nota = ctk.CTkLabel(der, text="", anchor="w", justify="left",
                                  wraplength=520, text_color=e.COLOR_TEXTO_SUAVE)
        self._nota.pack(fill="x", pady=(0, 6))
        self.t_parados = Tabla(der, COLUMNAS_PARADOS, alto=7)
        self.t_parados.pack(fill="both", expand=True)
        self._total = ctk.CTkLabel(der, text="", anchor="w",
                                   font=ctk.CTkFont(weight="bold"))
        self._total.pack(fill="x", pady=(6, 0))

    def refrescar(self):
        hoy = date.today()
        p = self._periodo
        for clave, b in self._b_periodo.items():
            activo = clave == p
            b.configure(fg_color=e.COLOR_PRIMARIO if activo else e.COLOR_NEUTRO,
                        hover_color=e.COLOR_PRIMARIO_HOVER if activo else e.COLOR_NEUTRO_HOVER,
                        text_color="#FFFFFF" if activo else e.COLOR_TEXTO)
        self._b_ojo.configure(text="Ocultar costos" if self._ver_costos
                              else "Mostrar costos")

        # más vendidos
        mas = reportes.mas_vendidos(p, hoy)
        self.t_mas.cargar([(f["id"], (f["nombre"], entero(f["unidades"]),
                                      moneda(f["vendido"]), entero(f["stock"])), "")
                           for f in mas])
        self._vacio_mas.configure(
            text="" if mas else "No hubo ventas en este periodo.")

        # parados
        parados = reportes.productos_parados(p, hoy)
        self._nota.configure(
            text=("Con «Hoy» no se puede saber qué está parado: se usa la semana. "
                  if p == "hoy" else "") +
                 "Rojo: no vendió nada. Amarillo: vendió menos del 10 % de su stock.")
        self.t_parados.cargar([
            (f["id"], (f["nombre"], entero(f["stock"]), entero(f["vendido"]),
                       _hace(f["dias_sin_vender"]),
                       moneda(f["valor_parado"]) if self._ver_costos else OCULTO),
             "peligro" if f["estado"] == "sin_ventas" else "aviso")
            for f in parados])
        if not parados:
            self._total.configure(text="Ningún producto parado en este periodo.",
                                  text_color=e.COLOR_OK)
        elif self._ver_costos:
            self._total.configure(
                text="Dinero parado en estos productos: "
                     + moneda(sum(f["valor_parado"] for f in parados)),
                text_color=e.COLOR_TEXTO)
        else:
            self._total.configure(text="Dinero parado en estos productos: S/ " + OCULTO,
                                  text_color=e.COLOR_TEXTO)