"""Demo: ventana de cierre de caja (de hoy y de un día que quedó sin cerrar).
No usa base de datos: solo muestra las ventanas."""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.dialogo_caja import cerrar_caja

e.aplicar_tema()
ventana = ctk.CTk()
ventana.geometry("900x600")
e.configurar_tabla()
ventana.update()

print("(1) Cierre de hoy, esperado 235. Prueba escribir 235, 230, 240, abc y 12,5.")
print("   ->", cerrar_caja(ventana, "2026-10-21", 235.0))
print("(2) Día anterior sin cerrar. Prueba «Cerrar sin contar».")
print("   ->", cerrar_caja(ventana, "2026-10-20", 80.0, anterior=True))
ventana.destroy()