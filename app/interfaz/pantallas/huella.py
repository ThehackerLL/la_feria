"""Pestaña «Huella digital»: cada producto vendido, sin poder borrar ni cambiar nada.

Una fila por producto vendido, con lo que valía ese día. Si una venta se anula
o se devuelve un producto, la fila sigue aquí y solo cambia «¿Anulado?» a «Sí».
Si alguien edita la base de datos por fuera, aparece un aviso rojo.
"""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Tabla
from app.servicios import huella
from app.utilidades.formato import entero, moneda

_COLUMNAS = [
    # Suman unos 1145 px: caben en la ventana normal (y «Producto» se estira).
    # En pantallas chicas, o con escala de Windows alta, aparece la barra de
    # desplazamiento horizontal.
    ("fecha", "Fecha y hora", 130, "w"),
    ("vendedor", "Vendedor", 105, "w"),
    ("cliente", "Cliente", 180, "w"),
    ("codigo", "Código", 65, "w"),
    ("producto", "Producto", 110, "w", True),
    ("cantidad", "Cantidad", 70, "center"),
    ("costo", "Costo", 62, "e"),
    ("precio", "Precio de venta", 110, "e"),
    ("descuento", "Descuento", 80, "center"),
    ("ganancia", "Ganancia", 78, "e"),
    ("forma", "Forma de pago", 105, "w"),
    ("estado", "Venta hecha", 120, "w"),
]


def _fecha_hora(texto):
    """'2026-11-02 14:40:05' -> '02/11/2026 14:40'."""
    dia, _, hora = str(texto).partition(" ")
    a, m, d = (dia.split("-") + ["", "", ""])[:3]
    return f"{d}/{m}/{a} {hora[:5]}".strip()


class PantallaHuella(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._periodo = "hoy"
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._b_periodo = {}
        for p in huella.PERIODOS:
            b = ctk.CTkButton(fila, text=p.capitalize(), width=100,
                              height=e.ALTO_CONTROL, font=ctk.CTkFont(weight="bold"),
                              command=lambda x=p: self._elegir(x))
            b.pack(side="left", padx=(0, 8))
            self._b_periodo[p] = b
        self._cuenta = ctk.CTkLabel(fila, text="", text_color=e.COLOR_TEXTO_SUAVE)
        self._cuenta.pack(side="left", padx=(8, 0))
        self._alerta = ctk.CTkLabel(
            self, text="", anchor="w", justify="left", wraplength=900,
            fg_color=e.COLOR_PELIGRO_FONDO, text_color=e.COLOR_PELIGRO,
            corner_radius=e.RADIO, font=ctk.CTkFont(weight="bold"))
        self.tabla = Tabla(self, _COLUMNAS, alto=18, scroll_x=True)
        self.tabla.pack(fill="both", expand=True)

    def _elegir(self, periodo):
        self._periodo = periodo
        self.refrescar()

    def refrescar(self):
        for clave, b in self._b_periodo.items():
            activo = clave == self._periodo
            b.configure(fg_color=e.COLOR_PRIMARIO if activo else e.COLOR_NEUTRO,
                        hover_color=e.COLOR_PRIMARIO_HOVER if activo else e.COLOR_NEUTRO_HOVER,
                        text_color="#FFFFFF" if activo else e.COLOR_TEXTO)
        filas = huella.listar(self._periodo)
        self.tabla.cargar([
            (f["id"], (_fecha_hora(f["fecha"]), f["vendedor"] or "-", f["cliente"],
                       f["codigo"], f["producto"], entero(f["cantidad"]),
                       moneda(f["costo"]), moneda(f["precio"]),
                       moneda(f["descuento"]) if f["descuento"] else "-",
                       moneda(f["ganancia"]), f["forma_pago"], f["estado"]),
             "aviso" if f["estado"] != "-" else "")
            for f in filas])
        texto = f"{len(filas)} {'producto' if len(filas) == 1 else 'productos'}"
        if len(filas) >= huella.LIMITE:
            texto += f" (se muestran los últimos {huella.LIMITE})"
        self._cuenta.configure(text=texto)
        malo = huella.verificar()
        if malo is None:
            self._alerta.pack_forget()
        else:
            self._alerta.configure(
                text=f"  ATENCIÓN: este registro fue modificado fuera del programa "
                     f"(línea {malo}). Los datos pueden no ser confiables.  ")
            self._alerta.pack(fill="x", pady=(0, e.ESPACIO), before=self.tabla)