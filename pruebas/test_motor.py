# -*- coding: utf-8 -*-
"""Verificación independiente del motor.

Cada métrica se recalcula aquí con pandas, leyendo los CSV crudos directamente. No se usa
DuckDB, ni las vistas SQL, ni el diccionario. Si el motor y este cálculo coinciden mes a mes,
la definición está implementada dos veces de forma distinta y da lo mismo.

Uso: .venv/Scripts/python.exe -m pytest pruebas/test_motor.py -q
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import sys

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from capa.motor import ErrorDeMetrica, Motor, huella_capa  # noqa: E402

CRUDOS = RAIZ / "datos" / "crudos"
MESES = [str(p) for p in pd.period_range("2017-01", "2018-08", freq="M")]
MESES_MOV = MESES[1:]                      # los movimientos necesitan un mes anterior completo
TOL = 0.011                                # el motor redondea a 2 decimales


def _csv(nombre: str) -> pd.DataFrame:
    (ruta,) = list(CRUDOS.rglob(nombre))
    return pd.read_csv(ruta)


@pytest.fixture(scope="module")
def motor():
    return Motor()


@pytest.fixture(scope="module")
def crudo():
    """Cálculo independiente en pandas sobre los CSV."""
    orders = _csv("olist_orders_dataset.csv")
    for c in ["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        orders[c] = pd.to_datetime(orders[c])
    validos = orders[~orders["order_status"].isin(["canceled", "unavailable"])].copy()
    validos["mes"] = validos["order_purchase_timestamp"].dt.to_period("M").astype(str)

    items = _csv("olist_order_items_dataset.csv").merge(
        validos[["order_id", "mes", "order_purchase_timestamp"]], on="order_id", how="inner")

    # Vendedor x mes, con todos los meses del calendario hasta 2018-08 (incluye meses sin ventas).
    calendario = [str(p) for p in pd.period_range(items["mes"].min(), "2018-08", freq="M")]
    tabla = (items[items["mes"].isin(calendario)]
             .pivot_table(index="seller_id", columns="mes", values="price", aggfunc="sum", fill_value=0.0)
             .reindex(columns=calendario, fill_value=0.0))
    previo = tabla.shift(1, axis=1).fillna(0.0)
    historico = tabla.cumsum(axis=1).shift(1, axis=1).fillna(0.0)

    reviews = _csv("olist_order_reviews_dataset.csv").groupby("order_id")["review_score"].mean()
    validos = validos.merge(reviews.rename("nota"), left_on="order_id", right_index=True, how="left")

    leads = _csv("olist_marketing_qualified_leads_dataset.csv")
    leads["first_contact_date"] = pd.to_datetime(leads["first_contact_date"])
    deals = _csv("olist_closed_deals_dataset.csv")
    deals["won_date"] = pd.to_datetime(deals["won_date"])
    deals = deals.merge(leads, on="mql_id", how="inner")
    deals["mes"] = deals["won_date"].dt.to_period("M").astype(str)
    leads["mes"] = leads["first_contact_date"].dt.to_period("M").astype(str)
    leads["cerrado"] = leads["mql_id"].isin(deals["mql_id"])

    ventas = items[["seller_id", "order_purchase_timestamp", "price"]]
    v = deals[["seller_id", "won_date"]].merge(ventas, on="seller_id", how="inner")
    en90 = v[v["order_purchase_timestamp"] < v["won_date"] + pd.Timedelta(days=90)]
    deals["gmv_90d"] = deals["seller_id"].map(en90.groupby("seller_id")["price"].sum()).fillna(0.0)
    deals["activado_90d"] = deals["seller_id"].isin(en90["seller_id"])
    deals["primera"] = deals["seller_id"].map(v.groupby("seller_id")["order_purchase_timestamp"].min())
    deals["observable"] = deals["won_date"] + pd.Timedelta(days=90) <= pd.Timestamp("2018-09-01")
    deals["dias_cierre"] = (deals["won_date"].dt.normalize() - deals["first_contact_date"]).dt.days
    deals["dias_primera"] = (deals["primera"].dt.normalize() - deals["won_date"].dt.normalize()).dt.days

    return dict(validos=validos, items=items, tabla=tabla, previo=previo, historico=historico,
                leads=leads, deals=deals, orders=orders)


def _motor_mes(motor, metrica, mes, **kw):
    return motor.valor(metrica, mes, **kw)["valor"]


def _igual(a, b):
    if b is None or (isinstance(b, float) and np.isnan(b)):
        return a is None
    return a is not None and abs(float(a) - float(b)) <= TOL


# ------------------------------------------------------------------------- ingresos
@pytest.mark.parametrize("mes", MESES)
def test_ingresos(motor, crudo, mes):
    it = crudo["items"][crudo["items"]["mes"] == mes]
    gmv, pedidos, vend = it["price"].sum(), it["order_id"].nunique(), it["seller_id"].nunique()
    assert _igual(_motor_mes(motor, "gmv", mes), gmv)
    assert _igual(_motor_mes(motor, "pedidos", mes), pedidos)
    assert _igual(_motor_mes(motor, "vendedores_activos", mes), vend)
    assert _igual(_motor_mes(motor, "ticket_promedio", mes), gmv / pedidos)
    assert _igual(_motor_mes(motor, "gmv_por_vendedor", mes), gmv / vend)


# ------------------------------------------------------ movimientos y retención
@pytest.mark.parametrize("mes", MESES_MOV)
def test_movimientos_y_retencion(motor, crudo, mes):
    g, p, h = crudo["tabla"][mes], crudo["previo"][mes], crudo["historico"][mes]
    d = g - p
    esperado = {
        "gmv_nuevo": d[(p == 0) & (h == 0) & (g > 0)].sum(),
        "gmv_reactivacion": d[(p == 0) & (h > 0) & (g > 0)].sum(),
        "gmv_expansion": d[(p > 0) & (g > p)].sum(),
        "gmv_contraccion": d[(p > 0) & (g < p) & (g > 0)].sum(),
        "gmv_baja": d[(p > 0) & (g == 0)].sum(),
    }
    for nombre, valor in esperado.items():
        assert _igual(_motor_mes(motor, nombre, mes) or 0, valor), nombre
    activos_previos = p > 0
    assert _igual(_motor_mes(motor, "churn_vendedores", mes),
                  100.0 * ((p > 0) & (g == 0)).sum() / activos_previos.sum())
    assert _igual(_motor_mes(motor, "retencion_neta", mes),
                  100.0 * g[activos_previos].sum() / p[activos_previos].sum())
    assert _igual(_motor_mes(motor, "retencion_bruta", mes),
                  100.0 * np.minimum(g, p)[activos_previos].sum() / p[activos_previos].sum())


@pytest.mark.parametrize("mes", MESES_MOV)
def test_conciliacion(motor, mes):
    """GMV del mes = GMV anterior + nuevo + reactivación + expansión + contracción + bajas.

    Usa solo salidas del motor: comprueba que las cinco métricas de movimiento, definidas por
    separado en el diccionario, no dejan ningún real sin clasificar.
    """
    anterior = str(pd.Period(mes, freq="M") - 1)
    movimientos = sum(_motor_mes(motor, n, mes) or 0 for n in
                      ["gmv_nuevo", "gmv_reactivacion", "gmv_expansion", "gmv_contraccion", "gmv_baja"])
    cambio = _motor_mes(motor, "gmv", mes) - _motor_mes(motor, "gmv", anterior)
    assert abs(movimientos - cambio) <= 0.05, (mes, movimientos, cambio)


@pytest.mark.parametrize("cohorte,k", [("2017-03", 1), ("2017-10", 3), ("2017-10", 6), ("2018-02", 6), ("2018-05", 2)])
def test_retencion_cohorte(motor, crudo, cohorte, k):
    t = crudo["tabla"]
    primera = (t > 0).idxmax(axis=1)                     # primer mes con venta de cada vendedor
    miembros = primera[primera == cohorte].index
    mes_k = str(pd.Period(cohorte, freq="M") + k)
    esperado = 100.0 * (t.loc[miembros, mes_k] > 0).sum() / len(miembros)
    r = motor.consultar("retencion_cohorte", cohorte, cohorte, ["meses_desde_primera_venta"], por_mes=False)
    fila = next(f for f in r["filas"] if f["meses_desde_primera_venta"] == k)
    assert _igual(fila["valor"], esperado)
    assert fila["muestra"] == len(miembros)


# --------------------------------------------------------------------------- embudo
@pytest.mark.parametrize("mes", ["2018-01", "2018-02", "2018-03", "2018-04", "2018-05"])
def test_embudo(motor, crudo, mes):
    le = crudo["leads"][crudo["leads"]["mes"] == mes]
    de = crudo["deals"][crudo["deals"]["mes"] == mes]
    assert _igual(_motor_mes(motor, "leads", mes), len(le))
    assert _igual(_motor_mes(motor, "tasa_cierre", mes), 100.0 * le["cerrado"].sum() / len(le))
    assert _igual(_motor_mes(motor, "cierres", mes), len(de))
    assert _igual(_motor_mes(motor, "dias_a_cierre", mes), de["dias_cierre"].median())
    obs = de[de["observable"]]
    assert _igual(_motor_mes(motor, "tasa_activacion_90d", mes), 100.0 * obs["activado_90d"].sum() / len(obs))
    assert _igual(_motor_mes(motor, "gmv_por_cierre_90d", mes), obs["gmv_90d"].sum() / len(obs))
    act = obs[obs["activado_90d"]]
    assert _igual(_motor_mes(motor, "dias_a_primera_venta", mes), act["dias_primera"].median())


@pytest.mark.parametrize("dimension", ["tipo_lead", "tipo_negocio", "origen"])
def test_activacion_por_segmento(motor, crudo, dimension):
    columna = {"tipo_lead": "lead_type", "tipo_negocio": "business_type", "origen": "origin"}[dimension]
    obs = crudo["deals"][crudo["deals"]["observable"]].copy()
    obs[columna] = obs[columna].fillna("sin_dato")
    r = motor.consultar("tasa_activacion_90d", "2017-12", "2018-11", [dimension], por_mes=False)
    assert len(r["filas"]) == obs[columna].nunique()
    for f in r["filas"]:
        grupo = obs[obs[columna] == f[dimension]]
        assert f["muestra"] == len(grupo)
        assert _igual(f["valor"], 100.0 * grupo["activado_90d"].sum() / len(grupo))


# -------------------------------------------------------------------------- calidad
@pytest.mark.parametrize("mes", MESES)
def test_calidad(motor, crudo, mes):
    v = crudo["validos"][crudo["validos"]["mes"] == mes]
    entregados = v[v["order_delivered_customer_date"].notna()]
    tarde = entregados["order_delivered_customer_date"] > entregados["order_estimated_delivery_date"]
    assert _igual(_motor_mes(motor, "entregas_tardias", mes), 100.0 * tarde.sum() / len(entregados))
    assert _igual(_motor_mes(motor, "nota_resenas", mes), v["nota"].mean())


# ------------------------------------------------------------- trampas documentadas
def test_trampa_union_con_pagos_infla_el_gmv(crudo):
    """El diccionario dice que unir ítems con pagos infla el GMV 4,5 %. Se comprueba el número."""
    items = _csv("olist_order_items_dataset.csv")
    pagos = _csv("olist_order_payments_dataset.csv")
    bien = items["price"].sum()
    mal = items.merge(pagos, on="order_id")["price"].sum()
    assert round(100.0 * (mal / bien - 1), 1) == 4.5


def test_trampa_pedidos_excluidos(crudo):
    o = crudo["orders"]
    assert o["order_status"].isin(["canceled", "unavailable"]).sum() == 1234
    assert len(o) == 99441


def test_trampa_censura_de_activacion(motor, crudo):
    """Sin ventana, la activación 'cae' de 56 % a 6 % entre enero y agosto de 2018.
    Con ventana de 90 días se mantiene entre 38 % y 51 %. La caída es un artefacto."""
    d = crudo["deals"]
    ingenua = d.groupby("mes")["primera"].apply(lambda s: 100.0 * s.notna().mean())
    assert ingenua["2018-01"] > 55 and ingenua["2018-08"] < 7
    r = motor.consultar("tasa_activacion_90d", "2018-01", "2018-05")
    valores = [f["valor"] for f in r["filas"]]
    assert all(f["fiable"] for f in r["filas"])
    assert 38 <= min(valores) and max(valores) <= 51


def test_ventana_de_tasa_de_cierre(motor):
    r = motor.consultar("tasa_cierre", "2017-10", "2018-02")
    assert r["advertencias"]
    fuera = [f for f in r["filas"] if f["mes"] < "2018-01"]
    assert fuera and all(not f["fiable"] and f.get("fuera_de_ventana") for f in fuera)


# --------------------------------------------------------------- reglas del motor
def test_rechaza_lo_que_el_diccionario_no_permite(motor):
    with pytest.raises(ErrorDeMetrica):
        motor.consultar("mrr")                                   # no existe: estos datos no tienen MRR
    with pytest.raises(ErrorDeMetrica):
        motor.consultar("gmv", dimensiones=["sdr_id"])           # dimensión no permitida para gmv
    with pytest.raises(ErrorDeMetrica):
        motor.consultar("gmv", desde="marzo")
    with pytest.raises(ErrorDeMetrica):
        motor.consultar("gmv", filtros={"categoria; drop table orders": "x"})


def test_filtro_viaja_como_parametro(motor):
    r = motor.consultar("gmv", "2018-03", "2018-03", filtros={"categoria": "x' OR '1'='1"}, por_mes=False)
    assert r["filas"][0]["valor"] is None                        # no devuelve todo el GMV


@pytest.mark.parametrize("sql", [
    "drop table orders", "select 1; select 2", "select * from read_csv('x.csv')",
    "insert into orders select * from orders", "attach 'otra.duckdb'", "copy orders to 'x.csv'",
])
def test_sql_libre_solo_lectura(motor, sql):
    with pytest.raises(ErrorDeMetrica):
        motor.sql_libre(sql)


def test_poca_muestra_no_es_fiable(motor):
    r = motor.consultar("tasa_activacion_90d", "2017-12", "2018-11", ["origen"], por_mes=False)
    por = {f["origen"]: f for f in r["filas"]}
    assert por["paid_search"]["fiable"] is True
    assert por["display"]["fiable"] is False                     # 6 cierres


def test_cada_respuesta_dice_la_version_del_diccionario(motor):
    sello = motor.sello
    assert sello["version"] == motor.general["version"]
    assert len(sello["huella"]) == 12
    respuestas = [
        motor.listar(), motor.definir("gmv"),
        motor.consultar("gmv", "2018-03", "2018-03", por_mes=False),
        motor.descomponer("gmv", "2018-02", "2018-03", "estado_vendedor"),
        motor.anomalias("2018-03"),
    ]
    for r in respuestas:
        assert r["diccionario"] == sello


def test_la_huella_cambia_si_cambia_la_capa(tmp_path):
    """Cambiar una definición o una vista cambia la huella, aunque nadie suba la versión."""
    modelos = tmp_path / "modelos"
    modelos.mkdir()
    for sql in (RAIZ / "capa" / "modelos").glob("*.sql"):
        (modelos / sql.name).write_bytes(sql.read_bytes())
    dic = tmp_path / "metricas.yml"
    dic.write_bytes((RAIZ / "capa" / "metricas.yml").read_bytes())
    original = huella_capa(RAIZ / "capa" / "metricas.yml", RAIZ / "capa" / "modelos")
    assert huella_capa(dic, modelos) == original                  # copia idéntica, misma huella

    dic.write_text(dic.read_text(encoding="utf-8").replace("muestra_minima: 30", "muestra_minima: 31", 1),
                   encoding="utf-8")
    assert huella_capa(dic, modelos) != original                  # cambió una definición

    dic.write_bytes((RAIZ / "capa" / "metricas.yml").read_bytes())
    vista = modelos / "01_pedidos.sql"
    vista.write_text(vista.read_text(encoding="utf-8").replace("'unavailable'", "'x'"), encoding="utf-8")
    assert huella_capa(dic, modelos) != original                  # cambió una vista


def test_descomposicion_aditiva_suma_el_cambio(motor):
    d = motor.descomponer("gmv", "2017-10", "2017-11", "estado_vendedor")
    assert d["segmentos_omitidos"] == 0
    assert abs(sum(s["cambio"] for s in d["segmentos"]) - d["cambio_total"]) <= 0.05
    assert abs(sum(s["aporte_al_cambio_pct"] for s in d["segmentos"]) - 100.0) <= 0.5
