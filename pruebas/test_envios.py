"""Pruebas de envíos (base de datos temporal)."""
import tempfile
import unittest
from pathlib import Path

from app import config
from app.base_datos.esquema import crear_tablas
from app.servicios import clientes, envios, inventario, ventas


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._original = (config.DATOS_DIR, config.DB_PATH)
        config.DATOS_DIR = Path(self.tmp.name)
        config.DB_PATH = config.DATOS_DIR / "prueba.db"
        crear_tablas()

    def tearDown(self):
        config.DATOS_DIR, config.DB_PATH = self._original
        self.tmp.cleanup()

    def datos(self, **extra):
        d = {"nombre": "Ana Pérez", "servicio": "Olva",
             "destino": "Huancayo - agencia Olva Real"}
        d.update(extra)
        return d


class PruebasEnvios(BaseTest):
    def test_crea_un_envio(self):
        id_ = envios.crear(self.datos(telefono="999 111 222", dni="12345678",
                                      guia="OL-123", nota="frágil"))
        e = envios.obtener(id_)
        self.assertEqual((e["telefono"], e["dni"], e["guia"]),
                         ("999111222", "12345678", "OL-123"))
        self.assertEqual(envios.contar(), 1)

    def test_validaciones(self):
        for malo in ({"nombre": " "}, {"servicio": "Cruz del Sur"},
                     {"destino": ""}, {"telefono": "abc"}, {"dni": "123"},
                     {"venta": "V-000999"}, {"venta": "xx"}):
            with self.assertRaises(ValueError, msg=str(malo)):
                envios.crear(self.datos(**malo))
        self.assertEqual(envios.listar(), [])            # nada se guardó

    def test_domicilio_y_shalom_son_validos(self):
        envios.crear(self.datos(servicio="Domicilio", destino="Av. Real 123"))
        envios.crear(self.datos(servicio="Shalom"))
        self.assertEqual(len(envios.listar()), 2)

    def test_listado_mas_nuevo_primero_y_busqueda(self):
        a = envios.crear(self.datos(nombre="Ana"))
        b = envios.crear(self.datos(nombre="Beto", servicio="Shalom"))
        self.assertEqual([e["nombre"] for e in envios.listar()], ["Beto", "Ana"])
        self.assertEqual(envios.listar(texto="shalom")[0]["id"], b)
        self.assertEqual(envios.listar(texto="ana huancayo")[0]["id"], a)
        self.assertEqual(envios.listar(texto="nadie"), [])
        self.assertEqual(envios.contar(), 2)

    def test_validar_no_guarda_nada(self):
        envios.validar(self.datos())
        with self.assertRaises(ValueError):
            envios.validar(self.datos(destino=""))
        self.assertEqual(envios.contar(), 0)

    def test_actualizar_y_quitar(self):
        id_ = envios.crear(self.datos())
        envios.actualizar(id_, self.datos(guia="NUEVA-9", destino="Lima"))
        e = envios.obtener(id_)
        self.assertEqual((e["guia"], e["destino"]), ("NUEVA-9", "Lima"))
        with self.assertRaises(ValueError):
            envios.actualizar(id_, self.datos(nombre=""))
        envios.quitar(id_)
        self.assertIsNone(envios.obtener(id_))
        with self.assertRaises(ValueError):
            envios.quitar(id_)

    def test_ligado_a_una_venta_y_a_un_cliente(self):
        p = inventario.crear_producto("Polo", "Camisas", costo=10,
                                      precio_unidad=20, precio_mayor=15, stock=10)
        v = ventas.registrar_venta(
            [{"producto_id": p.id, "cantidad": 1, "tipo": "unidad",
              "precio": 20}], [{"forma_pago": "Efectivo", "monto": 20}])
        c = clientes.crear_cliente("Ana Pérez", "999111222", direccion="Jr. Lima 5")
        id_ = envios.crear(self.datos(venta=v["numero"], cliente_id=c.id))
        e = envios.obtener(id_)
        self.assertEqual((e["venta"], e["cliente_id"]), (v["numero"], c.id))
        self.assertEqual(envios.listar(texto=v["numero"])[0]["id"], id_)


if __name__ == "__main__":
    unittest.main()