"""Lógica de ventas: validar lo que se vende, cómo se paga y guardar la venta."""
from app.base_datos.conexion import transaccion
from app.servicios import clientes, creditos, inventario

FORMAS_PAGO = ("Efectivo", "Yape/Plin", "Transferencia", "Tarjeta")
TIPOS_VENTA = ("unidad", "mayor")


def numero_venta(venta_id):
    """1 -> 'V-000001' (el número que se ve en pantalla y en el ticket)."""
    return f"V-{int(venta_id):06d}"


def precio_sugerido(producto, tipo):
    """Precio que se propone al vender: el de unidad o el de por mayor."""
    if tipo not in TIPOS_VENTA:
        raise ValueError("El tipo de venta debe ser unidad o por mayor.")
    return producto.precio_unidad if tipo == "unidad" else producto.precio_mayor


def _a_dinero(valor, texto_error):
    """Convierte a número con 2 decimales, o falla con el mensaje dado."""
    try:
        return round(float(valor), 2)
    except (TypeError, ValueError):
        raise ValueError(texto_error)


def leer_linea(n, item):
    """Valida una línea de la venta (n = número de línea) y la deja limpia.

    item: {"producto_id", "cantidad", "tipo", "precio"}
    """
    try:
        producto_id = int(item["producto_id"])
        cantidad = int(item["cantidad"])
        entero = (cantidad == float(item["cantidad"]))
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Línea {n}: producto o cantidad inválidos.")
    if not entero:
        raise ValueError(f"Línea {n}: la cantidad debe ser un número entero.")
    if cantidad <= 0:
        raise ValueError(f"Línea {n}: la cantidad debe ser mayor a 0.")
    tipo = item.get("tipo")
    if tipo not in TIPOS_VENTA:
        raise ValueError(f"Línea {n}: el tipo de venta debe ser unidad o mayor.")
    # Hasta 6 decimales: una docena a S/ 100 sale a 8.333333 por unidad y así
    # el total de la línea (12 x 8.333333) vuelve a ser exactamente 100.00.
    try:
        precio = round(float(item.get("precio")), 6)
    except (TypeError, ValueError):
        raise ValueError(f"Línea {n}: precio inválido.")
    if precio <= 0:
        raise ValueError(f"Línea {n}: el precio debe ser mayor a 0.")
    return {"producto_id": producto_id, "cantidad": cantidad, "tipo": tipo,
            "precio": precio}


def leer_lineas(items):
    """Valida todas las líneas. Una venta necesita al menos una."""
    if not items:
        raise ValueError("La venta no tiene productos.")
    return [leer_linea(n, item) for n, item in enumerate(items, start=1)]


def calcular_totales(lineas, descuento=0):
    """Devuelve subtotal, descuento y total (con 2 decimales).

    lineas: las que devuelve leer_lineas. El descuento es en soles.
    """
    subtotal = round(sum(l["cantidad"] * l["precio"] for l in lineas), 2)
    descuento = _a_dinero(descuento or 0, "Descuento: no es un número válido.")
    if descuento < 0:
        raise ValueError("El descuento no puede ser negativo.")
    if descuento > subtotal:
        raise ValueError("El descuento no puede ser mayor al subtotal "
                         f"({subtotal:.2f}).")
    return {"subtotal": subtotal, "descuento": descuento,
            "total": round(subtotal - descuento, 2)}


def _limpiar_pagos(pagos):
    """Valida cada pago (forma y monto) y los deja limpios."""
    limpios = []
    for n, pago in enumerate(pagos, start=1):
        forma = pago.get("forma_pago")
        if forma not in FORMAS_PAGO:
            raise ValueError(f"Pago {n}: forma de pago no válida.")
        monto = _a_dinero(pago.get("monto"), f"Pago {n}: monto inválido.")
        if monto <= 0:
            raise ValueError(f"Pago {n}: el monto debe ser mayor a 0.")
        limpios.append({"forma_pago": forma, "monto": monto})
    return limpios


def leer_abono(pagos, total):
    """Abono inicial de una venta a crédito: puede ser 0 (sin pagos).

    Si hay abono debe ser menor al total; si el cliente pagó todo, no es
    un crédito sino una venta normal.
    """
    limpios = _limpiar_pagos(pagos or [])
    abono = round(sum(p["monto"] for p in limpios), 2)
    if abono >= total:
        raise ValueError("El abono inicial debe ser menor al total. Si el "
                         "cliente pagó todo, cobra la venta normal.")
    return limpios


def leer_pagos(pagos, total):
    """Valida las formas de pago: cada una válida y la suma igual al total.

    pagos: lista de {"forma_pago", "monto"}. Una venta pagada en partes
    (efectivo + Yape) tiene varias.
    """
    if not pagos:
        raise ValueError("Elige la forma de pago.")
    limpios = _limpiar_pagos(pagos)
    pagado = round(sum(p["monto"] for p in limpios), 2)
    if pagado > total:
        raise ValueError(f"Lo pagado ({pagado:.2f}) supera el total "
                         f"({total:.2f}).")
    if pagado < total:
        raise ValueError(f"Faltan {total - pagado:.2f} por pagar: lo pagado es "
                         f"{pagado:.2f} y el total {total:.2f}.")
    return limpios


# ------------------------------------------------------------ guardar la venta
def registrar_venta(items, pagos, cliente_id=None, descuento=0, credito=None):
    """Registra una venta completa en una sola operación.

    items:  lista de {"producto_id", "cantidad", "tipo", "precio"}
    pagos:  lista de {"forma_pago", "monto"} (deben sumar el total)
    cliente_id: None = "Público general"
    credito: None = venta normal. Para vender a crédito, un diccionario
            {"cuotas": 1 a 12, "dias": días entre cuotas}. Entonces `pagos`
            es el abono inicial (puede estar vacío = 0), se exige un cliente
            guardado y el resto se reparte en cuotas.

    Guarda la venta, sus líneas (con el costo del momento) y sus pagos, y
    descuenta el stock. Si algo falla, no se guarda nada.
    """
    lineas = leer_lineas(items)
    totales = calcular_totales(lineas, descuento)
    plan = None
    if credito is None:
        pagos = leer_pagos(pagos, totales["total"])
    else:
        if cliente_id is None:
            raise ValueError("Para vender a crédito elige un cliente guardado.")
        pagos = leer_abono(pagos, totales["total"])
        abono = round(sum(p["monto"] for p in pagos), 2)
        saldo = round(totales["total"] - abono, 2)
        plan = creditos.crear_plan(
            saldo, credito.get("cuotas", creditos.CUOTAS_DEFECTO),
            credito.get("dias", creditos.DIAS_DEFECTO))

    with transaccion() as con:
        cliente = None
        if cliente_id is not None:
            cliente = clientes.obtener_cliente(cliente_id, con=con)
            if cliente is None or not cliente.activo:
                raise ValueError("El cliente ya no existe.")

        # Unidades pedidas por producto (un mismo producto puede estar en dos
        # líneas, por ejemplo unas a precio de unidad y otras por mayor).
        pedidas = {}
        for l in lineas:
            pedidas[l["producto_id"]] = pedidas.get(l["producto_id"], 0) \
                + l["cantidad"]
        productos = {}
        for producto_id, cantidad in pedidas.items():
            producto = inventario.obtener_producto(producto_id, con=con)
            if producto is None or not producto.activo:
                raise ValueError("Un producto de la venta ya no está "
                                 "disponible en el inventario.")
            if producto.stock < cantidad:
                raise ValueError(f"{producto.nombre}: solo hay "
                                 f"{producto.stock} en stock y pediste "
                                 f"{cantidad}.")
            productos[producto_id] = producto

        venta_id = con.execute(
            "INSERT INTO ventas (cliente_id, subtotal, descuento, total) "
            "VALUES (?, ?, ?, ?)",
            (cliente_id, totales["subtotal"], totales["descuento"],
             totales["total"])).lastrowid

        utilidad = 0.0
        detalle = []
        for l in lineas:
            producto = productos[l["producto_id"]]
            con.execute(
                "INSERT INTO venta_detalle (venta_id, producto_id, cantidad, "
                "tipo, precio_unitario, costo_unitario) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (venta_id, producto.id, l["cantidad"], l["tipo"], l["precio"],
                 producto.costo))
            utilidad += l["cantidad"] * (l["precio"] - producto.costo)
            detalle.append({
                "codigo": producto.codigo, "nombre": producto.nombre,
                "cantidad": l["cantidad"], "tipo": l["tipo"],
                "precio": l["precio"], "costo": producto.costo,
                "subtotal": round(l["cantidad"] * l["precio"], 2)})

        stock_bajo = []
        for producto_id, cantidad in pedidas.items():
            producto = productos[producto_id]
            actualizado = con.execute(
                "UPDATE productos SET stock = stock - ? "
                "WHERE id = ? AND stock >= ?",
                (cantidad, producto_id, cantidad)).rowcount
            if actualizado != 1:
                raise ValueError(f"{producto.nombre}: el stock cambió y ya no "
                                 "alcanza.")
            restante = producto.stock - cantidad
            if restante <= producto.stock_minimo:
                stock_bajo.append({"codigo": producto.codigo,
                                   "nombre": producto.nombre,
                                   "stock": restante})

        for pago in pagos:
            con.execute("INSERT INTO venta_pagos (venta_id, forma_pago, monto) "
                        "VALUES (?, ?, ?)",
                        (venta_id, pago["forma_pago"], pago["monto"]))
        if plan:
            creditos.guardar_plan(con, venta_id, plan)

        fecha = con.execute("SELECT fecha FROM ventas WHERE id = ?",
                            (venta_id,)).fetchone()["fecha"]

    return {"venta_id": venta_id, "numero": numero_venta(venta_id),
            "fecha": fecha,
            "cliente": cliente.nombre if cliente else clientes.PUBLICO_GENERAL,
            "subtotal": totales["subtotal"], "descuento": totales["descuento"],
            "total": totales["total"],
            "ganancia": round(utilidad - totales["descuento"], 2),
            "lineas": detalle, "pagos": pagos, "stock_bajo": stock_bajo,
            "credito": ({"abono": abono, "saldo": saldo, "cuotas": plan}
                        if plan else None)}