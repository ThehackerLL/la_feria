"""Lógica de productos y stock."""
import re
import unicodedata
from contextlib import contextmanager

from app import config
from app.base_datos.conexion import transaccion
from app.modelos.producto import Producto

COLUMNAS = ("id, codigo, categoria, nombre, costo, precio_unidad, "
            "precio_mayor, stock, stock_minimo, activo, creado")


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def normalizar(texto):
    """Para comparar: sin tildes, sin mayúsculas, sin espacios repetidos."""
    return " ".join(_sin_tildes(str(texto)).casefold().split())


@contextmanager
def _usar(con):
    """Usa la conexión recibida o abre una transacción propia."""
    if con is not None:
        yield con
    else:
        with transaccion() as nueva:
            yield nueva


def _a_producto(fila):
    return Producto(**dict(fila)) if fila else None


def _obtener(con, producto_id):
    fila = con.execute(f"SELECT {COLUMNAS} FROM productos WHERE id = ?",
                       (producto_id,)).fetchone()
    return _a_producto(fila)

# ------------------------------------------------------------------ códigos
def prefijo_categoria(categoria):
    """'Camisas' -> 'CAM', 'Pantalón' -> 'PAN'."""
    letras = re.sub(r"[^A-Za-z]", "", _sin_tildes(categoria)).upper()
    return (letras[:3] or "GEN").ljust(3, "X")


def _generar_codigo(con, categoria):
    """Siguiente código libre de la categoría. Cuenta también los quitados."""
    prefijo = prefijo_categoria(categoria)
    filas = con.execute("SELECT codigo FROM productos WHERE codigo LIKE ?",
                        (prefijo + "-%",)).fetchall()
    mayor = 0
    for fila in filas:
        m = re.fullmatch(re.escape(prefijo) + r"-(\d+)", fila["codigo"],
                         re.IGNORECASE)
        if m:
            mayor = max(mayor, int(m.group(1)))
    return f"{prefijo}-{mayor + 1:03d}"


def generar_codigo(categoria):
    """Siguiente código libre para una categoría (ej. 'CAM-004')."""
    with _usar(None) as con:
        return _generar_codigo(con, categoria)

# ------------------------------------------------------------------ búsquedas
def obtener_producto(producto_id, con=None):
    with _usar(con) as c:
        return _obtener(c, producto_id)


def buscar_por_codigo(codigo, incluir_inactivos=False, con=None):
    sql = f"SELECT {COLUMNAS} FROM productos WHERE codigo = ?"
    if not incluir_inactivos:
        sql += " AND activo = 1"
    with _usar(con) as c:
        return _a_producto(c.execute(sql, (codigo.strip().upper(),)).fetchone())


def buscar_por_nombre(nombre, incluir_inactivos=False, con=None):
    """Busca un producto por nombre exacto (sin importar mayúsculas ni tildes)."""
    buscado = normalizar(nombre)
    sql = f"SELECT {COLUMNAS} FROM productos"
    if not incluir_inactivos:
        sql += " WHERE activo = 1"
    with _usar(con) as c:
        for fila in c.execute(sql):
            if normalizar(fila["nombre"]) == buscado:
                return _a_producto(fila)
    return None


def buscar_existente(codigo="", nombre="", incluir_inactivos=True, con=None):
    """Si hay código, busca por código. Si no, por nombre exacto."""
    if codigo and codigo.strip():
        return buscar_por_codigo(codigo, incluir_inactivos, con)
    if nombre and nombre.strip():
        return buscar_por_nombre(nombre, incluir_inactivos, con)
    return None


def buscar_productos(texto="", solo_bajo_stock=False, con=None):
    """Lista productos activos. Cada palabra escrita debe aparecer en el
    código, el nombre o la categoría (en cualquier orden)."""
    palabras = normalizar(texto).split()
    with _usar(con) as c:
        filas = c.execute(f"SELECT {COLUMNAS} FROM productos WHERE activo = 1 "
                          "ORDER BY categoria, codigo").fetchall()
    resultado = []
    for fila in filas:
        p = _a_producto(fila)
        if solo_bajo_stock and not p.bajo_stock:
            continue
        campos = normalizar(f"{p.codigo} {p.nombre} {p.categoria}")
        if all(palabra in campos for palabra in palabras):
            resultado.append(p)
    return resultado


def listar_categorias(con=None):
    with _usar(con) as c:
        filas = c.execute("SELECT DISTINCT categoria FROM productos "
                          "WHERE activo = 1 ORDER BY categoria").fetchall()
    return [f["categoria"] for f in filas]

# --------------------------------------------------------------------- crear
def _categoria_canonica(con, categoria):
    """Si 'camisas' ya existe como 'Camisas', reutiliza la forma existente."""
    categoria = " ".join(categoria.split())
    for fila in con.execute("SELECT DISTINCT categoria FROM productos"):
        if normalizar(fila["categoria"]) == normalizar(categoria):
            return fila["categoria"]
    return categoria


def _nombre_repetido(con, nombre, excepto_id=None):
    """Devuelve el producto que ya usa ese nombre, o None."""
    buscado = normalizar(nombre)
    for fila in con.execute(f"SELECT {COLUMNAS} FROM productos"):
        if fila["id"] != excepto_id and normalizar(fila["nombre"]) == buscado:
            return _a_producto(fila)
    return None


def _validar(nombre, categoria, costo, precio_unidad, precio_mayor,
             stock, stock_minimo):
    nombre = " ".join(str(nombre).split())
    categoria = " ".join(str(categoria).split())
    if not nombre:
        raise ValueError("Escribe el nombre del producto.")
    if not categoria:
        raise ValueError("Escribe la categoría del producto.")
    if min(costo, precio_unidad, precio_mayor) < 0:
        raise ValueError("Costo y precios no pueden ser negativos.")
    if stock < 0 or stock_minimo < 0:
        raise ValueError("El stock no puede ser negativo.")
    return nombre, categoria


def crear_producto(nombre, categoria, costo=0, precio_unidad=0, precio_mayor=0,
                   stock=0, stock_minimo=None, codigo="", con=None):
    """Crea un producto. Si no se da código, se genera uno automático."""
    if stock_minimo is None:
        stock_minimo = config.STOCK_MINIMO_DEFECTO
    nombre, categoria = _validar(nombre, categoria, costo, precio_unidad,
                                 precio_mayor, stock, stock_minimo)
    with _usar(con) as c:
        repetido = _nombre_repetido(c, nombre)
        if repetido:
            quitado = "" if repetido.activo else (
                " (está quitado: cómpralo de nuevo para reactivarlo)")
            raise ValueError(f"Ya existe un producto con ese nombre: "
                             f"{repetido.codigo}{quitado}.")
        categoria = _categoria_canonica(c, categoria)
        codigo = (codigo or "").strip().upper() or _generar_codigo(c, categoria)
        if c.execute("SELECT 1 FROM productos WHERE codigo = ?",
                     (codigo,)).fetchone():
            raise ValueError(f"El código {codigo} ya existe.")
        cur = c.execute(
            "INSERT INTO productos (codigo, categoria, nombre, costo, "
            "precio_unidad, precio_mayor, stock, stock_minimo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (codigo, categoria, nombre, costo, precio_unidad, precio_mayor,
             stock, stock_minimo))
        return _obtener(c, cur.lastrowid)
    


# ---------------------------------------------------------- editar y quitar
def actualizar_producto(producto_id, nombre, categoria, costo, precio_unidad,
                        precio_mayor, stock, stock_minimo, codigo=""):
    """Edita un producto. Si el código viene vacío, se conserva el actual."""
    nombre, categoria = _validar(nombre, categoria, costo, precio_unidad,
                                 precio_mayor, stock, stock_minimo)
    with _usar(None) as c:
        actual = _obtener(c, producto_id)
        if actual is None:
            raise ValueError("El producto ya no existe.")
        repetido = _nombre_repetido(c, nombre, excepto_id=producto_id)
        if repetido:
            quitado = "" if repetido.activo else (
                " (está quitado: cómpralo de nuevo para reactivarlo)")
            raise ValueError(f"Ya existe otro producto con ese nombre: "
                             f"{repetido.codigo}{quitado}.")
        categoria = _categoria_canonica(c, categoria)
        codigo = (codigo or "").strip().upper() or actual.codigo
        otro = c.execute("SELECT 1 FROM productos WHERE codigo = ? AND id != ?",
                         (codigo, producto_id)).fetchone()
        if otro:
            raise ValueError(f"El código {codigo} ya lo usa otro producto.")
        c.execute(
            "UPDATE productos SET codigo=?, categoria=?, nombre=?, costo=?, "
            "precio_unidad=?, precio_mayor=?, stock=?, stock_minimo=? "
            "WHERE id=?",
            (codigo, categoria, nombre, costo, precio_unidad, precio_mayor,
             stock, stock_minimo, producto_id))
        return _obtener(c, producto_id)


def desactivar_producto(producto_id):
    """'Quita' un producto sin perder su historial (queda oculto)."""
    with _usar(None) as c:
        c.execute("UPDATE productos SET activo = 0 WHERE id = ?",
                  (producto_id,))


# ------------------------------------------------------------------- resumen
def resumen_stock(con=None):
    """Totales para las tarjetas de la pantalla de inventario."""
    with _usar(con) as c:
        fila = c.execute(
            "SELECT COUNT(*) AS productos, "
            "COALESCE(SUM(stock), 0) AS unidades, "
            "COALESCE(SUM(stock * costo), 0) AS valor, "
            "COALESCE(SUM(CASE WHEN stock <= stock_minimo THEN 1 ELSE 0 END), 0) "
            "AS bajo_stock FROM productos WHERE activo = 1").fetchone()
    return {"productos": fila["productos"], "unidades": fila["unidades"],
            "valor": round(fila["valor"], 2), "bajo_stock": fila["bajo_stock"]}