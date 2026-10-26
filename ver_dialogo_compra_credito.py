"""Demo: ventana del plan de cuotas, versión de compra (y la de venta).
No usa tu base de datos."""
import customtkinter as ctk

from app.interfaz import estilos as e
from app.interfaz.dialogo_credito import plan_credito
from app.modelos.proveedor import Proveedor
from app.modelos.cliente import Cliente

e.aplicar_tema()
ventana = ctk.CTk()
ventana.geometry("900x600")
e.configurar_tabla()
ventana.update()

proveedor = Proveedor(1, "Textiles Lima", "999111222")
print("COMPRA:", plan_credito(ventana, 200, proveedor, compra=True))

cliente = Cliente(1, "Juan Pérez", "999111222")
print("VENTA :", plan_credito(ventana, 200, cliente, "Efectivo"))
ventana.destroy()