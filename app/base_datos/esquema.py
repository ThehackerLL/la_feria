"""Creación de las tablas (Etapa 1: productos y compras; Etapa 2: ventas;
Etapa 5: crédito de clientes; compras: proveedores y deudas a proveedores)."""
from app.base_datos.conexion import transaccion

TABLAS = """
CREATE TABLE IF NOT EXISTS productos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo        TEXT    NOT NULL UNIQUE,
    categoria     TEXT    NOT NULL,
    nombre        TEXT    NOT NULL,
    costo         REAL    NOT NULL DEFAULT 0,
    precio_unidad REAL    NOT NULL DEFAULT 0,
    precio_mayor  REAL    NOT NULL DEFAULT 0,
    stock         INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    stock_minimo  INTEGER NOT NULL DEFAULT 12,
    activo        INTEGER NOT NULL DEFAULT 1,
    creado        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS compras (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha        TEXT NOT NULL,
    proveedor    TEXT,
    total        REAL NOT NULL DEFAULT 0,
    proveedor_id INTEGER REFERENCES proveedores(id)
);

CREATE TABLE IF NOT EXISTS compra_detalle (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id      INTEGER NOT NULL REFERENCES compras(id),
    producto_id    INTEGER NOT NULL REFERENCES productos(id),
    cantidad       INTEGER NOT NULL CHECK (cantidad > 0),
    costo_unitario REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre);

-- Etapa 2: clientes y ventas ------------------------------------------------
CREATE TABLE IF NOT EXISTS clientes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT    NOT NULL,
    telefono TEXT    NOT NULL DEFAULT '',
    activo   INTEGER NOT NULL DEFAULT 1,
    creado   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    dni       TEXT   NOT NULL DEFAULT '',
    direccion TEXT   NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ventas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    cliente_id INTEGER REFERENCES clientes(id),
    subtotal   REAL    NOT NULL DEFAULT 0,
    descuento  REAL    NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    total      REAL    NOT NULL DEFAULT 0 CHECK (total >= 0),
    estado     TEXT    NOT NULL DEFAULT 'activa'
               CHECK (estado IN ('activa', 'anulada'))
);

-- Guarda el precio Y el costo del momento: la ganancia no cambia aunque
-- el costo del producto cambie después.
CREATE TABLE IF NOT EXISTS venta_detalle (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id        INTEGER NOT NULL REFERENCES ventas(id),
    producto_id     INTEGER NOT NULL REFERENCES productos(id),
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    tipo            TEXT    NOT NULL CHECK (tipo IN ('unidad', 'mayor')),
    precio_unitario REAL    NOT NULL CHECK (precio_unitario >= 0),
    costo_unitario  REAL    NOT NULL DEFAULT 0
);

-- Una venta pagada en partes tiene varias filas. Lo que falte por pagar
-- (total menos la suma de pagos) será el crédito de la Etapa 5, y los abonos
-- futuros también entrarán aquí, con su propia fecha.
CREATE TABLE IF NOT EXISTS venta_pagos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id   INTEGER NOT NULL REFERENCES ventas(id),
    fecha      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    forma_pago TEXT    NOT NULL,
    monto      REAL    NOT NULL CHECK (monto > 0)
);

-- Etapa 5: crédito -----------------------------------------------------------
-- Una venta a crédito se paga en 1 a 12 cuotas. Cada cuota guarda su fecha de
-- vencimiento y lo que ya se pagó de ella. El dinero que entra (abono inicial
-- y pagos de cuota) sigue guardándose en venta_pagos, con su propia fecha.
CREATE TABLE IF NOT EXISTS credito_cuotas (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id INTEGER NOT NULL REFERENCES ventas(id),
    numero   INTEGER NOT NULL CHECK (numero >= 1),
    vence    TEXT    NOT NULL,
    monto    REAL    NOT NULL CHECK (monto > 0),
    pagado   REAL    NOT NULL DEFAULT 0 CHECK (pagado >= 0),
    UNIQUE (venta_id, numero)
);

-- Proveedores y compras a crédito ----------------------------------------------
-- A quién le compramos. "vende" es lo que nos provee (por ejemplo "polos").
CREATE TABLE IF NOT EXISTS proveedores (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT    NOT NULL,
    telefono  TEXT    NOT NULL DEFAULT '',
    direccion TEXT    NOT NULL DEFAULT '',
    vende     TEXT    NOT NULL DEFAULT '',
    activo    INTEGER NOT NULL DEFAULT 1,
    creado    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Lo que se paga por una compra (al comprar y después), con su fecha y forma
-- de pago: de aquí sale el dinero que sale de la caja. Las compras anteriores
-- a esta tabla no tienen pagos registrados.
CREATE TABLE IF NOT EXISTS compra_pagos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id  INTEGER NOT NULL REFERENCES compras(id),
    fecha      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    forma_pago TEXT    NOT NULL,
    monto      REAL    NOT NULL CHECK (monto > 0)
);

-- Cuotas de una compra a crédito: lo que se le debe al proveedor.
CREATE TABLE IF NOT EXISTS compra_cuotas (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id INTEGER NOT NULL REFERENCES compras(id),
    numero    INTEGER NOT NULL CHECK (numero >= 1),
    vence     TEXT    NOT NULL,
    monto     REAL    NOT NULL CHECK (monto > 0),
    pagado    REAL    NOT NULL DEFAULT 0 CHECK (pagado >= 0),
    UNIQUE (compra_id, numero)
);

CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha);
CREATE INDEX IF NOT EXISTS idx_detalle_venta ON venta_detalle(venta_id);
CREATE INDEX IF NOT EXISTS idx_pagos_venta ON venta_pagos(venta_id);
CREATE INDEX IF NOT EXISTS idx_pagos_fecha ON venta_pagos(fecha);
CREATE INDEX IF NOT EXISTS idx_cuotas_venta ON credito_cuotas(venta_id);
CREATE INDEX IF NOT EXISTS idx_cuotas_vence ON credito_cuotas(vence);
CREATE INDEX IF NOT EXISTS idx_cpagos_compra ON compra_pagos(compra_id);
CREATE INDEX IF NOT EXISTS idx_cpagos_fecha ON compra_pagos(fecha);
CREATE INDEX IF NOT EXISTS idx_ccuotas_compra ON compra_cuotas(compra_id);
CREATE INDEX IF NOT EXISTS idx_ccuotas_vence ON compra_cuotas(vence);
"""


def _agregar_columnas(con):
    """Agrega a las bases ya existentes las columnas que son nuevas.

    CREATE TABLE IF NOT EXISTS no cambia una tabla que ya existe, así que la
    columna nueva de compras se agrega aquí (sin tocar los datos).
    """
    columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(compras)")}
    if "proveedor_id" not in columnas:
        con.execute("ALTER TABLE compras ADD COLUMN proveedor_id "
                    "INTEGER REFERENCES proveedores(id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_compras_proveedor "
                "ON compras(proveedor_id)")
    # clientes: DNI y dirección (opcionales)
    columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(clientes)")}
    for nombre in ("dni", "direccion"):
        if nombre not in columnas:
            con.execute(f"ALTER TABLE clientes ADD COLUMN {nombre} "
                        "TEXT NOT NULL DEFAULT ''")


def crear_tablas():
    """Crea las tablas si todavía no existen (es seguro llamarla siempre)."""
    with transaccion() as con:
        con.executescript(TABLAS)
        _agregar_columnas(con)