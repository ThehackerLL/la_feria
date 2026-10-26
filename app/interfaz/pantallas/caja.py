"""Pantalla Caja y reportes.

Arriba tres botones: «Caja del día», «Reportes» y «Productos». Esta pantalla
construye «Caja del día»: abrir la caja con el efectivo inicial, ver lo que
entró y salió hoy, y cerrarla contando el efectivo. «Reportes» y «Productos»
son pantallas aparte que se cargan cuando están escritas.
"""
import importlib
from datetime import date, datetime

import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.componentes import Alerta, Campo, Tabla, TarjetaResumen, boton
from app.interfaz.dialogo_caja import cerrar_caja
from app.interfaz.dialogo_credito import fecha_corta
from app.servicios import caja
from app.utilidades.formato import entero, moneda
from app.utilidades.validaciones import a_numero

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

COLUMNAS_COBROS = [
    ("forma", "", 90, "w", True),
    ("ventas", "Cobrado en ventas", 160, "e"),
    ("abonos", "Abonos y cuotas", 145, "e"),
    ("pagado", "Pagado", 100, "e"),
    ("neto", "Neto", 100, "e"),
]
COLUMNAS_HISTORIAL = [
    ("fecha", "Fecha", 88, "w"),
    ("estado", "Estado", 80, "w", True),
    ("apertura", "Apertura", 90, "e"),
    ("esperado", "Esperado", 90, "e"),
    ("contado", "Contado", 85, "e"),
    ("dif", "Diferencia", 100, "e"),
]
ESTADO_TEXTO = {caja.ABIERTA: "Abierta", caja.CERRADA: "Cerrada",
                caja.SIN_CONTAR: "Sin contar"}

# (botón, módulo, clase): pantallas que se cargan cuando existen
SECCIONES = [
    ("Caja del día", None, None),
    ("Reportes", "reportes", "PantallaReportes"),
    ("Productos", "movimiento", "PantallaMovimiento"),
]


def fecha_larga(dia):
    """date -> 'miércoles 21 de octubre'."""
    return f"{_DIAS[dia.weekday()]} {dia.day} de {_MESES[dia.month - 1]}"


def _dinero(valor):
    return "—" if valor is None else moneda(valor)


class VistaCajaDia(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._ver_ganancia = False
        self._crear_encabezado()
        self.alerta = Alerta(self)
        self.alerta.pack(fill="x")
        self._crear_pendiente()
        self._crear_tarjetas()
        self._cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self._cuerpo.pack(fill="both", expand=True)
        self._cuerpo.grid_columnconfigure(0, weight=1, uniform="col")
        self._cuerpo.grid_columnconfigure(1, weight=1, uniform="col")
        self._cuerpo.grid_rowconfigure(0, weight=1)
        self._crear_izquierda()
        self._crear_historial()

    # ------------------------------------------------------------ encabezado
    def _crear_encabezado(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._titulo = ctk.CTkLabel(
            fila, text="", anchor="w",
            font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold"))
        self._titulo.pack(side="left")
        self._estado = ctk.CTkLabel(fila, text="", corner_radius=e.RADIO,
                                    font=ctk.CTkFont(weight="bold"))
        self._estado.pack(side="left", padx=(12, 0), ipadx=10, ipady=2)

    def _crear_pendiente(self):
        """Franja amarilla: un día anterior que se abrió y no se cerró."""
        self._pendiente = ctk.CTkFrame(self, fg_color=e.COLOR_AVISO_FONDO,
                                       corner_radius=e.RADIO)
        self._txt_pendiente = ctk.CTkLabel(
            self._pendiente, text="", anchor="w", text_color=e.COLOR_AVISO,
            font=ctk.CTkFont(weight="bold"))
        self._txt_pendiente.pack(side="left", padx=14, pady=8)
        boton(self._pendiente, "Cerrar ese día", self._cerrar_pendiente,
              "principal", ancho=130).pack(side="right", padx=10, pady=6)
        self._dia_pendiente = None

    # -------------------------------------------------------------- tarjetas
    def _crear_tarjetas(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, e.ESPACIO))
        self._tarjetas = {}
        for i, (clave, titulo) in enumerate([
                ("vendido", "Venta del día"), ("ganancia", "Ganancia del día"),
                ("efectivo", "Efectivo"), ("digital", "Digital (Yape, Plin, transf., tarjeta)")]):
            fila.grid_columnconfigure(i, weight=1, uniform="tarjeta")
            tarjeta = TarjetaResumen(fila, titulo)
            tarjeta.grid(row=0, column=i, sticky="ew",
                         padx=(0 if i == 0 else e.ESPACIO // 2,
                               0 if i == 3 else e.ESPACIO // 2))
            self._tarjetas[clave] = tarjeta
        # la ganancia se oculta con un botón pequeño (sin contraseña por ahora)
        self._b_ojo = ctk.CTkButton(
            self._tarjetas["ganancia"], text="Mostrar", width=64, height=24,
            fg_color=e.COLOR_NEUTRO, hover_color=e.COLOR_NEUTRO_HOVER,
            text_color=e.COLOR_TEXTO, font=ctk.CTkFont(size=e.TAM_PEQUENO),
            command=self._alternar_ganancia)
        self._b_ojo.place(relx=1.0, x=-10, y=8, anchor="ne")

    def _alternar_ganancia(self):
        self._ver_ganancia = not self._ver_ganancia
        self.refrescar()

    # ------------------------------------------------------------- izquierda
    def _crear_izquierda(self):
        izq = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="nsew")

        # --- caja sin abrir: pide la apertura
        self._abrir = ctk.CTkFrame(izq, border_width=1, border_color=e.COLOR_BORDE)
        ctk.CTkLabel(self._abrir, text="Abrir la caja de hoy", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(14, 0))
        ctk.CTkLabel(
            self._abrir, anchor="w", justify="left", text_color=e.COLOR_TEXTO_SUAVE,
            text="Escribe con cuánto efectivo empiezas el día. Ya aparece lo que "
                 "contaste en el último cierre."
            ).pack(fill="x", padx=18, pady=(0, 6))
        fila = ctk.CTkFrame(self._abrir, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=(0, 16))
        self.f_apertura = Campo(fila, "Efectivo con el que empiezas", ancho=220,
                                ayuda="0.00")
        self.f_apertura.pack(side="left")
        self.f_apertura.al_enter(self._abrir_caja)
        boton(fila, "Abrir caja", self._abrir_caja, "ok", ancho=120
              ).pack(side="left", padx=(12, 0), pady=(18, 0))

        # --- caja abierta o cerrada: cobros, pagos y efectivo
        self._detalle = ctk.CTkFrame(izq, fg_color="transparent")
        ctk.CTkLabel(self._detalle, text="Cobros y pagos de hoy", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", pady=(0, 6))
        self.t_cobros = Tabla(self._detalle, COLUMNAS_COBROS, alto=2)
        # Solo son 2 filas: se quita la barra de desplazamiento, que pedía 200 px
        # de alto y estiraba la tabla.
        for hijo in self.t_cobros.winfo_children():
            if isinstance(hijo, ctk.CTkScrollbar):
                hijo.grid_remove()
        self.t_cobros.pack(fill="x")
        self._credito = ctk.CTkLabel(self._detalle, text="", anchor="w",
                                     text_color=e.COLOR_TEXTO_SUAVE)
        self._credito.pack(fill="x", pady=(6, 10))

        cuenta = ctk.CTkFrame(self._detalle, border_width=1,
                              border_color=e.COLOR_BORDE)
        cuenta.pack(fill="x")
        ctk.CTkLabel(cuenta, text="Efectivo en caja", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", padx=18, pady=(14, 4))
        self._cuenta = ctk.CTkLabel(cuenta, text="", anchor="w", justify="left")
        self._cuenta.pack(fill="x", padx=18)
        self._cierre = ctk.CTkLabel(cuenta, text="", anchor="w", justify="left",
                                    font=ctk.CTkFont(weight="bold"))
        self._cierre.pack(fill="x", padx=18, pady=(4, 0))
        self._b_cerrar = boton(cuenta, "Cerrar caja", self._cerrar_hoy, "ok",
                               ancho=140)
        self._b_cerrar.pack(anchor="w", padx=18, pady=(10, 16))

    # ------------------------------------------------------------- historial
    def _crear_historial(self):
        der = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        der.grid(row=0, column=1, sticky="nsew", padx=(e.MARGEN, 0))
        ctk.CTkLabel(der, text="Aperturas y cierres", anchor="w",
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO, weight="bold")
                     ).pack(fill="x", pady=(0, 6))
        self.t_historial = Tabla(der, COLUMNAS_HISTORIAL, alto=8)
        self.t_historial.pack(fill="both", expand=True)
        self._sin_historial = ctk.CTkLabel(
            der, text="Todavía no hay cierres.", anchor="w",
            text_color=e.COLOR_TEXTO_SUAVE)

    # -------------------------------------------------------------- refrescar
    def refrescar(self):
        hoy = date.today()
        r = caja.resumen_dia(hoy)
        dia = r["dia"]
        self._titulo.configure(text=fecha_larga(hoy).capitalize())

        # estado del día
        if dia is None:
            texto, fondo, color = "Caja sin abrir", e.COLOR_AVISO_FONDO, e.COLOR_AVISO
        elif dia["estado"] == caja.ABIERTA:
            texto, fondo, color = "Caja abierta", e.COLOR_OK_FONDO, e.COLOR_OK
        else:
            texto, fondo, color = "Caja cerrada", e.COLOR_NEUTRO, e.COLOR_TEXTO_SUAVE
        self._estado.configure(text=texto, fg_color=fondo, text_color=color)

        # día anterior sin cerrar
        pendientes = caja.dias_pendientes(hoy)
        if pendientes:
            self._dia_pendiente = pendientes[0]
            extra = f" (y {len(pendientes) - 1} más)" if len(pendientes) > 1 else ""
            self._txt_pendiente.configure(
                text=f"La caja del {fecha_corta(pendientes[0])} quedó sin cerrar{extra}.")
            self._pendiente.pack(fill="x", pady=(0, e.ESPACIO), after=self.alerta)
        else:
            self._dia_pendiente = None
            self._pendiente.pack_forget()

        # tarjetas
        self._tarjetas["vendido"].actualizar(moneda(r["vendido"]))
        if self._ver_ganancia:
            self._tarjetas["ganancia"].actualizar(moneda(r["ganancia"]))
            self._b_ojo.configure(text="Ocultar")
        else:
            self._tarjetas["ganancia"].actualizar("S/ ••••")
            self._b_ojo.configure(text="Mostrar")
        self._tarjetas["efectivo"].actualizar(
            _dinero(r["efectivo_esperado"]),
            e.COLOR_TEXTO_SUAVE if dia is None else None)
        self._tarjetas["digital"].actualizar(moneda(r["digital_cobrado"]))

        # cuerpo: abrir caja o detalle
        if dia is None:
            self._detalle.pack_forget()
            self._abrir.pack(fill="x")
            if not self.f_apertura.obtener():
                self.f_apertura.poner(f"{caja.sugerir_apertura(hoy):.2f}")
        else:
            self._abrir.pack_forget()
            self._detalle.pack(fill="x")
            self._dibujar_detalle(r)
        self._dibujar_historial()

    def _dibujar_detalle(self, r):
        dia = r["dia"]
        ef = {d["forma"]: d for d in r["por_forma"]}[caja.FORMA_EFECTIVO]
        otras = [d for d in r["por_forma"] if d["forma"] != caja.FORMA_EFECTIVO]
        dig_ventas = round(sum(d["cobrado_ventas"] for d in otras), 2)
        dig_abonos = round(sum(d["cobrado_abonos"] for d in otras), 2)
        self.t_cobros.cargar([
            ("ef", ("Efectivo", moneda(ef["cobrado_ventas"]), moneda(ef["cobrado_abonos"]),
                    moneda(r["efectivo_pagado"]),
                    moneda(r["efectivo_cobrado"] - r["efectivo_pagado"])), ""),
            ("di", ("Digital", moneda(dig_ventas), moneda(dig_abonos),
                    moneda(r["digital_pagado"]),
                    moneda(r["digital_cobrado"] - r["digital_pagado"])), "")])
        self._credito.configure(
            text=(f"Vendido a crédito hoy y por cobrar: {moneda(r['a_credito'])}"
                  if r["a_credito"] else "Hoy no quedó nada por cobrar de ventas a crédito."))
        self._cuenta.configure(
            text=(f"Apertura {moneda(dia['apertura'])}  +  cobrado {moneda(r['efectivo_cobrado'])}"
                  f"  −  pagado {moneda(r['efectivo_pagado'])}  =  "
                  f"esperado {moneda(r['efectivo_esperado'])}"))
        if dia["estado"] == caja.ABIERTA:
            self._cierre.configure(text="")
            self._b_cerrar.pack(anchor="w", padx=18, pady=(10, 16))
        else:
            self._b_cerrar.pack_forget()
            if dia["contado"] is None:
                self._cierre.configure(text="Cerrada sin contar el efectivo.",
                                       text_color=e.COLOR_TEXTO_SUAVE)
            else:
                self._cierre.configure(
                    text=f"Contado {moneda(dia['contado'])}  ·  " + _frase_dif(dia["diferencia"]),
                    text_color=_color_dif(dia["diferencia"]))

    def _dibujar_historial(self):
        filas = []
        for h in caja.historial(60):
            dif = h["diferencia"]
            estado = ("peligro" if dif is not None and dif < 0 else
                      "aviso" if dif is not None and dif > 0 else "")
            filas.append((h["fecha"], (
                fecha_corta(h["fecha"]), ESTADO_TEXTO.get(h["estado"], h["estado"]),
                moneda(h["apertura"]), _dinero(h["esperado"]), _dinero(h["contado"]),
                "—" if dif is None else ("Cuadra" if dif == 0 else moneda(dif))), estado))
        self.t_historial.cargar(filas)
        if filas:
            self._sin_historial.pack_forget()
        else:
            self._sin_historial.pack(fill="x", pady=(6, 0))

    # --------------------------------------------------------------- acciones
    def _abrir_caja(self):
        try:
            monto = a_numero(self.f_apertura.obtener(), "Efectivo con el que empiezas")
            caja.abrir_dia(monto)
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            return
        self.f_apertura.limpiar()
        self.refrescar()
        self.alerta.mostrar(f"Caja abierta con {moneda(monto)}.", "ok")

    def _cerrar_hoy(self):
        self._cerrar(date.today().isoformat(), anterior=False)

    def _cerrar_pendiente(self):
        if self._dia_pendiente:
            self._cerrar(self._dia_pendiente, anterior=True)

    def _cerrar(self, fecha, anterior):
        esperado = caja.resumen_dia(fecha)["efectivo_esperado"]
        r = cerrar_caja(self, fecha, esperado, anterior)
        if r is None:
            return
        try:
            if r["sin_contar"]:
                caja.cerrar_sin_contar(fecha, nota=r["nota"])
                mensaje = f"Caja del {fecha_corta(fecha)} cerrada sin contar."
                tipo = "aviso"
            else:
                c = caja.cerrar_dia(r["contado"], hoy=fecha, nota=r["nota"])
                mensaje = (f"Caja del {fecha_corta(fecha)} cerrada. "
                           + _frase_dif(c["diferencia"]))
                tipo = "ok" if c["diferencia"] == 0 else "aviso"
        except ValueError as error:
            self.alerta.mostrar(str(error), "error")
            self.refrescar()
            return
        self.refrescar()
        self.alerta.mostrar(mensaje, tipo, segundos=8)


def _frase_dif(dif):
    if dif == 0:
        return "Cuadra: no sobra ni falta nada."
    return f"Sobran {moneda(dif)}" if dif > 0 else f"Faltan {moneda(-dif)}"


def _color_dif(dif):
    return e.COLOR_OK if dif == 0 else (e.COLOR_AVISO if dif > 0 else e.COLOR_PELIGRO)


def _cargar_clase(modulo, clase):
    ruta = f"app.interfaz.pantallas.{modulo}"
    try:
        return getattr(importlib.import_module(ruta), clase, None)
    except ModuleNotFoundError as error:
        if error.name == ruta:
            return None
        raise


class _Proximamente(ctk.CTkFrame):
    def __init__(self, padre, nombre):
        super().__init__(padre, fg_color="transparent")
        ctk.CTkLabel(self, text=f"{nombre}: próximamente",
                     text_color=e.COLOR_TEXTO_SUAVE,
                     font=ctk.CTkFont(size=e.TAM_SUBTITULO)).pack(pady=60)


class PantallaCaja(ctk.CTkFrame):
    def __init__(self, padre):
        super().__init__(padre, fg_color="transparent")
        self._vistas = {}
        self._activa = None
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(0, e.ESPACIO))
        self._botones = {}
        for nombre, *_ in SECCIONES:
            b = ctk.CTkButton(barra, text=nombre, width=140, height=e.ALTO_CONTROL,
                              font=ctk.CTkFont(weight="bold"),
                              command=lambda n=nombre: self.mostrar(n))
            b.pack(side="left", padx=(0, 8))
            self._botones[nombre] = b
        self._zona = ctk.CTkFrame(self, fg_color="transparent")
        self._zona.pack(fill="both", expand=True)
        self.mostrar("Caja del día")

    def _crear(self, nombre):
        for titulo, modulo, clase in SECCIONES:
            if titulo == nombre:
                if modulo is None:
                    return VistaCajaDia(self._zona)
                pantalla = _cargar_clase(modulo, clase)
                return pantalla(self._zona) if pantalla else _Proximamente(self._zona, nombre)

    def mostrar(self, nombre):
        if nombre not in self._vistas:
            self._vistas[nombre] = self._crear(nombre)
        if self._activa is not None:
            self._vistas[self._activa].pack_forget()
        self._vistas[nombre].pack(fill="both", expand=True)
        self._activa = nombre
        for n, b in self._botones.items():
            activo = n == nombre
            b.configure(fg_color=e.COLOR_PRIMARIO if activo else e.COLOR_NEUTRO,
                        hover_color=e.COLOR_PRIMARIO_HOVER if activo else e.COLOR_NEUTRO_HOVER,
                        text_color="#FFFFFF" if activo else e.COLOR_TEXTO)
        self.refrescar()

    def refrescar(self):
        """Se llama al entrar a la pestaña: vuelve a leer los números."""
        refrescar = getattr(self._vistas.get(self._activa), "refrescar", None)
        if callable(refrescar):
            refrescar()