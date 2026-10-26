"""Ranking de clientes: quién compró más, del 1 hasta el último."""
from app.servicios.inventario import _usar, normalizar


def ranking_clientes(texto="", con=None):
    """Clientes guardados ordenados por lo que han comprado.

    Se cuenta el total de cada venta (no anulada), esté o no pagada del todo.
    Orden: más soles comprados primero; si empatan, más compras; si siguen
    empatados, por nombre. Los clientes sin compras quedan al final y no
    tienen puesto (None).

    El puesto no cambia al buscar: si filtras por "juan", Juan sigue siendo
    el puesto que le toca en el ranking completo.

    Devuelve una lista de diccionarios:
    {"puesto", "id", "nombre", "telefono", "dni", "direccion", "compras",
    "total", "ultima"}
    """
    with _usar(con) as c:
        filas = c.execute(
            "SELECT c.id, c.nombre, c.telefono, c.dni, c.direccion, "
            "       COUNT(v.id) AS compras, "
            "       COALESCE(SUM(v.total), 0) AS total, "
            "       MAX(v.fecha) AS ultima "
            "FROM clientes c "
            "LEFT JOIN ventas v ON v.cliente_id = c.id AND v.estado = 'activa' "
            "WHERE c.activo = 1 "
            "GROUP BY c.id "
            "ORDER BY total DESC, compras DESC, c.nombre COLLATE NOCASE, c.id"
        ).fetchall()
    ranking = []
    puesto = 0
    for fila in filas:
        compras = fila["compras"]
        if compras > 0:
            puesto += 1
        ranking.append({
            "puesto": puesto if compras > 0 else None,
            "id": fila["id"], "nombre": fila["nombre"],
            "telefono": fila["telefono"], "dni": fila["dni"],
            "direccion": fila["direccion"], "compras": compras,
            "total": round(fila["total"], 2), "ultima": fila["ultima"]})
    palabras = normalizar(texto).split()
    if palabras:
        ranking = [r for r in ranking
                   if all(p in normalizar(f"{r['nombre']} {r['telefono']} "
                                      f"{r['dni']} {r['direccion']}")
                          for p in palabras)]
    return ranking