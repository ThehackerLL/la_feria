"""Ventana del plan de una venta o compra a crédito.

Se pide el abono inicial (puede ser 0), en cuántas cuotas se paga y cada
cuántos días. Mientras se escribe se ve el calendario de cuotas con sus
fechas y montos.

Sirve para las dos: en una venta el cliente nos debe a nosotros; en una
compra (compra=True) nosotros le debemos al proveedor.
"""
from datetime import date

import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Campo, Tabla, boton
from app.servicios import compras, creditos, ventas
from app.utilidades.formato import moneda
from app.utilidades.validaciones import a_numero

COLUMNAS = [
    ("cuota", "Cuota", 80, "center"),
    ("vence", "Vence", 150, "w", True),      # la que se estira
    ("monto", "Monto", 120, "e"),
]


def fecha_corta(texto):
    """'2026-10-17' -> '17/10/2026'."""
    anio, mes, dia = str(texto)[:10].split("-")
    return f"{dia}/{mes}/{anio}"


class _DialogoCredito(ctk.CTkToplevel):
    def __init__(self, padre, total, cliente, forma_inicial, compra=False):
        super().__init__(padre)
        self.resultado = None          # {"abono", "forma", "cuotas", "dias"}
        self._total = total
        self._compra = compra
        self._plan = None              # el plan que se ve en la tabla
        formas = compras.FORMAS_PAGO_COMPRA if compra else ventas.FORMAS_PAGO
        titulo = "Compra a crédito" if compra else "Venta a crédito"
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=e.COLOR_FONDO)

        cuerpo = ctk.CTkFrame(self)
        cuerpo.pack(fill="both", expand=True, padx=e.MARGEN, pady=e.MARGEN)
        cuerpo.grid_columnconfigure((0, 1), weight=1, uniform="col")

        ctk.CTkLabel(cuerpo, text=titulo, anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, sticky="ew",
                            padx=18, pady=(16, 2))
        ctk.CTkLabel(cuerpo, anchor="w", text_color=e.COLOR_PRIMARIO,
                     font=ctk.CTkFont(weight="bold"),
                     text=f"{cliente.nombre} · {cliente.telefono}"
                     ).grid(row=1, column=0, columnspan=2, sticky="ew",
                            padx=18)
        ctk.CTkLabel(cuerpo, anchor="w", text_color=e.COLOR_TEXTO_SUAVE,
                     text=f"Total de la {'compra' if compra else 'venta'}: "
                          f"{moneda(total)}"
                     ).grid(row=2, column=0, columnspan=2, sticky="ew",
                            padx=18, pady=(0, 6))

        # Abono inicial y su forma de pago
        self.f_abono = Campo(
            cuerpo, "Pagado al recibir (puede ser 0)" if compra
            else "Abono inicial (puede ser 0)", ayuda="0.00")
        self.f_abono.grid(row=3, column=0, sticky="ew", padx=(18, 6), pady=4)
        marco_forma = ctk.CTkFrame(cuerpo, fg_color="transparent")
        marco_forma.grid(row=3, column=1, sticky="ew", padx=(6, 18), pady=4)
        ctk.CTkLabel(marco_forma, text="Forma de pago" if compra else "Forma del abono",
                     anchor="w",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_PEQUENO)).pack(fill="x")
        self._forma = ctk.CTkOptionMenu(
            marco_forma, values=list(formas), height=e.ALTO_CONTROL,
            font=ctk.CTkFont(weight="bold"),
            dropdown_font=ctk.CTkFont(size=e.TAM_TEXTO))
        self._forma.set(forma_inicial if forma_inicial in formas else formas[0])
        self._forma.pack(fill="x", pady=(2, 0))

        # Cuántas cuotas y cada cuántos días
        self.f_cuotas = Campo(cuerpo, f"Número de cuotas (1 a "
                              f"{creditos.MAX_CUOTAS})", ayuda="1")
        self.f_cuotas.grid(row=4, column=0, sticky="ew", padx=(18, 6), pady=4)
        self.f_dias = Campo(cuerpo, "Días entre cuotas", ayuda="15")
        self.f_dias.grid(row=4, column=1, sticky="ew", padx=(6, 18), pady=4)
        self.f_cuotas.poner(creditos.CUOTAS_DEFECTO)
        self.f_dias.poner(creditos.DIAS_DEFECTO)
        for campo in (self.f_abono, self.f_cuotas, self.f_dias):
            campo.al_escribir(self._recalcular)
            campo.al_enter(self._confirmar)

        # Resumen (o el error, en rojo) y calendario de cuotas
        self._resumen = ctk.CTkLabel(cuerpo, text="", anchor="w",
                                     justify="left", wraplength=420,
                                     font=ctk.CTkFont(weight="bold"))
        self._resumen.grid(row=5, column=0, columnspan=2, sticky="ew",
                           padx=18, pady=(8, 4))
        self._tabla = Tabla(cuerpo, COLUMNAS, alto=5)
        self._tabla.grid(row=6, column=0, columnspan=2, sticky="ew",
                         padx=18, pady=4)

        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.grid(row=7, column=0, columnspan=2, sticky="ew", padx=18,
                 pady=(10, 16))
        self._b_confirmar = boton(
            pie, "Confirmar compra a crédito" if compra
            else "Confirmar crédito", self._confirmar, "ok",
            ancho=230 if compra else 170)
        self._b_confirmar.pack(side="right")
        boton(pie, "Cancelar", self._cancelar, "secundario",
              ancho=100).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _ev: self._cancelar())
        self._recalcular()
        self._centrar(padre)
        self.f_abono.foco()

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

    def _leer(self):
        """Valida lo escrito. Devuelve (abono, cuotas, días, plan) o falla."""
        abono = a_numero(self.f_abono.obtener(),
                         "Pagado al recibir" if self._compra
                         else "Abono inicial")
        if abono >= self._total:
            if self._compra:
                raise ValueError("Lo pagado debe ser menor al total. Si ya "
                                 "pagaste todo, registra la compra normal.")
            raise ValueError("El abono debe ser menor al total. Si el cliente "
                             "pagó todo, cobra la venta normal.")
        saldo = round(self._total - abono, 2)
        cuotas, dias = creditos.leer_condiciones(self.f_cuotas.obtener(),
                                                 self.f_dias.obtener())
        plan = creditos.crear_plan(saldo, cuotas, dias, date.today())
        return round(abono, 2), cuotas, dias, plan

    def _recalcular(self):
        """Actualiza el resumen y el calendario con lo que hay escrito."""
        try:
            abono, _cuotas, _dias, plan = self._leer()
        except ValueError as problema:
            self._plan = None
            self._tabla.vaciar()
            self._resumen.configure(text=str(problema),
                                    text_color=e.COLOR_PELIGRO)
            self._b_confirmar.configure(state="disabled")
            return
        self._plan = plan
        saldo = round(self._total - abono, 2)
        self._resumen.configure(
            text=f"Se financian {moneda(saldo)} en {len(plan)} "
                 f"{'cuota' if len(plan) == 1 else 'cuotas'}.",
            text_color=e.COLOR_TEXTO)
        self._tabla.cargar([(c["numero"], (c["numero"], fecha_corta(c["vence"]),
                                           moneda(c["monto"])), "")
                            for c in plan])
        self._b_confirmar.configure(state="normal")

    def _confirmar(self):
        try:
            abono, cuotas, dias, _plan = self._leer()
        except ValueError:
            return                      # el resumen ya muestra el problema
        self.resultado = {"abono": abono, "forma": self._forma.get(),
                          "cuotas": cuotas, "dias": dias}
        self._cerrar()

    def _cancelar(self):
        self.resultado = None
        self._cerrar()

    def _cerrar(self):
        self.grab_release()
        self.destroy()


def plan_credito(padre, total, cliente, forma_inicial=None, compra=False):
    """Abre la ventana del plan. Devuelve {"abono", "forma", "cuotas", "dias"}
    o None si se cancela.

    `cliente` es quien debe: el cliente en una venta o el proveedor en una
    compra (compra=True). Solo se usan su nombre y teléfono."""
    dialogo = _DialogoCredito(padre, total, cliente, forma_inicial, compra)
    padre.wait_window(dialogo)
    return dialogo.resultado