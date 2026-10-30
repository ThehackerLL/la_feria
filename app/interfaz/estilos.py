"""Estilo único de la aplicación: colores, fuentes, medidas y tablas.

Todo lo visual sale de aquí. Si el cliente pide otro color, se cambia en
este archivo y cambia en toda la aplicación.
"""
import customtkinter as ctk
from tkinter import ttk

# ------------------------------------------------------------------ fuentes
FUENTE = "Segoe UI"
TAM_TEXTO = 13
TAM_TITULO = 20
TAM_SUBTITULO = 15
TAM_PEQUENO = 12
TAM_CIFRA = 24

# ------------------------------------------------------------------ colores
# Base: morado de La Feria sobre fondo claro tipo tiza.
COLOR_FONDO = "#F4F5F7"          # fondo de ventanas
COLOR_TARJETA = "#FFFFFF"        # tarjetas, formularios, tablas
COLOR_BORDE = "#D9DDE3"          # bordes finos
COLOR_TEXTO = "#1B2430"
COLOR_TEXTO_SUAVE = "#5B6675"

COLOR_PRIMARIO = "#6A0080"       # morado
COLOR_PRIMARIO_HOVER = "#550066"
COLOR_PRIMARIO_SUAVE = "#F3E5F7"  # fila seleccionada, pestaña activa

COLOR_OK = "#198754"
COLOR_OK_HOVER = "#146C43"
COLOR_OK_FONDO = "#E3F4EA"

COLOR_AVISO = "#B45309"          # stock bajo
COLOR_AVISO_FONDO = "#FEF3C7"

COLOR_PELIGRO = "#B42318"        # agotado, errores, anular
COLOR_PELIGRO_HOVER = "#912018"
COLOR_PELIGRO_FONDO = "#FDE8E6"

COLOR_NEUTRO = "#E5E7EB"         # botón secundario
COLOR_NEUTRO_HOVER = "#D1D5DB"
COLOR_PESTANA_HOVER = "#E8D3EE"   # al pasar el mouse por una pestaña

# ------------------------------------------------------------------ medidas
RADIO = 8            # esquinas de botones, campos y tarjetas
ALTO_CONTROL = 36    # alto de botones y campos
ALTO_FILA = 30       # alto de fila en tablas
ESPACIO = 12         # separación estándar
MARGEN = 16          # margen de pantallas


def _fijar(seccion, **valores):
    """Cambia valores del tema global de CustomTkinter."""
    tema = ctk.ThemeManager.theme[seccion]
    for clave, valor in valores.items():
        tema[clave] = valor


def aplicar_tema():
    """Se llama UNA vez, antes de crear la ventana principal."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    t = ctk.ThemeManager.theme

    t["CTkFont"]["family"] = FUENTE
    t["CTkFont"]["size"] = TAM_TEXTO

    _fijar("CTk", fg_color=COLOR_FONDO)
    _fijar("CTkToplevel", fg_color=COLOR_FONDO)
    _fijar("CTkFrame", corner_radius=RADIO, fg_color=COLOR_TARJETA,
           top_fg_color=COLOR_FONDO, border_color=COLOR_BORDE)
    _fijar("CTkLabel", text_color=COLOR_TEXTO, fg_color="transparent")
    _fijar("CTkButton", corner_radius=RADIO, border_width=0,
           fg_color=COLOR_PRIMARIO, hover_color=COLOR_PRIMARIO_HOVER,
           text_color="#FFFFFF", text_color_disabled="#9AA3B2")
    _fijar("CTkEntry", corner_radius=RADIO, border_width=1,
           fg_color="#FFFFFF", border_color=COLOR_BORDE,
           text_color=COLOR_TEXTO, placeholder_text_color="#6B7280")
    _fijar("CTkComboBox", corner_radius=RADIO, border_width=1,
           fg_color="#FFFFFF", border_color=COLOR_BORDE,
           button_color=COLOR_NEUTRO, button_hover_color=COLOR_NEUTRO_HOVER,
           text_color=COLOR_TEXTO)
    _fijar("CTkOptionMenu", corner_radius=RADIO, fg_color=COLOR_NEUTRO,
           button_color=COLOR_NEUTRO, button_hover_color=COLOR_NEUTRO_HOVER,
           text_color=COLOR_TEXTO)
    _fijar("DropdownMenu", fg_color="#FFFFFF", hover_color=COLOR_PRIMARIO_SUAVE,
           text_color=COLOR_TEXTO)
    _fijar("CTkCheckBox", corner_radius=5, border_color=COLOR_BORDE,
           fg_color=COLOR_PRIMARIO, hover_color=COLOR_PRIMARIO_HOVER,
           text_color=COLOR_TEXTO)
    _fijar("CTkScrollbar", corner_radius=RADIO, fg_color="transparent",
           button_color="#C3C9D3", button_hover_color="#A5ADBA")
    _fijar("CTkTextbox", corner_radius=RADIO, border_width=1,
           fg_color="#FFFFFF", border_color=COLOR_BORDE, text_color=COLOR_TEXTO)


def configurar_tabla():
    """Estilo de las tablas. Se llama después de crear la ventana."""
    estilo = ttk.Style()
    estilo.theme_use("clam")
    estilo.configure("Feria.Treeview", rowheight=ALTO_FILA,
                     font=(FUENTE, 11), background=COLOR_TARJETA,
                     fieldbackground=COLOR_TARJETA, foreground=COLOR_TEXTO,
                     borderwidth=0, relief="flat")