# -*- coding: utf-8 -*-
"""Prueba de humo: cada métrica del diccionario responde, y las herramientas principales corren.

Uso: .venv/Scripts/python.exe pruebas/humo.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from capa.motor import Motor  # noqa: E402

t0 = time.time()
m = Motor()
print(f"motor listo en {time.time() - t0:.1f} s, {len(m.metricas)} métricas\n")

print(f"{'métrica':<24}{'2018-03':>14}{'muestra':>10}  fiable   seg")
for nombre in m.metricas:
    t = time.time()
    if nombre == "retencion_cohorte":
        r = m.consultar(nombre, "2017-10", "2017-10", ["meses_desde_primera_venta"], por_mes=False)
        f = next(x for x in r["filas"] if x["meses_desde_primera_venta"] == 3)
    else:
        f = m.valor(nombre, "2018-03")
    print(f"{nombre:<24}{str(f['valor']):>14}{str(f['muestra']):>10}  {str(f['fiable']):<7}{time.time() - t:5.2f}")

print("\n-- descomponer gmv 2017-10 -> 2017-11 por categoria (top 5)")
d = m.descomponer("gmv", "2017-10", "2017-11", "categoria")
print("total", d["total_base"], "->", d["total_comparado"], "cambio", d["cambio_total"])
for s in d["segmentos"][:5]:
    print("  ", s)

print("\n-- anomalias 2018-03")
a = m.anomalias("2018-03")
for x in a["alertas"]:
    print("  ALERTA", x)
print("  sin alerta:", [x["metrica"] for x in a["sin_alerta"]])
print("  no evaluadas:", a["no_evaluadas"])

print("\n-- sql libre")
print(m.sql_libre("select order_status, count(*) n from orders group by 1 order by 2 desc", 3))
for malo in ["drop table orders", "select 1; select 2", "select * from read_csv('x.csv')"]:
    try:
        m.sql_libre(malo)
        print("  NO BLOQUEADO:", malo)
    except Exception as e:  # noqa: BLE001
        print("  bloqueado:", malo, "->", type(e).__name__)
