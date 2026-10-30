"""Seguridad: usuarios con contraseña y la contraseña del dueño (para la ganancia).

- Al abrir el programa se entra con USUARIO + CONTRASEÑA. Cada persona que
  vende tiene su usuario; su nombre queda anotado en lo que registra.
- Los usuarios se llaman «Analista-NombreDeLaPersona»: se escribe solo el
  nombre («marta pérez») y queda «Analista-MartaPérez».
- La ganancia se protege con otra contraseña, la del DUEÑO. Al escribirla bien,
  la ganancia queda visible 60 segundos y luego se oculta sola.
- Las contraseñas nunca se guardan: solo su «huella» (PBKDF2 con sal).
- Clave de recuperación: se muestra UNA vez al crear la primera cuenta. Sirve
  para volver a poner una contraseña olvidada sin perder datos.
- Tras 5 contraseñas malas seguidas, se bloquea 30 segundos.

Las tablas se crean solas (CREATE TABLE IF NOT EXISTS).
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from app.servicios.inventario import _usar, normalizar

PREFIJO_USUARIO = "Analista-"
SEGUNDOS_GANANCIA = 60
INTENTOS_MAXIMOS = 5
SEGUNDOS_BLOQUEO = 30
MIN_CLAVE = 4
_VUELTAS = 200_000
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"     # sin 0/O ni 1/I (se confunden)

_TABLAS = """
CREATE TABLE IF NOT EXISTS usuarios (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    sal    TEXT NOT NULL,
    huella TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1,
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seguridad_ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

# Estado en memoria (se pierde al cerrar el programa, a propósito).
_estado = {"usuario": None, "ganancia_hasta": None, "fallos": 0,
           "bloqueado_hasta": None}


def reiniciar_estado():
    """Cierra la sesión y bloquea la ganancia (también la usan las pruebas)."""
    _estado.update(usuario=None, ganancia_hasta=None, fallos=0,
                   bloqueado_hasta=None)


def _preparar(con):
    con.executescript(_TABLAS)
    return con


def _ahora(ahora):
    return ahora or datetime.now()


# ----------------------------------------------------------------- huellas
def _huella(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"),
                               bytes.fromhex(sal), _VUELTAS).hex()


def _nueva_huella(clave):
    sal = secrets.token_hex(16)
    return sal, _huella(clave, sal)


def _coincide(clave, sal, huella):
    return hmac.compare_digest(_huella(clave, sal), huella)


def _validar_clave(clave, que="La contraseña"):
    if not isinstance(clave, str) or len(clave) < MIN_CLAVE:
        raise ValueError(f"{que} debe tener al menos {MIN_CLAVE} caracteres.")


def formato_nombre(nombre):
    """'marta pérez' -> 'Analista-MartaPérez' (también acepta 'analista-marta').

    Falla con ValueError si no queda ningún nombre.
    """
    texto = " ".join(str(nombre or "").split())
    if normalizar(texto).startswith(normalizar(PREFIJO_USUARIO)):
        texto = texto[len(PREFIJO_USUARIO):]
    palabras = [p for p in re.split(r"[\s\-]+", texto) if p]
    if not palabras:
        raise ValueError("Escribe el nombre del usuario.")
    return PREFIJO_USUARIO + "".join(p[0].upper() + p[1:].lower()
                                     for p in palabras)


def _validar_nombre(nombre):
    nombre = formato_nombre(nombre)
    if len(nombre) > 40:
        raise ValueError("El nombre del usuario es muy largo.")
    return nombre


# ------------------------------------------------------------ ajustes (dueño)
def _leer(con, clave):
    f = con.execute("SELECT valor FROM seguridad_ajustes WHERE clave = ?",
                    (clave,)).fetchone()
    return f["valor"] if f else None


def _guardar(con, clave, valor):
    con.execute("INSERT INTO seguridad_ajustes (clave, valor) VALUES (?, ?) "
                "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                (clave, valor))


def _guardar_clave_dueno(con, clave):
    sal, huella = _nueva_huella(clave)
    _guardar(con, "dueno_sal", sal)
    _guardar(con, "dueno_huella", huella)


def _nueva_recuperacion(con):
    """Crea y guarda una clave de recuperación nueva. Devuelve el texto."""
    texto = "".join(secrets.choice(_ALFABETO) for _ in range(16))
    sal, huella = _nueva_huella(texto)
    _guardar(con, "rec_sal", sal)
    _guardar(con, "rec_huella", huella)
    return "-".join(texto[i:i + 4] for i in range(0, 16, 4))


def _limpiar_recuperacion(texto):
    return re.sub(r"[\s\-]", "", str(texto or "")).upper()


# ------------------------------------------------------------ primer arranque
def hay_configuracion(con=None):
    """True si ya se creó la primera cuenta (usuario y clave del dueño)."""
    with _usar(con) as c:
        _preparar(c)
        return (_leer(c, "dueno_huella") is not None and c.execute(
            "SELECT 1 FROM usuarios WHERE activo = 1").fetchone() is not None)


def configurar_primera_vez(nombre, clave_usuario, clave_dueno, con=None):
    """Crea el primer usuario y la contraseña del dueño.

    Devuelve la clave de recuperación (se muestra una sola vez: hay que
    guardarla).
    """
    nombre = _validar_nombre(nombre)
    _validar_clave(clave_usuario, "La contraseña del usuario")
    _validar_clave(clave_dueno, "La contraseña del dueño")
    if clave_usuario == clave_dueno:
        raise ValueError("La contraseña del dueño debe ser distinta a la del "
                         "usuario.")
    with _usar(con) as c:
        _preparar(c)
        if hay_configuracion(c):
            raise ValueError("El programa ya tiene usuarios creados.")
        sal, huella = _nueva_huella(clave_usuario)
        c.execute("INSERT INTO usuarios (nombre, sal, huella, creado) "
                  "VALUES (?, ?, ?, ?)",
                  (nombre, sal, huella,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        _guardar_clave_dueno(c, clave_dueno)
        return _nueva_recuperacion(c)


# ------------------------------------------------------------------ bloqueo
def _revisar_bloqueo(ahora):
    hasta = _estado["bloqueado_hasta"]
    if hasta and ahora < hasta:
        resta = int((hasta - ahora).total_seconds()) + 1
        raise ValueError(f"Demasiados intentos. Espera {resta} segundos.")
    if hasta:
        _estado["bloqueado_hasta"], _estado["fallos"] = None, 0


def _fallo(ahora):
    _estado["fallos"] += 1
    if _estado["fallos"] >= INTENTOS_MAXIMOS:
        _estado["bloqueado_hasta"] = ahora + timedelta(seconds=SEGUNDOS_BLOQUEO)


def _acierto():
    _estado["fallos"] = 0
    _estado["bloqueado_hasta"] = None


# ----------------------------------------------------------------- usuarios
def _buscar_usuario(c, nombre):
    """El usuario activo con ese nombre (sirve «marta» o «Analista-Marta»)."""
    try:
        buscado = normalizar(formato_nombre(nombre))
    except ValueError:
        return None
    return next((f for f in c.execute(
        "SELECT * FROM usuarios WHERE activo = 1")
        if normalizar(f["nombre"]) == buscado), None)


def listar_usuarios(con=None):
    """Usuarios activos [{'id', 'nombre'}], por orden alfabético."""
    with _usar(con) as c:
        _preparar(c)
        return [{"id": f["id"], "nombre": f["nombre"]} for f in c.execute(
            "SELECT id, nombre FROM usuarios WHERE activo = 1 "
            "ORDER BY nombre COLLATE NOCASE")]


def iniciar_sesion(nombre, clave, ahora=None, con=None):
    """Entra al programa. Devuelve {'id', 'nombre'} o falla con ValueError."""
    ahora = _ahora(ahora)
    _revisar_bloqueo(ahora)
    with _usar(con) as c:
        _preparar(c)
        u = _buscar_usuario(c, nombre)
    if u is None or not _coincide(str(clave or ""), u["sal"], u["huella"]):
        _fallo(ahora)
        raise ValueError("Usuario o contraseña incorrectos.")
    _acierto()
    _estado["usuario"] = {"id": u["id"], "nombre": u["nombre"]}
    return dict(_estado["usuario"])


def usuario_actual():
    """El usuario que entró ({'id', 'nombre'}) o None."""
    return dict(_estado["usuario"]) if _estado["usuario"] else None


def nombre_usuario():
    """Nombre de quien está en el programa ('' si nadie entró)."""
    return _estado["usuario"]["nombre"] if _estado["usuario"] else ""


def cerrar_sesion():
    reiniciar_estado()


def crear_usuario(nombre, clave, con=None):
    """Agrega un usuario nuevo. Devuelve su id."""
    nombre = _validar_nombre(nombre)
    _validar_clave(clave, "La contraseña del usuario")
    with _usar(con) as c:
        _preparar(c)
        if _buscar_usuario(c, nombre):
            raise ValueError(f"Ya existe un usuario llamado «{nombre}».")
        if _leer(c, "dueno_huella") and _coincide(
                clave, _leer(c, "dueno_sal"), _leer(c, "dueno_huella")):
            raise ValueError("Esa contraseña es la del dueño: elige otra.")
        sal, huella = _nueva_huella(clave)
        return c.execute(
            "INSERT INTO usuarios (nombre, sal, huella, creado) VALUES (?, ?, ?, ?)",
            (nombre, sal, huella,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))).lastrowid


def cambiar_clave_usuario(nombre, clave_actual, clave_nueva, con=None):
    """El usuario cambia su propia contraseña (pide la actual)."""
    _validar_clave(clave_nueva, "La contraseña nueva")
    with _usar(con) as c:
        _preparar(c)
        u = _buscar_usuario(c, nombre)
        if u is None or not _coincide(str(clave_actual or ""), u["sal"],
                                      u["huella"]):
            raise ValueError("La contraseña actual no es correcta.")
        if _leer(c, "dueno_huella") and _coincide(
                clave_nueva, _leer(c, "dueno_sal"), _leer(c, "dueno_huella")):
            raise ValueError("Esa contraseña es la del dueño: elige otra.")
        sal, huella = _nueva_huella(clave_nueva)
        c.execute("UPDATE usuarios SET sal = ?, huella = ? WHERE id = ?",
                  (sal, huella, u["id"]))


def quitar_usuario(usuario_id, con=None):
    """Desactiva un usuario (su nombre sigue en lo que ya registró).

    No deja quitar al usuario que está dentro ni al último que queda.
    """
    with _usar(con) as c:
        _preparar(c)
        u = c.execute("SELECT id FROM usuarios WHERE id = ? AND activo = 1",
                      (usuario_id,)).fetchone()
        if u is None:
            raise ValueError("Ese usuario ya no existe.")
        if _estado["usuario"] and _estado["usuario"]["id"] == usuario_id:
            raise ValueError("No puedes quitar al usuario con el que entraste.")
        if c.execute("SELECT COUNT(*) FROM usuarios WHERE activo = 1"
                     ).fetchone()[0] <= 1:
            raise ValueError("Debe quedar al menos un usuario.")
        c.execute("UPDATE usuarios SET activo = 0 WHERE id = ?", (usuario_id,))


# --------------------------------------------------------- ganancia (dueño)
def desbloquear_ganancia(clave, ahora=None, con=None):
    """Si la contraseña del dueño es correcta, la ganancia se ve 60 segundos.

    Devuelve True; si no es correcta, falla con ValueError.
    """
    ahora = _ahora(ahora)
    _revisar_bloqueo(ahora)
    with _usar(con) as c:
        _preparar(c)
        sal, huella = _leer(c, "dueno_sal"), _leer(c, "dueno_huella")
    if huella is None or not _coincide(str(clave or ""), sal, huella):
        _fallo(ahora)
        raise ValueError("Contraseña del dueño incorrecta.")
    _acierto()
    _estado["ganancia_hasta"] = ahora + timedelta(seconds=SEGUNDOS_GANANCIA)
    return True


def ganancia_visible(ahora=None):
    """True mientras dure el desbloqueo (60 segundos)."""
    hasta = _estado["ganancia_hasta"]
    return bool(hasta and _ahora(ahora) < hasta)


def segundos_restantes(ahora=None):
    """Segundos que le quedan a la ganancia visible (0 si está oculta)."""
    hasta = _estado["ganancia_hasta"]
    if not hasta:
        return 0
    return max(0, int((hasta - _ahora(ahora)).total_seconds() + 0.999))


def ocultar_ganancia():
    _estado["ganancia_hasta"] = None


def cambiar_clave_dueno(clave_actual, clave_nueva, con=None):
    """El dueño cambia su contraseña (pide la actual)."""
    _validar_clave(clave_nueva, "La contraseña del dueño")
    with _usar(con) as c:
        _preparar(c)
        sal, huella = _leer(c, "dueno_sal"), _leer(c, "dueno_huella")
        if huella is None or not _coincide(str(clave_actual or ""), sal, huella):
            raise ValueError("La contraseña actual del dueño no es correcta.")
        _no_igual_a_usuarios(c, clave_nueva)
        _guardar_clave_dueno(c, clave_nueva)


def _no_igual_a_usuarios(c, clave):
    for u in c.execute("SELECT sal, huella FROM usuarios WHERE activo = 1"):
        if _coincide(clave, u["sal"], u["huella"]):
            raise ValueError("Esa contraseña la usa un usuario: elige otra "
                             "distinta para el dueño.")


# -------------------------------------------------------------- recuperación
def _comprobar_recuperacion(c, clave_recuperacion, ahora):
    _revisar_bloqueo(ahora)
    sal, huella = _leer(c, "rec_sal"), _leer(c, "rec_huella")
    if huella is None or not _coincide(_limpiar_recuperacion(clave_recuperacion),
                                       sal, huella):
        _fallo(ahora)
        raise ValueError("La clave de recuperación no es correcta.")
    _acierto()


def restablecer_clave_usuario(nombre, clave_recuperacion, clave_nueva,
                              ahora=None, con=None):
    """Pone una contraseña nueva a un usuario usando la clave de recuperación.

    Devuelve una clave de recuperación NUEVA (la anterior deja de servir).
    """
    _validar_clave(clave_nueva, "La contraseña nueva")
    with _usar(con) as c:
        _preparar(c)
        _comprobar_recuperacion(c, clave_recuperacion, _ahora(ahora))
        u = _buscar_usuario(c, nombre)
        if u is None:
            raise ValueError("Ese usuario no existe.")
        sal, huella = _nueva_huella(clave_nueva)
        c.execute("UPDATE usuarios SET sal = ?, huella = ? WHERE id = ?",
                  (sal, huella, u["id"]))
        return _nueva_recuperacion(c)


def restablecer_clave_dueno(clave_recuperacion, clave_nueva, ahora=None, con=None):
    """Pone una contraseña de dueño nueva usando la clave de recuperación.

    Devuelve una clave de recuperación NUEVA (la anterior deja de servir).
    """
    _validar_clave(clave_nueva, "La contraseña del dueño")
    with _usar(con) as c:
        _preparar(c)
        _comprobar_recuperacion(c, clave_recuperacion, _ahora(ahora))
        _no_igual_a_usuarios(c, clave_nueva)
        _guardar_clave_dueno(c, clave_nueva)
        return _nueva_recuperacion(c)