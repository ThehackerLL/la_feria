"""Pruebas de anular ventas y su efecto en stock y caja (base temporal)."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app import config
from app.base_datos.conexion import transaccion
from app.base_datos.esquema import crear_tablas
from app.servicios import anulaciones, caja, clientes, inventario, ventas

EF, YAPE = "Efectivo", "Yape/Plin"


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._original = (config.DATOS_DIR, config.DB_PATH)
        config.DATOS_DIR = Path(self.tmp.name)
        config.DB_PATH = config.DATOS_DIR / "prueba.db"
        crear_tablas()
        self.producto = inventario.crear_producto(
            "Polo", "Camisas", costo=10, precio_unidad=20, precio_mayor=15,
            stock=50)
        self.hoy = datetime.now().strftime("%Y-%m-%d")
        caja.abrir_dia(100)

    def tearDown(self):
        config.DATOS_DIR, config.DB_PATH = self._original
        self.tmp.cleanup()

    def vender(self, cantidad, pagos, **extra):
        return ventas.registrar_venta(
            [{"producto_id": self.producto.id, "cantidad": cantidad,
              "tipo": "unidad", "precio": 20}], pagos, **extra)

    def stock(self):
        return inventario.obtener_producto(self.producto.id).stock

    def mover_a_dia_pasado(self, venta_id, fecha="2020-01-01 10:00:00"):
        with transaccion() as con:
            con.execute("UPDATE ventas SET fecha = ? WHERE id = ?",
                        (fecha, venta_id))
            con.execute("UPDATE venta_pagos SET fecha = ? WHERE venta_id = ?",
                        (fecha, venta_id))


class PruebasAnular(BaseTest):
    def test_devuelve_stock_y_marca_anulada(self):
        v = self.vender(5, [{"forma_pago": EF, "monto": 100}])
        self.assertEqual(self.stock(), 45)
        r = anulaciones.anular_venta(v["venta_id"], "Error al cobrar")
        self.assertEqual(self.stock(), 50)
        self.assertEqual(r["total_devuelto"], 100)
        d = anulaciones.detalle_venta(v["venta_id"])
        self.assertEqual(d["estado"], "anulada")
        self.assertEqual(d["anulacion"]["motivo"], "Error al cobrar")
        self.assertEqual(len(d["lineas"]), 1)          # no se borra nada

    def test_danada_no_vuelve_al_stock_pero_si_se_devuelve_el_dinero(self):
        v = self.vender(5, [{"forma_pago": EF, "monto": 100}])
        r = anulaciones.anular_venta(v["venta_id"], "Llegó rota",
                                     volver_al_stock=False)
        self.assertFalse(r["volvio_al_stock"])
        self.assertEqual(self.stock(), 45)
        self.assertEqual(r["total_devuelto"], 100)
        d = anulaciones.detalle_venta(v["venta_id"])
        self.assertEqual(d["anulacion"]["al_stock"], 0)

    def test_no_se_anula_dos_veces_ni_sin_motivo(self):
        v = self.vender(1, [{"forma_pago": EF, "monto": 20}])
        with self.assertRaises(ValueError):
            anulaciones.anular_venta(v["venta_id"], "  ")
        self.assertEqual(self.stock(), 49)             # nada cambió
        anulaciones.anular_venta(v["venta_id"], "Cliente se arrepintió")
        with self.assertRaises(ValueError):
            anulaciones.anular_venta(v["venta_id"], "Otra vez")
        self.assertEqual(self.stock(), 50)
        with self.assertRaises(ValueError):
            anulaciones.anular_venta(9999, "No existe")

    def test_devuelve_por_cada_forma_de_pago(self):
        v = self.vender(5, [{"forma_pago": EF, "monto": 60},
                            {"forma_pago": YAPE, "monto": 40}])
        r = anulaciones.anular_venta(v["venta_id"], "Prueba")
        self.assertEqual({d["forma_pago"]: d["monto"] for d in r["devuelto"]},
                         {EF: 60, YAPE: 40})

    def test_venta_a_credito_cancela_la_deuda(self):
        cliente = clientes.crear_cliente("Ana", "999111222")
        v = self.vender(10, [{"forma_pago": EF, "monto": 50}],
                        cliente_id=cliente.id,
                        credito={"cuotas": 2, "dias": 15})
        self.assertEqual(caja.resumen_dia()["a_credito"], 150)
        r = anulaciones.anular_venta(v["venta_id"], "Cliente no pagó")
        self.assertEqual(r["total_devuelto"], 50)
        self.assertEqual(self.stock(), 50)
        self.assertEqual(caja.resumen_dia()["a_credito"], 0)
        fila = anulaciones.listar_ventas()[0]
        self.assertEqual((fila["estado"], fila["debe"]), ("anulada", 0))


class PruebasCajaConAnulaciones(BaseTest):
    def test_anular_el_mismo_dia_deja_la_caja_como_al_inicio(self):
        v = self.vender(5, [{"forma_pago": EF, "monto": 60},
                            {"forma_pago": YAPE, "monto": 40}])
        self.assertEqual(caja.resumen_dia()["efectivo_esperado"], 160)
        anulaciones.anular_venta(v["venta_id"], "Prueba")
        r = caja.resumen_dia()
        self.assertEqual(r["efectivo_esperado"], 100)
        self.assertEqual(r["vendido"], 0)
        self.assertEqual(r["ventas"], 0)
        self.assertEqual(r["devuelto_total"], 100)
        self.assertEqual(r["digital_cobrado"] - r["digital_pagado"], 0)

    def test_anular_venta_de_otro_dia_no_cambia_ese_dia(self):
        v = self.vender(5, [{"forma_pago": EF, "monto": 100}])
        self.mover_a_dia_pasado(v["venta_id"])
        antes = caja.resumen_dia("2020-01-01")
        anulaciones.anular_venta(v["venta_id"], "Devolvió todo")
        despues = caja.resumen_dia("2020-01-01")
        # el dinero que entró ese día sigue ahí; lo devuelto sale hoy
        self.assertEqual(despues["efectivo_cobrado"], antes["efectivo_cobrado"])
        self.assertEqual(despues["devuelto_total"], 0)
        hoy = caja.resumen_dia()
        self.assertEqual(hoy["devuelto_total"], 100)
        self.assertEqual(hoy["efectivo_esperado"], 0)       # 100 - 100

    def test_ventas_vigentes_no_se_afectan(self):
        a = self.vender(2, [{"forma_pago": EF, "monto": 40}])
        self.vender(3, [{"forma_pago": EF, "monto": 60}])
        anulaciones.anular_venta(a["venta_id"], "Error")
        r = caja.resumen_dia()
        self.assertEqual((r["ventas"], r["vendido"]), (1, 60))
        self.assertEqual(r["efectivo_esperado"], 160)       # 100 + 60


class PruebasListado(BaseTest):
    def test_lista_filtra_y_busca(self):
        cliente = clientes.crear_cliente("Ana Pérez", "999111222")
        self.vender(1, [{"forma_pago": EF, "monto": 20}])
        v2 = self.vender(2, [{"forma_pago": EF, "monto": 40}],
                         cliente_id=cliente.id)
        self.assertEqual(len(anulaciones.listar_ventas()), 2)
        self.assertEqual(len(anulaciones.listar_ventas(texto="ana")), 1)
        self.assertEqual(len(anulaciones.listar_ventas(texto="V-000001")), 1)
        self.assertEqual(len(anulaciones.listar_ventas(desde="2020-01-01",
                                                       hasta="2020-01-31")), 0)
        anulaciones.anular_venta(v2["venta_id"], "Prueba")
        estados = {f["numero"]: f["estado"] for f in anulaciones.listar_ventas()}
        self.assertEqual(estados, {"V-000001": "activa", "V-000002": "anulada"})


class PruebasDevolucionParcial(BaseTest):
    def setUp(self):
        super().setUp()
        self.otro = inventario.crear_producto(
            "Short", "Pantalón", costo=15, precio_unidad=25, precio_mayor=22,
            stock=40)

    def venta_de_dos(self, pagos, **extra):
        """10 polos a 20 (=200) + 4 shorts a 25 (=100): total 300."""
        return ventas.registrar_venta(
            [{"producto_id": self.producto.id, "cantidad": 10,
              "tipo": "unidad", "precio": 20},
             {"producto_id": self.otro.id, "cantidad": 4,
              "tipo": "unidad", "precio": 25}], pagos, **extra)

    def linea(self, venta_id, producto):
        d = anulaciones.detalle_venta(venta_id)
        return next(l for l in d["lineas"] if l["producto_id"] == producto.id)

    def stock_otro(self):
        return inventario.obtener_producto(self.otro.id).stock

    def test_devuelve_un_producto_completo(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 300}])
        vid = v["venta_id"]
        r = anulaciones.devolver_producto(
            vid, self.linea(vid, self.producto)["id"], 10)
        self.assertEqual((r["valor"], r["dinero"]), (200, 200))
        d = anulaciones.detalle_venta(vid)
        self.assertEqual(d["estado"], "activa")
        self.assertEqual(d["total"], 100)
        self.assertEqual([l["nombre"] for l in d["lineas"]], ["Short"])
        self.assertEqual(self.stock(), 50)              # volvieron los 10
        self.assertEqual(d["pagado"], 100)
        self.assertEqual(d["debe"], 0)
        self.assertEqual(d["devoluciones"][0]["cantidad"], 10)

    def test_devuelve_solo_parte_de_las_unidades(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 300}])
        vid = v["venta_id"]
        r = anulaciones.devolver_producto(
            vid, self.linea(vid, self.producto)["id"], 4)
        self.assertEqual(r["dinero"], 80)
        self.assertEqual(self.linea(vid, self.producto)["cantidad"], 6)
        self.assertEqual(anulaciones.detalle_venta(vid)["total"], 220)

    def test_danado_no_vuelve_al_stock(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 300}])
        vid = v["venta_id"]
        anulaciones.devolver_producto(
            vid, self.linea(vid, self.otro)["id"], 2, volver_al_stock=False)
        self.assertEqual(self.stock_otro(), 40 - 4)     # no se repone
        d = anulaciones.detalle_venta(vid)
        self.assertEqual(d["devoluciones"][0]["al_stock"], 0)

    def test_descuento_se_reparte_proporcional(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 270}], descuento=30)
        vid = v["venta_id"]
        r = anulaciones.devolver_producto(
            vid, self.linea(vid, self.producto)["id"], 10)
        self.assertEqual(r["valor"], 180)               # 200 - 10 % de descuento
        d = anulaciones.detalle_venta(vid)
        self.assertEqual((d["subtotal"], d["descuento"], d["total"]),
                         (100, 10, 90))

    def test_no_deja_devolver_de_mas_ni_todo(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 300}])
        vid = v["venta_id"]
        polo = self.linea(vid, self.producto)["id"]
        for malo in (0, 11, "x", -1):
            with self.assertRaises(ValueError):
                anulaciones.devolver_producto(vid, polo, malo)
        anulaciones.devolver_producto(vid, polo, 10)
        short = self.linea(vid, self.otro)["id"]
        with self.assertRaises(ValueError):             # ya sería todo
            anulaciones.devolver_producto(vid, short, 4)
        self.assertEqual(anulaciones.detalle_venta(vid)["total"], 100)

    def test_caja_del_dia(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 300}])
        vid = v["venta_id"]
        anulaciones.devolver_producto(
            vid, self.linea(vid, self.producto)["id"], 10)
        r = caja.resumen_dia()
        self.assertEqual(r["vendido"], 100)
        self.assertEqual(r["efectivo_esperado"], 200)   # 100 + 300 - 200
        self.assertEqual(r["ganancia"], 100 - 4 * 15)

    def test_credito_primero_baja_la_deuda(self):
        cliente = clientes.crear_cliente("Ana", "999111222")
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 100}],
                              cliente_id=cliente.id,
                              credito={"cuotas": 2, "dias": 15})
        vid = v["venta_id"]                              # debe 200
        r = anulaciones.devolver_producto(
            vid, self.linea(vid, self.otro)["id"], 2)    # vale 50
        self.assertEqual((r["baja_deuda"], r["dinero"]), (50, 0))
        d = anulaciones.detalle_venta(vid)
        self.assertEqual((d["total"], d["debe"]), (250, 150))
        with transaccion() as con:
            cuotas = con.execute("SELECT SUM(monto - pagado) FROM credito_cuotas "
                                 "WHERE venta_id = ?", (vid,)).fetchone()[0]
        self.assertEqual(cuotas, 150)
        self.assertEqual(caja.resumen_dia()["efectivo_esperado"], 200)

    def test_credito_el_sobrante_se_devuelve_en_dinero(self):
        cliente = clientes.crear_cliente("Ana", "999111222")
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 250}],
                              cliente_id=cliente.id,
                              credito={"cuotas": 1, "dias": 15})
        vid = v["venta_id"]                              # debe 50
        r = anulaciones.devolver_producto(
            vid, self.linea(vid, self.producto)["id"], 10)   # vale 200
        self.assertEqual((r["baja_deuda"], r["dinero"]), (50, 150))
        d = anulaciones.detalle_venta(vid)
        self.assertEqual((d["total"], d["debe"], d["pagado"]), (100, 0, 100))
        with transaccion() as con:
            n = con.execute("SELECT COUNT(*) FROM credito_cuotas WHERE venta_id = ?",
                            (vid,)).fetchone()[0]
        self.assertEqual(n, 0)                           # la deuda desapareció

    def test_anular_despues_de_devolver_solo_devuelve_lo_que_queda(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 300}])
        vid = v["venta_id"]
        anulaciones.devolver_producto(
            vid, self.linea(vid, self.producto)["id"], 10, forma_pago=EF)
        r = anulaciones.anular_venta(vid, "Devolvió el resto")
        self.assertEqual(r["total_devuelto"], 100)
        self.assertEqual(self.stock(), 50)
        self.assertEqual(self.stock_otro(), 40)
        self.assertEqual(caja.resumen_dia()["efectivo_esperado"], 100)

    def test_devolver_en_otra_forma_de_pago(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 300}])
        vid = v["venta_id"]
        anulaciones.devolver_producto(
            vid, self.linea(vid, self.producto)["id"], 10, forma_pago=YAPE)
        r = caja.resumen_dia()
        self.assertEqual(r["digital_pagado"], 200)
        r2 = anulaciones.anular_venta(vid, "Resto")
        self.assertEqual(r2["total_devuelto"], 100)      # no devuelve de más

    def test_vista_previa_no_guarda_nada(self):
        v = self.venta_de_dos([{"forma_pago": EF, "monto": 300}])
        vid = v["venta_id"]
        p = anulaciones.vista_previa_devolucion(
            vid, self.linea(vid, self.producto)["id"], 3)
        self.assertEqual((p["valor"], p["dinero"]), (60, 60))
        self.assertEqual(anulaciones.detalle_venta(vid)["total"], 300)


if __name__ == "__main__":
    unittest.main()