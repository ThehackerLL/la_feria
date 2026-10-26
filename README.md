# La Feria - Sistema de inventario y ventas

Programa de escritorio (Windows) para tienda mayorista de ropa.
Python + CustomTkinter + SQLite + openpyxl + python-escpos.

## Estructura

- `main.py`: punto de entrada
- `app/base_datos/`: conexión SQLite y creación de tablas
- `app/modelos/`: producto, cliente, venta, pago, envío
- `app/servicios/`: lógica (inventario, compras, ventas, créditos, envíos, reportes, excel, ticket, respaldo, seguridad)
- `app/interfaz/`: ventana principal, estilos y pantallas
- `app/utilidades/`: formatos y validaciones
- `datos/`: base de datos (`.db`)
- `reportes/`: Excel diarios
- `respaldos/`: copias de seguridad
- `recursos/`: logo e iconos
- `pruebas/`: pruebas automáticas

## Cómo abrirlo en VS Code

1. Descomprime la carpeta y abre `la_feria` con *File > Open Folder*.
2. Terminal (Ctrl+Ñ): `python -m venv venv`
3. Activar: `venv\Scripts\activate`
4. Instalar: `pip install -r requirements.txt`
5. Ejecutar: `python main.py`

## Etapas

1. Base de datos, productos y stock
2. Ventas
3. Ticket (BT-58B)
4. Excel y cierre de caja
5. Crédito y envíos
6. Respaldo e instalador .exe
