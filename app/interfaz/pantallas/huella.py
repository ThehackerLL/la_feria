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
    ("fecha", "Fecha y hora", 125, "w"),
    ("cliente", "Cliente", 250, "w"),
    ("codigo", "Código", 75, "w"),
    ("producto", "Producto", 140, "w", True),
    ("cantidad", "Cantidad", 90, "center"),
    ("costo", "Costo", 72, "e"),
    ("precio", "Precio de venta", 150, "w"),
    ("descuento", "Descuento", 96, "center"),
    ("vendedor", "Vendedor", 200, "w"),
    ("forma", "Forma de pago", 150, "w"),
    ("anulado", "¿Anulado?", 100, "center"),
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
        self.tabla = Tabla(self, _COLUMNAS, alto=18)
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
            (f["id"], (_fecha_hora(f["fecha"]), f["cliente"], f["codigo"],
                       f["producto"], entero(f["cantidad"]), moneda(f["costo"]),
                       moneda(f["precio"]),
                       moneda(f["descuento"]) if f["descuento"] else "—",
                       f["vendedor"] or "—", f["forma_pago"], f["anulado"]),
             "aviso" if f["anulado"] == "Sí" else "")
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