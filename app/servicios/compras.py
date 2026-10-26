"""Registro de compras: crea productos nuevos o suma stock a los existentes."""
from datetime import datetime

from app.base_datos.conexion import transaccion
from app.servicios import creditos, inventario, proveedores

# Orden en que se ofrecen las formas de pago al comprar (se compra por
# internet a Lima: primero transferencia y Yape/Plin, y por último efectivo).
FORMAS_PAGO_COMPRA = ("Transferencia", "Yape/Plin", "Tarjeta", "Efectivo")


def _leer_linea(n, item):
    """Convierte y valida una línea de la compra (n = número de línea)."""
    try:
        cantidad = int(item["cantidad"])
        costo = float(item.get("costo") or 0)
        precio_unidad = float(item.get("precio_unidad") or 0)
        precio_mayor = float(item.get("precio_mayor") or 0)
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Línea {n}: cantidad o precios inválidos.")
    if cantidad != float(item["cantidad"]):
        raise ValueError(f"Línea {n}: la cantidad debe ser un número entero.")
    if cantidad <= 0:
        raise ValueError(f"Línea {n}: la cantidad debe ser mayor a 0.")
    if min(costo, precio_unidad, precio_mayor) < 0:
        raise ValueError(f"Línea {n}: los precios no pueden ser negativos.")
    return cantidad, costo, precio_unidad, precio_mayor


def _limpiar_pagos(pagos):
    """Valida cada pago (forma y monto) y los deja limpios."""
    limpios = []
    for n, pago in enumerate(pagos, start=1):
        forma = pago.get("forma_pago")
        if forma not in FORMAS_PAGO_COMPRA:
            raise ValueError(f"Pago {n}: forma de pago no válida.")
        try:
            monto = round(float(pago.get("monto")), 2)
        except (TypeError, ValueError):
            raise ValueError(f"Pago {n}: monto inválido.")
        if monto <= 0:
            raise ValueError(f"Pago {n}: el monto debe ser mayor a 0.")
        limpios.append({"forma_pago": forma, "monto": monto})
    return limpios


def total_compra(items, con=None):
    """Total en soles que costará la compra, calculado igual que al guardarla:
    si el costo de un producto que ya existe queda vacío, se usa el actual.

    Sirve para mostrar el total (y repartirlo en cuotas) antes de guardar.
    """
    total = 0.0
    with inventario._usar(con) as c:
        for n, item in enumerate(items, start=1):
            cantidad, costo, _pu, _pm = _leer_linea(n, item)
            existente = inventario.buscar_existente(
                item.get("codigo") or "", item.get("nombre") or "",
                incluir_inactivos=True, con=c)
            if existente:
                costo = costo or existente.costo
            total += cantidad * costo
    return round(total, 2)


def registrar_compra(items, proveedor="", pagos=None, proveedor_id=None,
                     credito=None):
    """Registra una compra completa en una sola operación.

    Cada item es un diccionario con:
        codigo (opcional), nombre, categoria, cantidad, costo,
        precio_unidad, precio_mayor

    - Si el producto ya existe (por código, o por nombre si no hay código),
      se SUMA la cantidad al stock y el costo pasa a ser el PROMEDIO
      PONDERADO entre lo que había y lo que entra.
    - Si no existe, se crea con la cantidad como stock inicial.
    - Si algo falla, no se guarda nada de la compra.

    Cómo se paga:
        pagos: lista de {"forma_pago", "monto"} (formas de FORMAS_PAGO_COMPRA).
               En una compra al contado deben sumar el total. Si es None no se
               registra ningún pago (así se guardaban las compras antes).
        proveedor_id: el proveedor guardado (su nombre pasa a `proveedor`).
               Es opcional al contado y OBLIGATORIO a crédito.
        credito: None = al contado. Para comprar a crédito, un diccionario
               {"cuotas": 1 a 12, "dias": días entre cuotas}. Entonces `pagos`
               es lo pagado al recibir (puede estar vacío = 0), se exige un
               y el resto se reparte en cuotas.
    """
    if not items:
        raise ValueError("La compra no tiene productos.")
    if credito is not None and proveedor_id is None:
        raise ValueError("Para comprar a crédito elige un proveedor guardado: "
                         "hay que saber a quién se le debe.")
    if pagos is not None:
        pagos = _limpiar_pagos(pagos)
    elif credito is not None:
        pagos = []
    if credito is None and pagos is not None and not pagos:
        raise ValueError("Elige la forma de pago.")

    with transaccion() as con:
        if proveedor_id is not None:
            guardado = proveedores.obtener_proveedor(proveedor_id, con=con)
            if guardado is None or not guardado.activo:
                raise ValueError("El proveedor ya no existe.")
            proveedor = guardado.nombre
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        compra_id = con.execute(
            "INSERT INTO compras (fecha, proveedor, total, proveedor_id) "
            "VALUES (?, ?, 0, ?)",
            (fecha, (proveedor or "").strip(), proveedor_id)).lastrowid

        total = 0.0
        lineas = []
        for n, item in enumerate(items, start=1):
            cantidad, costo, precio_unidad, precio_mayor = _leer_linea(n, item)
            existente = inventario.buscar_existente(
                item.get("codigo") or "", item.get("nombre") or "",
                incluir_inactivos=True, con=con)

            if existente:
                costo = costo or existente.costo      # costo vacío: asume el actual
                # Promedio ponderado: (stock x costo + cantidad x costo nuevo) / total
                costo_nuevo = round(
                    (existente.stock * existente.costo + cantidad * costo)
                    / (existente.stock + cantidad), 2)
                con.execute(
                    "UPDATE productos SET stock = stock + ?, costo = ?, "
                    "precio_unidad = ?, precio_mayor = ?, activo = 1 "
                    "WHERE id = ?",
                    (cantidad, costo_nuevo,
                     precio_unidad or existente.precio_unidad,
                     precio_mayor or existente.precio_mayor,
                     existente.id))
                producto = existente
                antes, accion = existente.stock, "sumado"
                costo_antes, costo_despues = existente.costo, costo_nuevo
            else:
                try:
                    producto = inventario.crear_producto(
                        nombre=item.get("nombre") or "",
                        categoria=item.get("categoria") or "",
                        costo=costo, precio_unidad=precio_unidad,
                        precio_mayor=precio_mayor, stock=cantidad,
                        codigo=item.get("codigo") or "", con=con)
                except ValueError as error:
                    raise ValueError(f"Línea {n}: {error}")
                antes, accion = 0, "creado"
                costo_antes = costo_despues = costo

            con.execute(
                "INSERT INTO compra_detalle (compra_id, producto_id, cantidad, "
                "costo_unitario) VALUES (?, ?, ?, ?)",
                (compra_id, producto.id, cantidad, costo))
            total += cantidad * costo
            lineas.append({"codigo": producto.codigo, "nombre": producto.nombre,
                           "accion": accion, "stock_antes": antes,
                           "stock_despues": antes + cantidad,
                           "costo_antes": costo_antes,
                           "costo_despues": costo_despues})

        total = round(total, 2)
        con.execute("UPDATE compras SET total = ? WHERE id = ?",
                    (total, compra_id))

        # Lo pagado y, si es a crédito, las cuotas. Si no cuadra, se deshace
        # toda la compra (también el stock).
        plan = abono = saldo = None
        if credito is not None:
            abono = round(sum(p["monto"] for p in pagos), 2)
            if abono >= total:
                raise ValueError("Lo pagado al recibir debe ser menor al total. "
                                 "Si ya pagaste todo, registra la compra al "
                                 "contado.")
            saldo = round(total - abono, 2)
            plan = creditos.crear_plan(
                saldo, credito.get("cuotas", creditos.CUOTAS_DEFECTO),
                credito.get("dias", creditos.DIAS_DEFECTO))
        elif pagos and total > 0:
            pagado = round(sum(p["monto"] for p in pagos), 2)
            if pagado > total:
                raise ValueError(f"Lo pagado ({pagado:.2f}) supera el total "
                                 f"({total:.2f}).")
            if pagado < total:
                raise ValueError(f"Faltan {total - pagado:.2f} por pagar: lo "
                                 f"pagado es {pagado:.2f} y el total "
                                 f"{total:.2f}.")
        elif pagos:
            raise ValueError("El total de la compra es 0: no hay nada que "
                             "pagar. Escribe el costo de los productos.")
        for pago in pagos or []:
            con.execute("INSERT INTO compra_pagos (compra_id, forma_pago, "
                        "monto) VALUES (?, ?, ?)",
                        (compra_id, pago["forma_pago"], pago["monto"]))
        for cuota in plan or []:
            con.execute("INSERT INTO compra_cuotas (compra_id, numero, vence, "
                        "monto) VALUES (?, ?, ?, ?)",
                        (compra_id, cuota["numero"], cuota["vence"],
                         cuota["monto"]))

    return {"compra_id": compra_id, "total": total, "lineas": lineas,
            "creados": sum(1 for l in lineas if l["accion"] == "creado"),
            "actualizados": sum(1 for l in lineas if l["accion"] == "sumado"),
            "proveedor": (proveedor or "").strip(), "pagos": pagos or [],
            "credito": ({"abono": abono, "saldo": saldo, "cuotas": plan}
                        if plan else None)}