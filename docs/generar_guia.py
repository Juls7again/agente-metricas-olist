# -*- coding: utf-8 -*-
"""Genera docs/guia-datos-y-proyecto.html: la guía de los datos y del proyecto.

Las cifras y los gráficos salen del motor (capa/motor.py) y de consultas a datos/olist.duckdb
hechas aquí mismo. Ningún número del documento se escribe a mano.

Uso: .venv/Scripts/python.exe docs/generar_guia.py
El PDF se exporta después abriendo el HTML en el navegador e imprimiendo en A4.
"""
import html
import sys
from pathlib import Path
from string import Template

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from capa.motor import Motor  # noqa: E402

SALIDA = RAIZ / "docs" / "guia-datos-y-proyecto.html"
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

AZUL = "#2a78d6"
NARANJA = "#eb6834"
GRIS = "#bdbcb6"
TINTA = "#1d1d1b"
TINTA2 = "#52514e"
REJILLA = "#e4e3de"
FONDO = "#ffffff"


def num(x, dec=0):
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def esc(t):
    return html.escape(str(t), quote=True)


def mes_corto(m):
    a, mm = m.split("-")
    return MESES[int(mm) - 1], a


# ----------------------------------------------------------------------------- gráficos SVG
def barras(datos, ticks, fmt_tick, fmt_valor, alto=220, ancho=660, titulo=""):
    """Barras verticales por mes. datos: [{mes, valor, color, etiqueta}]"""
    izq, der, arr, aba = 52, 6, 20, 34
    w, h = ancho - izq - der, alto - arr - aba
    n = len(datos)
    paso = w / n
    bw = paso * 0.66
    vmax = ticks[-1]

    def y(v):
        return arr + h - h * v / vmax

    p = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="{esc(titulo)}">']
    for t in ticks:
        yy = y(t)
        p.append(f'<line x1="{izq}" x2="{ancho - der}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{REJILLA}" stroke-width="1"/>')
        p.append(f'<text x="{izq - 8}" y="{yy + 3.5:.1f}" text-anchor="end" class="eje">{fmt_tick(t)}</text>')
    anio_previo = None
    for i, d in enumerate(datos):
        x = izq + i * paso + (paso - bw) / 2
        cx = x + bw / 2
        if d["valor"] is not None and d["valor"] > 0:
            yt, y0 = y(d["valor"]), y(0)
            r = min(3.0, bw / 2, y0 - yt)
            p.append(
                f'<path d="M{x:.1f},{y0:.1f} L{x:.1f},{yt + r:.1f} Q{x:.1f},{yt:.1f} {x + r:.1f},{yt:.1f} '
                f'L{x + bw - r:.1f},{yt:.1f} Q{x + bw:.1f},{yt:.1f} {x + bw:.1f},{yt + r:.1f} L{x + bw:.1f},{y0:.1f} Z" '
                f'fill="{d["color"]}"><title>{esc(d["mes"])}: {esc(fmt_valor(d["valor"]))}</title></path>')
            if d.get("etiqueta"):
                p.append(f'<text x="{cx:.1f}" y="{yt - 5:.1f}" text-anchor="middle" class="valor">{fmt_valor(d["valor"])}</text>')
        mm, aa = mes_corto(d["mes"])
        p.append(f'<text x="{cx:.1f}" y="{arr + h + 13}" text-anchor="middle" class="eje">{mm}</text>')
        if aa != anio_previo:
            p.append(f'<text x="{cx:.1f}" y="{arr + h + 26}" text-anchor="middle" class="eje anio">{aa}</text>')
            anio_previo = aa
    p.append(f'<line x1="{izq}" x2="{ancho - der}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{TINTA2}" stroke-width="1"/>')
    p.append("</svg>")
    return "\n".join(p)


def barras_h(filas, vmax, fmt_valor, ancho=660, titulo="", izq=150, der=200):
    """Barras horizontales. filas: [{etiqueta, valor, color, derecha}]"""
    alto_fila, arr = 25, 4
    alto = arr + alto_fila * len(filas) + 6
    w = ancho - izq - der
    p = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="{esc(titulo)}">']
    for i, f in enumerate(filas):
        yc = arr + i * alto_fila + alto_fila / 2
        bh = 14
        largo = max(0.0, w * f["valor"] / vmax)
        p.append(f'<text x="{izq - 10}" y="{yc + 4:.1f}" text-anchor="end" class="cat">{esc(f["etiqueta"])}</text>')
        if largo > 0:
            r = min(3.0, bh / 2, largo)
            x0, y0 = izq, yc - bh / 2
            p.append(
                f'<path d="M{x0},{y0:.1f} L{x0 + largo - r:.1f},{y0:.1f} Q{x0 + largo:.1f},{y0:.1f} {x0 + largo:.1f},{y0 + r:.1f} '
                f'L{x0 + largo:.1f},{y0 + bh - r:.1f} Q{x0 + largo:.1f},{y0 + bh:.1f} {x0 + largo - r:.1f},{y0 + bh:.1f} '
                f'L{x0},{y0 + bh:.1f} Z" fill="{f["color"]}"><title>{esc(f["etiqueta"])}: {esc(fmt_valor(f["valor"]))}</title></path>')
        p.append(f'<text x="{izq + largo + 6:.1f}" y="{yc + 4:.1f}" class="valor">{fmt_valor(f["valor"])}</text>')
        p.append(f'<text x="{ancho - 4}" y="{yc + 4:.1f}" text-anchor="end" class="nota">{esc(f["derecha"])}</text>')
    p.append(f'<line x1="{izq}" x2="{izq}" y1="{arr}" y2="{alto - 4}" stroke="{TINTA2}" stroke-width="1"/>')
    p.append("</svg>")
    return "\n".join(p)


def lineas(meses, series, ticks, fmt_tick, alto=230, ancho=660, sombra_desde=None, texto_sombra="", titulo=""):
    """Líneas por mes. series: [{nombre, color, valores: {mes: v}}]"""
    izq, der, arr, aba = 44, 92, 14, 34
    w, h = ancho - izq - der, alto - arr - aba
    n = len(meses)
    paso = w / (n - 1)
    vmin, vmax = ticks[0], ticks[-1]

    def x(i):
        return izq + i * paso

    def y(v):
        return arr + h - h * (v - vmin) / (vmax - vmin)

    p = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="{esc(titulo)}">']
    if sombra_desde in meses:
        i0 = meses.index(sombra_desde)
        xs = x(i0) - paso / 2
        p.append(f'<rect x="{xs:.1f}" y="{arr}" width="{x(n - 1) - xs + 6:.1f}" height="{h}" fill="#f2f1ec"/>')
        p.append(f'<text x="{xs + 8:.1f}" y="{arr + 14}" class="nota">{esc(texto_sombra)}</text>')
    for t in ticks:
        yy = y(t)
        p.append(f'<line x1="{izq}" x2="{x(n - 1)}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{REJILLA}" stroke-width="1"/>')
        p.append(f'<text x="{izq - 8}" y="{yy + 3.5:.1f}" text-anchor="end" class="eje">{fmt_tick(t)}</text>')
    anio_previo = None
    for i, m in enumerate(meses):
        mm, aa = mes_corto(m)
        p.append(f'<text x="{x(i):.1f}" y="{arr + h + 13}" text-anchor="middle" class="eje">{mm}</text>')
        if aa != anio_previo:
            p.append(f'<text x="{x(i):.1f}" y="{arr + h + 26}" text-anchor="middle" class="eje anio">{aa}</text>')
            anio_previo = aa
    for s in series:
        tramos, actual = [], []
        for i, m in enumerate(meses):
            v = s["valores"].get(m)
            if v is None:
                if actual:
                    tramos.append(actual)
                actual = []
            else:
                actual.append((x(i), y(v), m, v))
        if actual:
            tramos.append(actual)
        for tr in tramos:
            pts = " ".join(f"{a:.1f},{b:.1f}" for a, b, _, _ in tr)
            p.append(f'<polyline points="{pts}" fill="none" stroke="{s["color"]}" stroke-width="2" stroke-linejoin="round"/>')
        for tr in tramos:
            for a, b, m, v in tr:
                p.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="4" fill="{s["color"]}" stroke="{FONDO}" stroke-width="2">'
                         f'<title>{esc(s["nombre"])} {esc(m)}: {num(v, 1)}</title></circle>')
        if s.get("etiqueta"):
            mes_e, dx, dy, texto, ancla = s["etiqueta"]
            for tr in tramos:
                for a, b, m, _ in tr:
                    if m == mes_e:
                        p.append(f'<text x="{a + dx:.1f}" y="{b + dy:.1f}" text-anchor="{ancla}" class="valor">{esc(texto)}</text>')
        if tramos and s.get("etiqueta_final"):
            a, b, _, v = tramos[-1][-1]
            p.append(f'<text x="{a + 9:.1f}" y="{b + 4:.1f}" class="valor">{esc(s["etiqueta_final"](v))}</text>')
    p.append(f'<line x1="{izq}" x2="{x(n - 1)}" y1="{y(vmin):.1f}" y2="{y(vmin):.1f}" stroke="{TINTA2}" stroke-width="1"/>')
    p.append("</svg>")
    return "\n".join(p)


def leyenda(items):
    return '<div class="leyenda">' + "".join(
        f'<span><i style="background:{c}"></i>{esc(t)}</span>' for t, c in items) + "</div>"


# ----------------------------------------------------------------------------- datos
def recoger():
    m = Motor()
    q = lambda s: m.con.execute(s).fetchall()  # noqa: E731
    d = {"m": m}

    d["tablas"] = {t: q(f'select count(*) from "{t}"')[0][0] for t in [
        "marketing_qualified_leads", "closed_deals", "sellers", "orders", "order_items", "order_payments",
        "order_reviews", "customers", "products", "product_category_name_translation", "geolocation"]}
    d["estados"] = dict(q("select order_status, count(*) from orders group by 1"))
    d["excluidos"] = d["estados"].get("canceled", 0) + d["estados"].get("unavailable", 0)
    d["sin_items"] = q("select count(*) from orders o where not exists "
                       "(select 1 from order_items i where i.order_id = o.order_id)")[0][0]
    d["clientes_unicos"] = q("select count(distinct customer_unique_id) from customers")[0][0]
    d["sdr"], d["sr"] = q("select count(distinct sdr_id), count(distinct sr_id) from closed_deals")[0]
    d["cierres_con_venta"] = q("select count(*) filter (where gmv_total > 0) from v_cierres")[0][0]
    d["gmv_crudo"] = q("select sum(price) from order_items")[0][0]
    d["gmv_con_pagos"] = q("select sum(i.price) from order_items i join order_payments p using (order_id)")[0][0]
    d["inflado_pct"] = 100 * (d["gmv_con_pagos"] / d["gmv_crudo"] - 1)
    d["declarado_ingreso"] = q("select count(*) filter (where declared_monthly_revenue > 0) from closed_deals")[0][0]
    d["con_empresa"] = q("select count(has_company) from closed_deals")[0][0]
    d["pedidos_mes"] = dict((str(a)[:7], b) for a, b in q(
        "select date_trunc('month', order_purchase_timestamp)::date, count(*) from orders group by 1"))
    incompletos = [v for k, v in d["pedidos_mes"].items() if k < "2017-01" or k > "2018-08"]
    d["incompleto_min"], d["incompleto_max"] = min(incompletos), max(incompletos)

    con = lambda met, **kw: m.consultar(met, **kw)["filas"]  # noqa: E731
    d["gmv_mes"] = con("gmv")
    d["tardias_mes"] = con("entregas_tardias")
    d["nota_mes"] = {f["mes"]: f["valor"] for f in con("nota_resenas")}
    d["nrr"] = {f["mes"]: f for f in con("retencion_neta")}
    d["grr"] = {f["mes"]: f for f in con("retencion_bruta")}
    d["churn"] = {f["mes"]: f for f in con("churn_vendedores")}
    d["act_tot"] = con("tasa_activacion_90d", por_mes=False)[0]
    d["gmv90_tot"] = con("gmv_por_cierre_90d", por_mes=False)[0]
    d["act_tipo"] = con("tasa_activacion_90d", dimensiones=["tipo_lead"], por_mes=False)
    d["gmv90_tipo"] = {f["tipo_lead"]: f for f in con("gmv_por_cierre_90d", dimensiones=["tipo_lead"], por_mes=False)}
    d["act_negocio"] = {f["tipo_negocio"]: f for f in con("tasa_activacion_90d", dimensiones=["tipo_negocio"], por_mes=False)}
    d["gmv90_negocio"] = {f["tipo_negocio"]: f for f in con("gmv_por_cierre_90d", dimensiones=["tipo_negocio"], por_mes=False)}
    d["act_origen"] = {f["origen"]: f for f in con("tasa_activacion_90d", dimensiones=["origen"], por_mes=False)}
    d["cierre_origen"] = con("tasa_cierre", dimensiones=["origen"], por_mes=False)
    d["cierre_tot"] = con("tasa_cierre", por_mes=False)[0]
    d["cierre_mes"] = m.consultar("tasa_cierre", desde="2017-06", hasta="2018-05")["filas"]
    d["leads_mes"] = {f["mes"]: f["valor"] for f in m.consultar("leads", desde="2017-06", hasta="2018-05")["filas"]}
    d["censura"] = q("""
        select strftime(mes, '%Y-%m'), count(*),
               100.0 * count(*) filter (where gmv_total > 0 and primera_venta < timestamp '2018-09-01') / count(*),
               100.0 * count(*) filter (where observable_90d and activado_90d)
                     / nullif(count(*) filter (where observable_90d), 0),
               count(*) filter (where observable_90d)
        from v_cierres group by 1 order by 1""")
    d["dias_cierre"] = con("dias_a_cierre", por_mes=False)[0]
    d["anom"] = {mes: m.anomalias(mes) for mes in ("2017-11", "2018-03", "2018-05")}
    d["dic"] = yaml.safe_load((RAIZ / "capa" / "metricas.yml").read_text(encoding="utf-8"))
    d["control"] = resumen_control(d["dic"])
    return d


def resumen_control(dic):
    """Cuenta las respuestas iguales a la cifra oficial en las preguntas de control."""
    import json
    sys.path.insert(0, str(RAIZ / "pruebas"))
    from evaluar_agente import CONDICIONES, PREGUNTAS, RESULTADOS, clasificar
    preguntas = {q["id"]: q for q in yaml.safe_load(PREGUNTAS.read_text(encoding="utf-8"))["preguntas"]}
    ultimas = {}
    for linea in RESULTADOS.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            f = json.loads(linea)
            ultimas[(f["id"], f["condicion"])] = f
    out = {c: {"igual": 0, "n": 0} for c in CONDICIONES}
    for (qid, c), f in ultimas.items():
        if f["estado"] != "ok" or qid not in preguntas:
            continue
        q = preguntas[qid]
        unidad = dic["metricas"][q["esperado"]["metrica"]]["unidad"] if "metrica" in q["esperado"] else None
        out[c]["n"] += 1
        out[c]["igual"] += clasificar(f.get("valor"), f.get("esperado"), unidad, q.get("tol_abs", 0.0)) == "igual"
    return out


# ----------------------------------------------------------------------------- piezas del documento
def tabla_metricas(dic):
    filas = []
    grupo_previo = None
    for nombre, x in dic["metricas"].items():
        g = x["grupo"]
        celda_g = f'<td class="grupo">{esc(g)}</td>' if g != grupo_previo else '<td class="grupo"></td>'
        grupo_previo = g
        filas.append(
            f"<tr>{celda_g}<td><b>{esc(x['etiqueta'])}</b><br><code>{esc(nombre)}</code></td>"
            f"<td>{esc(x['definicion'])}</td><td>{esc(x['dueno'])}</td><td>{esc(x['equivalente_saas'])}</td></tr>")
    return "\n".join(filas)


def ficha_metrica(dic, nombre):
    x = dic["metricas"][nombre]
    crit = "".join(f"<li>{esc(c)}</li>" for c in x["criterios_de_lectura"])
    return f"""
<div class="ficha">
  <div class="ficha-cab"><code>{esc(nombre)}</code> · {esc(x['etiqueta'])}</div>
  <dl>
    <dt>Definición</dt><dd>{esc(x['definicion'])}</dd>
    <dt>Fórmula</dt><dd>{esc(x['formula'])}</dd>
    <dt>Dueño</dt><dd>{esc(x['dueno'])}</dd>
    <dt>Vista y filtro</dt><dd><code>{esc(x['vista'])}</code>, solo filas con <code>{esc(x.get('filtro', '—'))}</code></dd>
    <dt>Muestra mínima</dt><dd>{esc(x['muestra_minima'])} cierres. Por debajo, el resultado sale con <code>fiable: false</code></dd>
    <dt>Se puede abrir por</dt><dd>{esc(', '.join(x['dimensiones']))}</dd>
    <dt>Criterios de lectura</dt><dd><ul>{crit}</ul></dd>
    <dt>No confundir con</dt><dd><code>{esc(x['no_confundir_con'])}</code></dd>
    <dt>Equivalente en SaaS</dt><dd>{esc(x['equivalente_saas'])}</dd>
    <dt>Alerta</dt><dd>si cae por debajo de su línea base dividida entre {num(x['vigilar']['ratio'], 2)} y la caída es de al menos {esc(x['vigilar']['minimo'])} puntos</dd>
  </dl>
</div>"""


def graficos(d):
    g = {}
    # GMV mensual
    g["gmv"] = barras(
        [{"mes": f["mes"], "valor": f["valor"], "color": NARANJA if f["mes"] == "2017-11" else AZUL,
          "etiqueta": f["mes"] in ("2017-11", "2017-01", "2018-08")} for f in d["gmv_mes"]],
        ticks=[0, 250_000, 500_000, 750_000, 1_000_000, 1_250_000],
        fmt_tick=lambda t: "0" if t == 0 else (f"{num(t / 1e6, 2)} M" if t >= 1e6 else f"{num(t / 1e3)} mil"),
        fmt_valor=lambda v: f"{num(v / 1e6, 2)} M" if v >= 1e6 else f"{num(v / 1e3)} mil",
        titulo="GMV mensual en BRL, enero de 2017 a agosto de 2018")
    # Entregas tardías
    resaltar = {"2017-11", "2018-02", "2018-03"}
    g["tardias"] = barras(
        [{"mes": f["mes"], "valor": f["valor"], "color": NARANJA if f["mes"] in resaltar else AZUL,
          "etiqueta": f["mes"] in resaltar} for f in d["tardias_mes"]],
        ticks=[0, 5, 10, 15, 20, 25], fmt_tick=lambda t: f"{t} %",
        fmt_valor=lambda v: f"{num(v, 1)} %", titulo="Entregas tardías por mes de compra")
    # Tasa de cierre por mes de entrada del lead
    g["cierre_mes"] = barras(
        [{"mes": f["mes"], "valor": f["valor"],
          "color": GRIS if f["mes"] < "2018-01" else (NARANJA if f["mes"] == "2018-05" else AZUL),
          "etiqueta": True} for f in d["cierre_mes"]],
        ticks=[0, 4, 8, 12, 16], fmt_tick=lambda t: f"{t} %",
        fmt_valor=lambda v: f"{num(v, 1)}", alto=200,
        titulo="Tasa de cierre por mes de entrada del lead")
    # Censura
    meses_c = [r[0] for r in d["censura"] if r[0] >= "2018-01"]
    ingenua = {r[0]: r[2] for r in d["censura"] if r[0] >= "2018-01"}
    ventana = {r[0]: r[3] for r in d["censura"] if r[0] >= "2018-01" and r[4] >= 30}
    g["censura"] = lineas(
        meses_c,
        [{"nombre": "Sin ventana", "color": NARANJA, "valores": ingenua,
          "etiqueta": ("2018-07", 10, -8, "sin ventana", "start")},
         {"nombre": "Ventana de 90 días", "color": AZUL, "valores": ventana,
          "etiqueta": ("2018-02", 0, 22, "con ventana de 90 días", "middle")}],
        ticks=[0, 20, 40, 60], fmt_tick=lambda t: f"{t} %", sombra_desde="2018-06",
        texto_sombra="Aún sin 90 días de observación",
        titulo="Activación de los cierres por mes de cierre, con y sin ventana de 90 días")
    # Activación por tipo de lead
    filas = []
    for f in sorted(d["act_tipo"], key=lambda f: (not f["fiable"], -f["valor"])):
        gm = d["gmv90_tipo"][f["tipo_lead"]]
        filas.append({
            "etiqueta": f["tipo_lead"], "valor": f["valor"], "color": AZUL if f["fiable"] else GRIS,
            "derecha": (f"{f['muestra']} cierres · {num(gm['valor'])} BRL por cierre" if f["fiable"]
                        else f"{f['muestra']} cierres · no fiable")})
    g["act_tipo"] = barras_h(filas, vmax=80, fmt_valor=lambda v: f"{num(v, 1)} %",
                             titulo="Activación a 90 días por tipo de lead", der=230)
    # Tasa de cierre por origen
    filas = []
    for f in sorted(d["cierre_origen"], key=lambda f: (not f["fiable"], -f["valor"])):
        filas.append({"etiqueta": f["origen"], "valor": f["valor"], "color": AZUL if f["fiable"] else GRIS,
                      "derecha": f"{num(f['muestra'])} leads" + ("" if f["fiable"] else " · no fiable")})
    g["cierre_origen"] = barras_h(filas, vmax=30, fmt_valor=lambda v: f"{num(v, 1)} %",
                                  titulo="Tasa de cierre por origen del lead, leads de enero a mayo de 2018")
    # Retención neta y bruta
    meses_r = [k for k in sorted(d["nrr"]) if k >= "2017-02"]
    g["retencion"] = lineas(
        meses_r,
        [{"nombre": "Retención neta", "color": AZUL, "valores": {k: d["nrr"][k]["valor"] for k in meses_r},
          "etiqueta_final": lambda v: f"neta {num(v)} %"},
         {"nombre": "Retención bruta", "color": NARANJA, "valores": {k: d["grr"][k]["valor"] for k in meses_r},
          "etiqueta_final": lambda v: f"bruta {num(v)} %"}],
        ticks=[40, 60, 80, 100, 120, 140], fmt_tick=lambda t: f"{t} %",
        titulo="Retención neta y bruta de GMV, mes contra mes")
    return g


# ----------------------------------------------------------------------------- plantilla
PLANTILLA = Template(r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guía de datos y proyecto</title>
<style>
:root {
  --tinta: #1d1d1b; --tinta2: #52514e; --tenue: #7a7973; --linea: #dcdbd5; --suave: #f4f3ef;
  --azul: #2a78d6; --azul-suave: #eaf2fc; --naranja: #eb6834; --naranja-suave: #fdf0ea;
}
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; background: #fff; color: var(--tinta);
  font: 10.2pt/1.5 "Segoe UI", "Helvetica Neue", Arial, sans-serif; }
main { max-width: 176mm; margin: 0 auto; padding: 8mm 0; }
h1, h2, h3 { font-family: Georgia, "Times New Roman", serif; font-weight: 600; color: var(--tinta);
  break-after: avoid; page-break-after: avoid; }
h1 { font-size: 26pt; line-height: 1.15; margin: 0 0 6pt; letter-spacing: -0.01em; }
h2 { font-size: 17pt; margin: 26pt 0 8pt; padding-top: 10pt; border-top: 1px solid var(--linea); }
.capitulo h2 { margin-top: 0; padding-top: 0; border-top: 0; }
h2 .num { color: var(--azul); margin-right: 6pt; }
h3 { font-size: 12pt; margin: 16pt 0 5pt; }
p { margin: 0 0 7pt; }
ul, ol { margin: 0 0 8pt; padding-left: 16pt; }
li { margin-bottom: 3pt; }
code { font: 8.8pt/1.3 Consolas, "Cascadia Mono", monospace; background: var(--suave);
  padding: 0 3px; border-radius: 3px; }
b, strong { font-weight: 600; }
.capitulo { break-before: page; page-break-before: always; }
.portada { padding-top: 14mm; }
.eyebrow { font-size: 8.5pt; letter-spacing: .12em; text-transform: uppercase; color: var(--azul);
  font-weight: 600; margin-bottom: 10pt; }
.subtitulo { font-size: 13pt; color: var(--tinta2); margin: 0 0 14pt; }
.autor { font-size: 9.5pt; color: var(--tenue); border-top: 1px solid var(--linea); padding-top: 8pt;
  margin-bottom: 18pt; }
.lead { font-size: 11.5pt; line-height: 1.55; }
.cifras { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8pt; margin: 14pt 0 16pt; }
.cifra { border-top: 3px solid var(--azul); background: var(--suave); padding: 8pt 9pt 9pt; }
.cifra b { display: block; font: 600 20pt/1.1 Georgia, serif; }
.cifra span { font-size: 8.6pt; color: var(--tinta2); }
.pasos { counter-reset: paso; list-style: none; padding: 0; }
.pasos li { counter-increment: paso; position: relative; padding-left: 24pt; margin-bottom: 6pt; }
.pasos li::before { content: counter(paso); position: absolute; left: 0; top: 0; width: 16pt; height: 16pt;
  border-radius: 50%; background: var(--azul); color: #fff; font-size: 8.5pt; font-weight: 600;
  text-align: center; line-height: 16pt; }
.caja { background: var(--azul-suave); border-left: 3px solid var(--azul); padding: 8pt 11pt; margin: 10pt 0;
  break-inside: avoid; }
.caja.alerta { background: var(--naranja-suave); border-left-color: var(--naranja); }
.caja p:last-child, .caja ul:last-child { margin-bottom: 0; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0 12pt; font-size: 8.9pt; line-height: 1.38; }
th { text-align: left; font-weight: 600; color: var(--tinta2); border-bottom: 1.5px solid var(--tinta);
  padding: 4pt 6pt 4pt 0; vertical-align: bottom; }
td { border-bottom: 1px solid var(--linea); padding: 4pt 6pt 4pt 0; vertical-align: top; }
tr { break-inside: avoid; page-break-inside: avoid; }
td.n, th.n { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
td.grupo { color: var(--azul); font-weight: 600; white-space: nowrap; }
td code { font-size: 8pt; }
figure { margin: 10pt 0 14pt; break-inside: avoid; page-break-inside: avoid; }
figcaption { font-size: 9.5pt; font-weight: 600; margin-bottom: 4pt; }
figcaption span { display: block; font-weight: 400; color: var(--tinta2); font-size: 8.8pt; }
.fuente { font-size: 8pt; color: var(--tenue); margin-top: 3pt; }
svg { width: 100%; height: auto; display: block; }
svg text { font-family: "Segoe UI", Arial, sans-serif; }
svg .eje { font-size: 9.5px; fill: #6b6a64; }
svg .eje.anio { font-weight: 600; fill: #3d3c38; }
svg .valor { font-size: 10px; font-weight: 600; fill: #1d1d1b; }
svg .cat { font-size: 10.5px; fill: #1d1d1b; }
svg .nota { font-size: 9.5px; fill: #6b6a64; }
.leyenda { display: flex; gap: 14pt; font-size: 8.8pt; color: var(--tinta2); margin: 2pt 0 4pt; }
.leyenda i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px;
  vertical-align: -1px; }
.ficha { border: 1px solid var(--linea); border-radius: 4px; margin: 8pt 0 12pt; break-inside: avoid; font-size: 8.9pt; }
.ficha-cab { background: var(--suave); padding: 5pt 9pt; font-weight: 600; border-bottom: 1px solid var(--linea); }
.ficha dl { display: grid; grid-template-columns: 30mm 1fr; margin: 0; padding: 6pt 9pt; gap: 3pt 8pt; }
.ficha dt { color: var(--tinta2); font-weight: 600; }
.ficha dd { margin: 0; }
.ficha ul { margin: 0; padding-left: 12pt; }
.dos { display: grid; grid-template-columns: 1fr 1fr; gap: 12pt; }
.hallazgo h3 { margin-top: 18pt; }
.glosario { display: grid; grid-template-columns: 38mm 1fr; gap: 4pt 10pt; margin: 0 0 10pt; font-size: 9.4pt; }
.glosario dt { font-weight: 600; }
.glosario dd { margin: 0; color: var(--tinta2); }
pre { font: 8.6pt/1.45 Consolas, monospace; background: var(--suave); padding: 7pt 9pt; border-radius: 4px;
  white-space: pre-wrap; break-inside: avoid; margin: 4pt 0 10pt; }
.diagrama text { font-family: "Segoe UI", Arial, sans-serif; }
@page { size: A4; margin: 16mm 17mm 18mm; }
@media screen { body { background: #ecebe6; } main { background: #fff; padding: 16mm 17mm; margin: 10mm auto;
  max-width: 210mm; box-shadow: 0 1px 4px rgba(0,0,0,.12); } }
@media print { main { max-width: none; padding: 0; } }
</style>
</head>
<body>
<main>

<!-- ======================================================================= PORTADA -->
<section class="portada">
  <div class="eyebrow">Reto de Alegra · Business Intelligence &amp; Analytics Partner</div>
  <h1>Agente de métricas sobre datos reales de Olist</h1>
  <p class="subtitulo">Qué datos usa, cómo está construido y qué encontró.</p>
  <div class="autor">Julián Martínez Ortiz · noviembre de 2026 · construido con Claude Code</div>

  <p class="lead">Es un analista al que se le pregunta en español. Responde con cifras de datos reales,
  dice qué definición usó, avisa cuando un número no es fiable y termina en una recomendación con su
  forma de medirla.</p>

  <div class="cifras">
    <div class="cifra"><b>11</b><span>tablas reales cargadas, todas cuadran con su CSV</span></div>
    <div class="cifra"><b>23</b><span>métricas definidas en un solo diccionario</span></div>
    <div class="cifra"><b>6</b><span>herramientas que el agente puede usar</span></div>
    <div class="cifra"><b>107</b><span>pruebas automáticas en verde</span></div>
  </div>

  <h3>El problema que resuelve</h3>
  <p>Cuando un asistente de IA escribe su propio SQL, responde rápido, pero con su propia versión de
  cada métrica. Dos personas que preguntan lo mismo pueden recibir dos números distintos, y ninguno dice
  qué contó ni qué dejó por fuera.</p>
  <p>Aquí el asistente no inventa la métrica: se la pide a una capa que tiene <b>una sola definición de cada
  una</b>. Es la misma que usaría un tablero o un analista.</p>

  <h3>Cómo funciona, en cuatro pasos</h3>
  <ol class="pasos">
    <li>Los CSV de Olist se cargan en una base local (DuckDB) y se comprueba que no se perdió ninguna fila.</li>
    <li>Cinco archivos SQL limpian los datos una sola vez: sacan los pedidos cancelados, evitan duplicados y
    fijan ventanas de tiempo.</li>
    <li>Un diccionario (<code>metricas.yml</code>) define las 23 métricas: fórmula, dueño, trampas conocidas y
    equivalente en SaaS.</li>
    <li>Un servidor MCP le da a Claude Code seis herramientas para usar ese diccionario. Claude Code no calcula
    cifras oficiales por su cuenta.</li>
  </ol>

  <div class="caja">
    <p><b>Cómo se construyó.</b> Con Claude Code, el 15 de noviembre de 2026. Julián tomó las decisiones de
    producto y de datos: construir un agente nuevo, usar datos reales en vez de simulados, escoger Olist y
    definir cómo se entrega. Claude Code escribió el código, el SQL y las pruebas a partir de esas decisiones.</p>
  </div>
</section>

<!-- ======================================================================= 1. DATOS -->
<section class="capitulo">
  <h2><span class="num">1</span>Los datos</h2>

  <h3>De dónde salen</h3>
  <p>Son dos conjuntos de datos que publicó Olist en Kaggle:</p>
  <ul>
    <li><b>Marketing Funnel by Olist:</b> $leads leads calificados y $cierres negocios cerrados.</li>
    <li><b>Brazilian E-Commerce Public Dataset by Olist:</b> $pedidos pedidos de 2016 a 2018, con sus
    ítems, pagos, reseñas, clientes, vendedores y productos.</li>
  </ul>
  <p>Son <b>datos reales</b> de la operación de Olist, anonimizados por la propia empresa. No son simulados.
  Se escogieron después de revisar Kaggle: casi todos los datos de "SaaS" que hay allí son inventados, y el
  único real que apareció (KKBox) solo permite usarse en su competencia, en investigación o en educación, y prohíbe redistribuirlo.</p>
  <p>La licencia es <b>CC BY-NC-SA 4.0</b>: uso no comercial y con atribución a Olist. Los dos archivos se
  bajan del enlace público de Kaggle, sin iniciar sesión, y pesan cerca de 45 MB comprimidos. El paquete
  de entrega no los incluye: trae las instrucciones para bajarlos y el script que los carga.</p>

  <h3>Qué es Olist y por qué sirve para este reto</h3>
  <p>Olist es una empresa brasileña que conecta pequeños negocios con los grandes marketplaces de Brasil.
  Un negocio se registra en Olist y vende sus productos a través de la tienda de Olist en esos marketplaces.
  Eso deja dos procesos en los datos:</p>
  <ul>
    <li><b>Un embudo comercial B2B.</b> Un negocio deja sus datos en una página (lead), un SDR lo califica y un
    ejecutivo comercial (SR) lo cierra. Hay $sdr SDR y $sr SR en los datos. En este documento,
    "vendedor" es siempre el negocio que vende en Olist, nunca el SR.</li>
    <li><b>La actividad del negocio ya cerrado:</b> cuánto vende cada mes y cómo le va con sus clientes.</li>
  </ul>
  <p>Es el mismo dibujo de una empresa de software para pymes: conseguir pymes, cerrarlas y lograr que usen el
  producto mes a mes. La tabla muestra dónde se parece y dónde no.</p>
  <table>
    <tr><th>En Olist</th><th>En un SaaS para pymes</th><th>La diferencia que importa</th></tr>
    <tr><td>Lead calificado</td><td>Lead calificado (MQL)</td><td>Ninguna.</td></tr>
    <tr><td>Negocio cerrado</td><td>Cliente nuevo</td><td>Ninguna.</td></tr>
    <tr><td>Primera venta del vendedor</td><td>Activación</td><td>Ninguna: es el momento en que el cliente empieza a sacar valor.</td></tr>
    <tr><td>GMV del vendedor en el mes</td><td>MRR de la cuenta</td><td>El GMV no es ingreso de Olist ni es recurrente por contrato. <b>Nunca se llama MRR.</b></td></tr>
    <tr><td>Un mes sin ventas</td><td>Churn</td><td>En SaaS la baja es una cancelación. Aquí el vendedor puede volver al mes siguiente.</td></tr>
    <tr><td>Entregas y reseñas</td><td>Salud de la cuenta, soporte</td><td>Miden el servicio al cliente final, no al vendedor.</td></tr>
  </table>

  <h3>Las 11 tablas</h3>
  <table>
    <tr><th>Tabla</th><th class="n">Filas</th><th>Un renglón es</th><th>Lo que usa el proyecto</th></tr>
    <tr><td><code>marketing_qualified_leads</code></td><td class="n">$t_mql</td><td>un lead calificado</td><td>fecha del primer contacto, origen, página de entrada</td></tr>
    <tr><td><code>closed_deals</code></td><td class="n">$t_cd</td><td>un negocio cerrado</td><td>fecha de cierre, vendedor en que se convirtió, tipo de lead, tipo de negocio, segmento, SDR y SR</td></tr>
    <tr><td><code>sellers</code></td><td class="n">$t_sel</td><td>un vendedor</td><td>estado de Brasil del vendedor</td></tr>
    <tr><td><code>orders</code></td><td class="n">$t_ord</td><td>un pedido</td><td>estado del pedido, fecha de compra, fecha de entrega real y prometida</td></tr>
    <tr><td><code>order_items</code></td><td class="n">$t_it</td><td>un producto dentro de un pedido</td><td>precio y vendedor: es la base del GMV</td></tr>
    <tr><td><code>order_payments</code></td><td class="n">$t_pay</td><td>un pago de un pedido</td><td>nada. Un pedido puede tener varios pagos (ver trampas)</td></tr>
    <tr><td><code>order_reviews</code></td><td class="n">$t_rev</td><td>una reseña</td><td>nota de 1 a 5</td></tr>
    <tr><td><code>customers</code></td><td class="n">$t_cus</td><td>un cliente en un pedido</td><td>estado del cliente. La persona real es <code>customer_unique_id</code> ($clientes_unicos)</td></tr>
    <tr><td><code>products</code></td><td class="n">$t_pro</td><td>un producto</td><td>categoría</td></tr>
    <tr><td><code>product_category_name_translation</code></td><td class="n">$t_tr</td><td>una categoría</td><td>nombre en inglés</td></tr>
    <tr><td><code>geolocation</code></td><td class="n">$t_geo</td><td>un código postal con coordenadas</td><td>nada</td></tr>
  </table>
  <p><code>datos/cargar.py</code> carga cada CSV en una tabla de DuckDB y compara el número de filas con el
  del archivo. Las 11 cuadran. <code>closed_deals</code> trae más campos declarados por el vendedor, pero casi
  vacíos: solo $con_empresa de $cierres cierres dicen si tienen empresa y solo $declarado_ingreso declaran un
  ingreso mensual. Por eso no se usan.</p>

  <h3>Cómo se conectan</h3>
  $diagrama_modelo
  <p>El puente entre el embudo y los pedidos es <code>seller_id</code>, y solo existe para los negocios
  cerrados: de un lead que no cerró no se sabe nada más. De los $cierres cierres, <b>$cierres_con_venta
  aparecen con al menos una venta válida</b>. Los demás nunca vendieron o cerraron cuando los pedidos ya
  terminaban.</p>

  <h3>Qué periodo cubre cada parte</h3>
  $diagrama_fechas
  <p>Las tres partes no cubren las mismas fechas, y eso decide qué se puede medir:</p>
  <ul>
    <li><b>Pedidos:</b> de septiembre de 2016 a octubre de 2018, pero solo de enero de 2017 a agosto de 2018
    son meses completos. Antes y después hay entre $incompleto_min y $incompleto_max pedidos por mes, frente a
    miles en un mes normal.</li>
    <li><b>Leads:</b> primer contacto entre junio de 2017 y mayo de 2018. Es una muestra aleatoria, no el total.</li>
    <li><b>Cierres:</b> de diciembre de 2017 a noviembre de 2018. Antes de diciembre de 2017 no hay ningún
    cierre registrado, aunque sí hay leads de esos meses.</li>
  </ul>

  <h3>Lo que estos datos no tienen</h3>
  <div class="caja alerta">
    <p>No hay suscripciones, precios, comisiones de Olist ni gasto de adquisición. Por eso <b>no se puede
    calcular MRR, ARR, CAC ni LTV</b>, y el proyecto no los aproxima. Si se los piden al agente, dice que no
    están.</p>
    <p>La mecánica sí se muestra con datos reales: cohortes, retención neta y bruta, churn y movimientos de
    expansión y contracción, calculados sobre el GMV de los vendedores en lugar del MRR de las cuentas.</p>
  </div>
</section>

<!-- ======================================================================= TRAMPAS -->
<section>
  <h2><span class="num">2</span>Las trampas de estos datos</h2>
  <p>Son errores que no se ven en el resultado: el número sale, se ve razonable y está mal. Todos aparecieron
  en la exploración de los datos reales. Cada uno quedó resuelto una sola vez en la capa, para que ninguna
  métrica ni ningún agente tenga que acordarse.</p>
  <table>
    <tr><th>Trampa</th><th>Qué pasa si se ignora</th><th>Cómo quedó resuelta</th></tr>
    <tr><td>Unir ítems con pagos</td><td>Un pedido con dos pagos duplica sus ítems. El GMV sale $inflado % más alto: $gmv_pagos M en vez de $gmv_crudo M.</td><td>La vista de ítems nunca toca la tabla de pagos.</td></tr>
    <tr><td>Pedidos cancelados o no disponibles</td><td>Entran $excluidos pedidos que no fueron venta.</td><td>Se excluyen en la vista de pedidos, una sola vez.</td></tr>
    <tr><td>Meses incompletos</td><td>2016 y septiembre-octubre de 2018 parecen caídas del negocio.</td><td>Las cifras oficiales van de enero de 2017 a agosto de 2018.</td></tr>
    <tr><td>Censura en la activación</td><td>La activación parece desplomarse en los cierres recientes.</td><td>Se mide con una ventana fija de 90 días (gráfico abajo).</td></tr>
    <tr><td>Cierres registrados solo desde diciembre de 2017</td><td>Los leads de 2017 parecen cerrar entre 1 % y 5 %.</td><td>La tasa de cierre solo se lee para leads de enero a mayo de 2018.</td></tr>
    <tr><td>Muestras pequeñas</td><td>Un segmento con 6 cierres da un porcentaje que parece un hallazgo.</td><td>Cada métrica tiene una muestra mínima. Por debajo, sale marcada como no fiable.</td></tr>
    <tr><td>Pedidos sin ítems</td><td>$sin_items pedidos no tienen productos.</td><td>No entran al GMV ni al conteo de pedidos.</td></tr>
  </table>

  <figure>
    <figcaption>La activación parece caer, pero es falta de tiempo
      <span>Porcentaje de negocios cerrados que hicieron al menos una venta, según el mes del cierre.</span></figcaption>
    $leyenda_censura
    $g_censura
    <div class="fuente">Fuente: vista <code>v_cierres</code>. La línea azul solo incluye meses con al menos 30 cierres observables durante 90 días.</div>
  </figure>
  <p>Los pedidos terminan el 31 de agosto de 2018. Un negocio que cerró en enero tuvo siete meses para hacer
  su primera venta; uno que cerró en agosto tuvo días. Sin ventana, la activación "cae" de $cens_ene % a
  $cens_ago % y luego a 0 %. Con la ventana de 90 días, cada cierre tiene el mismo tiempo para vender y la
  tasa se queda entre $cens_min % y $cens_max %. <b>No hubo caída: faltaba tiempo.</b></p>

  <figure>
    <figcaption>Los leads de 2017 parecen no cerrar, pero sus cierres no están en los datos
      <span>Tasa de cierre (%) según el mes en que entró el lead. En gris, meses fuera de la ventana válida.</span></figcaption>
    $g_cierre_mes
    <div class="fuente">Fuente: métrica <code>tasa_cierre</code>. En naranja, mayo de 2018: el motor lo marca como alerta (ver hallazgos).</div>
  </figure>
</section>

<!-- ======================================================================= 3. PROYECTO -->
<section>
  <h2><span class="num">3</span>El proyecto</h2>

  <h3>La idea: una definición, tres consumidores</h3>
  <p>Growth pregunta por la activación, Sales por la conversión y Finance por la retención. Si cada uno, o cada
  asistente de IA, calcula a su manera, salen números distintos para la misma pregunta. La capa de métricas
  guarda una sola definición de cada una. El agente, un tablero y un analista la leen del mismo lugar, así que
  no pueden contradecirse.</p>

  <h3>Arquitectura</h3>
  $diagrama_arquitectura

  <h3>Las piezas, una por una</h3>
  <p><b>1. Carga</b> (<code>datos/cargar.py</code>). Descomprime los archivos de Kaggle, crea una tabla por
  CSV en <code>datos/olist.duckdb</code> y compara el número de filas de cada tabla con el de su archivo.
  Los archivos bajados se tratan como no confiables: se leen, nunca se ejecutan.</p>

  <p><b>2. Vistas SQL</b> (<code>capa/modelos/</code>, cinco archivos). Limpian y dan forma a los datos una
  sola vez:</p>
  <table>
    <tr><th>Vista</th><th>Un renglón es</th><th>Qué resuelve</th></tr>
    <tr><td><code>v_pedidos</code></td><td>un pedido válido</td><td>Excluye cancelados y no disponibles. Promedia las reseñas de cada pedido para no duplicarlo. Marca si llegó tarde.</td></tr>
    <tr><td><code>v_items</code></td><td>un producto vendido</td><td>Es la base del GMV. Le pega el estado del vendedor, la categoría y el tipo de lead. Nunca toca pagos.</td></tr>
    <tr><td><code>v_gmv_vendedor_mes</code></td><td>un vendedor en un mes</td><td>GMV y pedidos de cada vendedor por mes. Base de la retención y las cohortes.</td></tr>
    <tr><td><code>v_mov</code></td><td>un vendedor en un mes con cambio</td><td>Compara a cada vendedor con su mes anterior y lo clasifica: nuevo, expansión, contracción, baja o reactivación.</td></tr>
    <tr><td><code>v_leads</code></td><td>un lead</td><td>Mes de entrada, origen y si terminó cerrando.</td></tr>
    <tr><td><code>v_cierres</code></td><td>un negocio cerrado</td><td>Días hasta el cierre, primera venta, GMV en 90 días y si ya tiene 90 días de observación.</td></tr>
    <tr><td><code>v_cohortes</code></td><td>un vendedor en cada mes desde su primera venta</td><td>Si siguió vendiendo 1, 2, 3… meses después.</td></tr>
  </table>

  <p><b>3. Diccionario</b> (<code>capa/metricas.yml</code>). Es la fuente única. Cada métrica dice qué mide en
  lenguaje de negocio, cómo se calcula, quién es su dueño, por qué columnas se puede abrir, cuál es su muestra
  mínima, qué trampas tiene, con qué se suele confundir, cómo se llamaría en SaaS y, si aplica, cuándo debe
  disparar una alerta. Así se ve una completa:</p>
  $ficha
</section>

<section>
  <p><b>4. Motor</b> (<code>capa/motor.py</code>). Recibe un pedido ("activación a 90 días, por tipo de lead") y:</p>
  <ul>
    <li>revisa que la métrica exista y que se pueda abrir por esas columnas (si no, explica por qué);</li>
    <li>arma el SQL desde el diccionario, con los filtros como parámetros y nunca pegados al texto;</li>
    <li>marca cada fila como fiable o no según su muestra, y si está fuera de la ventana válida;</li>
    <li>devuelve el número, la definición, los criterios de lectura y el SQL que usó, para que se pueda auditar.</li>
  </ul>
  <p>La base se abre en <b>solo lectura</b> y sin acceso a archivos externos. El motor también descompone
  cambios y detecta anomalías (ver abajo).</p>

  <p><b>5. Servidor MCP</b> (<code>servidor_mcp.py</code>). MCP es el estándar abierto con el que un asistente
  de IA usa herramientas externas. El servidor le da a Claude Code seis:</p>
  <table>
    <tr><th>Herramienta</th><th>Para qué sirve</th></tr>
    <tr><td><code>listar_metricas</code></td><td>Ver qué métricas existen, con su definición corta.</td></tr>
    <tr><td><code>definir_metrica</code></td><td>Leer la definición completa de una antes de usarla.</td></tr>
    <tr><td><code>consultar_metrica</code></td><td>Calcularla por mes y por segmento. <b>Es la única fuente válida de cifras.</b></td></tr>
    <tr><td><code>descomponer_cambio</code></td><td>Explicar por qué cambió entre dos meses, segmento por segmento. En métricas que se suman (GMV), dice qué parte del cambio aporta cada segmento; en tasas, en cuáles cambió más y con cuánta muestra.</td></tr>
    <tr><td><code>detectar_anomalias</code></td><td>Revisar un mes contra la mediana de sus seis meses anteriores. Alerta solo si el desvío es grande en proporción <b>y</b> en tamaño, para no hacer ruido.</td></tr>
    <tr><td><code>sql_exploratorio</code></td><td>Mirar un detalle con SQL libre. Solo consultas de lectura, con tope de 500 filas, y la respuesta avisa que no es cifra oficial.</td></tr>
  </table>
  <p>La regla de anomalías (mediana como línea base, desvío relativo y mínimo absoluto a la vez) se adaptó de
  las alertas de desempeño que Julián usa en su trabajo actual, pasada de días a meses.</p>

  <p><b>6. Reglas del agente</b> (instrucciones del servidor). Viajan con el servidor, así que las recibe cualquier asistente que se conecte, no solo Claude Code. Cada respuesta dice además con qué versión del diccionario se calculó (versión y huella). Las principales:</p>
  <ul>
    <li>Toda cifra sale de <code>consultar_metrica</code>. Nada de recalcular a mano.</li>
    <li>Decir en una línea qué definición se usó y qué criterios de lectura afectan la respuesta.</li>
    <li>Si una fila no es fiable, decirlo y no sacar conclusiones de ella.</li>
    <li>Para un "¿por qué cambió?", descomponer por más de una dimensión antes de concluir.</li>
    <li>Terminar con una recomendación concreta y cómo medir si funcionó.</li>
    <li>Si piden MRR, ARR, CAC o LTV, decir que estos datos no los tienen.</li>
  </ul>

  <h3>Cómo responde una pregunta</h3>
  <p>El recorrido que piden las reglas, con la pregunta de la primera prueba real:</p>
  <div class="caja">
    <p><b>"Los negocios que cerramos, ¿de verdad terminan vendiendo? ¿A qué tipo de lead le debería dedicar más
    tiempo el equipo de ventas?"</b></p>
    <ol>
      <li>Busca la métrica que aplica: <code>tasa_activacion_90d</code> y <code>gmv_por_cierre_90d</code>.</li>
      <li>Lee su definición y sus trampas: la ventana de 90 días y la muestra mínima de 30 cierres.</li>
      <li>Las consulta abiertas por tipo de lead.</li>
      <li>Responde con la definición usada, la tabla, los segmentos no fiables señalados, una recomendación y
      cómo medirla.</li>
    </ol>
  </div>
  <p>Esa prueba se corrió con <code>claude -p</code> conectado al servidor. Respondió en 49 segundos y sus
  cifras coinciden con las del motor.</p>
</section>

<!-- ======================================================================= MÉTRICAS -->
<section>
  <h2><span class="num">4</span>Las 23 métricas</h2>
  <p>Agrupadas como las pide el aviso de Alegra: embudo, activación, ingresos, movimientos, retención y calidad.
  La columna de la derecha dice cómo se llamaría cada una con datos de suscripción. Esta tabla se genera
  directamente del diccionario.</p>
  <table class="metricas">
    <tr><th>Grupo</th><th>Métrica</th><th>Qué mide</th><th>Dueño</th><th>En SaaS</th></tr>
    $tabla_metricas
  </table>
</section>

<!-- ======================================================================= PRUEBAS -->
<section>
  <h2><span class="num">5</span>Cómo se comprobó</h2>
  <p>Que el código corra no dice que las cifras estén bien. Por eso cada cifra se comprueba contra un cálculo
  hecho por otro camino, no contra el resultado del propio motor.</p>
  <table>
    <tr><th>Prueba</th><th>Qué demuestra</th><th>Resultado</th></tr>
    <tr><td>Carga</td><td>Cada tabla tiene las mismas filas que su CSV.</td><td>11 de 11</td></tr>
    <tr><td>Recalculo independiente</td><td>Las métricas del motor coinciden con un cálculo aparte en pandas, leyendo los CSV crudos.</td><td rowspan="5"><b>107 pruebas en verde</b> (pytest, unos 2 minutos)</td></tr>
    <tr><td>Conciliación de movimientos</td><td>En cada mes, GMV anterior + nuevo + expansión + reactivación − contracción − bajas = GMV del mes.</td></tr>
    <tr><td>Trampas</td><td>Unir con pagos infla el GMV 4,5 % (se comprueba el número), los cancelados no entran y la censura está controlada.</td></tr>
    <tr><td>Seguridad del SQL libre</td><td>Se rechazan escrituras, borrados, varias sentencias, lectura de archivos y filtros con SQL escondido.</td></tr>
    <tr><td>Muestra y descomposición</td><td>Los segmentos pequeños salen como no fiables. Los aportes al cambio suman 100 %.</td></tr>
    <tr><td>Mutación</td><td>Se quitó a propósito la exclusión de pedidos "no disponibles" para ver si las pruebas lo notaban.</td><td>12 pruebas fallaron. Se restauró.</td></tr>
    <tr><td>Servidor como cliente real</td><td><code>pruebas/probar_servidor.py</code> llama las seis herramientas, incluida una métrica que no existe (<code>mrr</code>) y un <code>DROP TABLE</code>.</td><td>Las seis responden. Las dos llamadas malas se rechazan con un mensaje útil.</td></tr>
    <tr><td>De punta a punta</td><td>Una pregunta de negocio hecha a Claude Code con el servidor conectado.</td><td>Respuesta correcta en 49 s.</td></tr>
    <tr><td>Preguntas de control</td><td>Las mismas 12 preguntas de negocio a Claude Code (Sonnet), con la capa y solo con SQL libre sobre las tablas crudas.</td><td>Cifra oficial: <b>$ctl_con de $ctl_n_con con la capa</b>, $ctl_sin de $ctl_n_sin sin ella.</td></tr>
  </table>
  <div class="caja">
    <p><b>Lo que mostraron las preguntas de control.</b> Sin la capa, el agente respondió rápido y con
    seguridad, pero con su propia definición: contó pedidos cancelados, usó los pagos (que incluyen flete)
    para el ticket, cayó en la censura de la activación e incluyó leads de 2017 cuyos cierres no están
    registrados. No calculó mal: definió distinto. Con la capa, las 12 respuestas dieron la cifra oficial.
    El detalle, con el SQL que usó en cada caso, está en <code>pruebas/RESULTADOS.md</code>.</p>
  </div>

  <h3>Decisiones de diseño y por qué</h3>
  <table>
    <tr><th>Decisión</th><th>Por qué</th></tr>
    <tr><td>DuckDB local</td><td>No necesita servidor, lee los CSV directo y usa SQL casi estándar. Las vistas se pueden llevar a un warehouse con pocos cambios.</td></tr>
    <tr><td>Diccionario en YAML</td><td>Se lee como texto, se revisa en git y lo pueden leer una persona, el motor y el agente.</td></tr>
    <tr><td>MCP en vez de SQL libre</td><td>El agente solo puede pedir métricas que existen y abrirlas por columnas permitidas. No puede inventar una definición.</td></tr>
    <tr><td>Mediana como línea base</td><td>Un mes raro, como noviembre de 2017, no mueve la base de los meses siguientes.</td></tr>
    <tr><td>Alerta con dos condiciones</td><td>Un cambio grande en porcentaje pero chico en tamaño no genera ruido.</td></tr>
    <tr><td>Muestra mínima por métrica</td><td>No es igual leer un promedio de 100 pedidos que una tasa sobre 30 cierres. Cada métrica fija la suya.</td></tr>
    <tr><td>El SQL va con la respuesta</td><td>Cualquiera puede ver qué se contó y reproducir el número.</td></tr>
  </table>
</section>

<!-- ======================================================================= HALLAZGOS -->
<section>
  <h2><span class="num">6</span>Lo que muestran los datos</h2>
  <p>Todo sale de los datos reales. Nada se sembró: los hallazgos aparecieron en la exploración y cada cifra
  se reproduce con el motor.</p>

  <div class="hallazgo">
  <h3>1. Menos de la mitad de los cierres termina vendiendo</h3>
  <p>De $act_n cierres con 90 días de observación, <b>$act_tot % hizo al menos una venta</b> en ese plazo.
  En promedio, cada cierre vendió $gmv90_tot BRL en sus primeros 90 días, contando a los que no vendieron.
  El tipo de lead marca mucha diferencia:</p>
  <figure>
    <figcaption>Activación a 90 días por tipo de lead
      <span>Porcentaje de cierres con al menos una venta en 90 días. A la derecha, cierres y GMV por cierre en 90 días.</span></figcaption>
    $g_act_tipo
    <div class="fuente">En gris, segmentos con menos de 30 cierres: el motor los marca como no fiables.</div>
  </figure>
  <p>Por tipo de negocio: revendedor $act_rev % y $gmv_rev BRL por cierre ($n_rev cierres); fabricante
  $act_fab % y $gmv_fab BRL ($n_fab). Por origen: búsqueda pagada $act_paid % y búsqueda orgánica $act_org %.
  <b>Límite:</b> el tipo de lead solo existe en los negocios cerrados. Se sabe que unos venden más una vez
  cerrados, no si cierran más.</p>
  </div>

  <div class="hallazgo">
  <h3>2. La tasa de cierre depende mucho del origen</h3>
  <figure>
    <figcaption>Tasa de cierre por origen del lead
      <span>Leads que entraron de enero a mayo de 2018, la única ventana válida. Tasa total: $cierre_tot %.</span></figcaption>
    $g_cierre_origen
    <div class="fuente">En gris, grupos con menos de 50 leads: el motor los marca como no fiables.</div>
  </figure>
  <p>Búsqueda orgánica, búsqueda pagada y tráfico directo cierran cerca de 14 a 15 %; redes sociales y correo,
  entre 4 % y 6 %. El grupo "unknown" cierra $cierre_unknown %, pero no se sabe qué canal es. En mayo de 2018 la tasa total bajó a $cierre_may % frente a una base de $cierre_base %.
  Es una alerta real del motor.</p>
  </div>

  <div class="hallazgo">
  <h3>3. Noviembre de 2017 se sale de lo normal</h3>
  <figure>
    <figcaption>GMV mensual (BRL)
      <span>Venta de los vendedores en pedidos válidos, sin flete. Meses completos.</span></figcaption>
    $g_gmv
  </figure>
  <p>El GMV de noviembre de 2017 fue $nov_gmv BRL, frente a una base de $nov_base. Ese mismo mes las entregas
  tardías subieron a $nov_tard % (base $nov_tard_base %) y la nota de reseñas bajó a $nov_nota (base
  $nov_nota_base). La retención neta fue $nov_nrr % y en diciembre cayó a $dic_nrr %. El detector de anomalías
  marca las tres métricas en ese mes.</p>
  </div>

  <div class="hallazgo">
  <h3>4. Febrero y marzo de 2018: las entregas se retrasan</h3>
  <figure>
    <figcaption>Entregas tardías por mes de compra
      <span>De cada 100 pedidos entregados, cuántos llegaron después de la fecha prometida.</span></figcaption>
    $g_tardias
  </figure>
  <p>Las entregas tardías llegaron a $feb_tard % en febrero y <b>$mar_tard % en marzo</b> de 2018, frente a
  una base de $mar_tard_base %. La nota de reseñas bajó a $feb_nota y $mar_nota. El detector de anomalías marca las dos métricas en marzo. Los datos no dicen la causa,
  y el agente no debe afirmar ninguna.</p>
  </div>

  <div class="hallazgo">
  <h3>5. Los vendedores venden de forma intermitente</h3>
  <figure>
    <figcaption>Retención neta y bruta de GMV
      <span>Por cada 100 BRL que vendían el mes anterior los vendedores activos, cuánto venden este mes.</span></figcaption>
    $leyenda_ret
    $g_retencion
  </figure>
  <p>Cada mes, entre $churn_min % y $churn_max % de los vendedores activos no vende nada (churn mensual), y la
  retención bruta va de $grr_min % a $grr_max %. Pero parte de ellos vuelve: por eso el churn de un mes no es una
  pérdida definitiva, como sí lo es una cancelación en SaaS.</p>
  </div>
</section>

<!-- ======================================================================= ESTADO -->
<section>
  <h2><span class="num">7</span>Estado y lo que falta</h2>
  <h3>Hecho</h3>
  <ul>
    <li>Datos reales cargados y comprobados (11 tablas).</li>
    <li>Cinco archivos de vistas SQL, diccionario de 23 métricas, motor y servidor MCP con seis herramientas.</li>
    <li>107 pruebas en verde, prueba de mutación y prueba del servidor como cliente.</li>
    <li>Primera pregunta real respondida por Claude Code de punta a punta.</li>
    <li>Preguntas de control con y sin la capa: $ctl_con de $ctl_n_con contra $ctl_sin de $ctl_n_sin.</li>
    <li>Reglas para responder dentro del servidor y versión del diccionario en cada respuesta.</li>
    <li>README con atribución a Olist y licencia.</li>
    <li>Hallazgos y preguntas candidatas para la demo (<code>datos/hallazgos.md</code>).</li>
  </ul>
  <h3>Falta</h3>
  <ul>
    <li>Copia limpia del trabajo en Beemo para los primeros segundos del video.</li>
    <li>Guion (meta: 4 minutos 40 segundos), ensayos y grabación.</li>
    <li>Entrega en Teamtailor: el video, este PDF, el código sin los datos y las capturas.</li>
  </ul>

  <h3>Cómo correrlo</h3>
  <pre>uv venv .venv
uv pip install -r requirements.txt
.venv/Scripts/python.exe -I datos/cargar.py          # carga los CSV a datos/olist.duckdb
.venv/Scripts/python.exe -m pytest pruebas -q        # 107 pruebas
.venv/Scripts/python.exe pruebas/probar_servidor.py  # llama las 6 herramientas
claude                                               # Claude Code, con el servidor y las reglas</pre>

  <h3>Glosario</h3>
  <dl class="glosario">
    <dt>GMV</dt><dd>Valor de lo que venden los vendedores, sin flete. No es ingreso de Olist.</dd>
    <dt>BRL</dt><dd>Reales brasileños, la moneda de todos los valores.</dd>
    <dt>Lead calificado (MQL)</dt><dd>Negocio que pidió contacto y pasó el primer filtro de marketing.</dd>
    <dt>SDR y SR</dt><dd>El SDR califica al lead; el SR (ejecutivo comercial) lo cierra.</dd>
    <dt>Vendedor</dt><dd>El negocio que vende sus productos en Olist. No es el SR.</dd>
    <dt>Activación</dt><dd>Que un negocio cerrado haga su primera venta.</dd>
    <dt>Censura</dt><dd>Cuando los casos recientes todavía no han tenido tiempo de mostrar el resultado. Hace ver caídas que no existen.</dd>
    <dt>Cohorte</dt><dd>Grupo de vendedores que empezó en el mismo mes, seguido en el tiempo.</dd>
    <dt>Churn</dt><dd>Aquí, vendedor que vendió el mes anterior y este mes no vendió nada.</dd>
    <dt>Retención neta y bruta</dt><dd>Cuánto del GMV del mes anterior conservan los mismos vendedores. La neta suma lo que crecieron; la bruta solo cuenta lo que se perdió.</dd>
    <dt>Vista SQL</dt><dd>Una consulta guardada con nombre, que se usa como si fuera una tabla.</dd>
    <dt>DuckDB</dt><dd>Base de datos analítica que corre en un solo archivo, sin servidor.</dd>
    <dt>MCP</dt><dd>Model Context Protocol: estándar abierto para que un asistente de IA use herramientas externas.</dd>
    <dt>Claude Code</dt><dd>El asistente de programación de Anthropic con el que se construyó el proyecto y en el que corre el agente.</dd>
  </dl>
  <p class="fuente">Datos: Olist, "Marketing Funnel by Olist" y "Brazilian E-Commerce Public Dataset by Olist",
  Kaggle, licencia CC BY-NC-SA 4.0. Este documento se genera con <code>docs/generar_guia.py</code>; todas sus
  cifras salen del motor de métricas.</p>
</section>

</main>
</body>
</html>
""")


# ----------------------------------------------------------------------------- diagramas fijos
def caja(x, y, w, h, titulo, sub="", color=AZUL, relleno="#ffffff", grosor=1.5):
    t = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{relleno}" stroke="{color}" stroke-width="{grosor}"/>']
    cy = y + h / 2 + (-4 if sub else 4)
    t.append(f'<text x="{x + w / 2}" y="{cy}" text-anchor="middle" font-size="11" font-weight="600" fill="{TINTA}">{titulo}</text>')
    if sub:
        t.append(f'<text x="{x + w / 2}" y="{cy + 14}" text-anchor="middle" font-size="9.5" fill="{TINTA2}">{sub}</text>')
    return "".join(t)


def flecha(x1, y1, x2, y2, texto="", color=TINTA2, dx=0, dy=-5):
    t = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.3" marker-end="url(#punta)"/>']
    if texto:
        t.append(f'<text x="{(x1 + x2) / 2 + dx}" y="{(y1 + y2) / 2 + dy}" text-anchor="middle" font-size="9" '
                 f'font-family="Consolas, monospace" fill="{TINTA2}">{texto}</text>')
    return "".join(t)


DEFS = (f'<defs><marker id="punta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{TINTA2}"/></marker></defs>')


def diagrama_modelo(d):
    t = d["tablas"]
    n = lambda k: num(t[k])  # noqa: E731
    s = [f'<figure class="diagrama"><figcaption>Cómo se unen las tablas<span>Arriba, el embudo comercial. '
         f'Abajo, los pedidos. Las flechas dicen por qué columna se unen.</span></figcaption>'
         f'<svg viewBox="0 0 660 300" role="img" aria-label="Modelo de datos de Olist">{DEFS}']
    s.append(f'<rect x="2" y="6" width="656" height="78" rx="6" fill="#f4f8fd"/>')
    s.append(f'<text x="12" y="22" font-size="9.5" font-weight="600" fill="{AZUL}">EMBUDO · Marketing Funnel</text>')
    s.append(f'<rect x="2" y="104" width="656" height="192" rx="6" fill="#f7f6f2"/>')
    s.append(f'<text x="12" y="120" font-size="9.5" font-weight="600" fill="{TINTA2}">PEDIDOS · Brazilian E-Commerce</text>')
    s.append(caja(20, 32, 170, 42, "marketing_qualified_leads", f"{n('marketing_qualified_leads')} leads"))
    s.append(caja(250, 32, 150, 42, "closed_deals", f"{n('closed_deals')} cierres"))
    s.append(flecha(190, 53, 248, 53, "mql_id"))
    s.append(caja(470, 130, 150, 42, "sellers", f"{n('sellers')} vendedores", color=NARANJA, grosor=2))
    s.append(f'<path d="M400,53 L545,53 L545,128" fill="none" stroke="{NARANJA}" stroke-width="2" marker-end="url(#punta)"/>')
    s.append(f'<text x="470" y="47" text-anchor="middle" font-size="9" font-family="Consolas, monospace" fill="{NARANJA}">seller_id · el único puente</text>')
    s.append(caja(250, 130, 150, 42, "order_items", f"{n('order_items')} ítems"))
    s.append(flecha(468, 151, 402, 151, "seller_id"))
    s.append(caja(250, 222, 150, 42, "orders", f"{n('orders')} pedidos"))
    s.append(flecha(325, 172, 325, 220, "order_id", dx=26, dy=4))
    s.append(caja(20, 130, 150, 42, "products", f"{n('products')} productos"))
    s.append(flecha(248, 151, 172, 151, "product_id"))
    s.append(caja(20, 222, 150, 42, "customers", f"{n('customers')} clientes"))
    s.append(flecha(248, 243, 172, 243, "customer_id"))
    s.append(caja(470, 196, 150, 36, "order_payments", f"{n('order_payments')} pagos", color=GRIS))
    s.append(caja(470, 246, 150, 36, "order_reviews", f"{n('order_reviews')} reseñas"))
    s.append(flecha(402, 236, 468, 214, "", color=TINTA2))
    s.append(flecha(402, 250, 468, 264, "order_id", dy=14))
    s.append(f'<text x="545" y="192" text-anchor="middle" font-size="8.5" fill="{TINTA2}">no se usa para el GMV</text>')
    s.append(f'<text x="95" y="186" text-anchor="middle" font-size="8.5" fill="{TINTA2}">+ traducción de categorías ({n("product_category_name_translation")})</text>')
    s.append("</svg></figure>")
    return "".join(s)


def diagrama_fechas():
    # Eje: 2016-09 a 2018-12 (28 meses)
    x0, x1 = 150, 650
    inicio = (2016, 9)
    total = 28

    def xm(a, m):
        k = (a - inicio[0]) * 12 + (m - inicio[1])
        return x0 + (x1 - x0) * k / total

    filas = [
        ("Pedidos registrados", (2016, 9), (2018, 11), GRIS, "sep-2016 a oct-2018"),
        ("Meses completos", (2017, 1), (2018, 9), AZUL, "ene-2017 a ago-2018"),
        ("Leads (primer contacto)", (2017, 6), (2018, 6), AZUL, "jun-2017 a may-2018"),
        ("Cierres registrados", (2017, 12), (2018, 12), AZUL, "dic-2017 a nov-2018"),
        ("Tasa de cierre legible", (2018, 1), (2018, 6), NARANJA, "leads de ene a may-2018"),
        ("Activación a 90 días", (2017, 12), (2018, 6), NARANJA, "cierres hasta jun-2018"),
    ]
    s = ['<figure class="diagrama"><figcaption>Qué fechas cubre cada parte<span>En naranja, las ventanas '
         'en las que una métrica se puede leer sin sesgo.</span></figcaption>'
         '<svg viewBox="0 0 660 196" role="img" aria-label="Cobertura de fechas">']
    for a, m in [(2017, 1), (2018, 1)]:
        s.append(f'<line x1="{xm(a, m):.1f}" x2="{xm(a, m):.1f}" y1="6" y2="168" stroke="{REJILLA}" stroke-width="1"/>')
    for i, (et, (a1, m1), (a2, m2), color, nota) in enumerate(filas):
        y = 12 + i * 26
        s.append(f'<text x="{x0 - 10}" y="{y + 12}" text-anchor="end" font-size="10" fill="{TINTA}">{et}</text>')
        xa, xb = xm(a1, m1), xm(a2, m2)
        s.append(f'<rect x="{xa:.1f}" y="{y + 2}" width="{xb - xa:.1f}" height="14" rx="3" fill="{color}"/>')
        tx = xa + 6 if xb - xa > 150 else xb + 6
        fill = "#ffffff" if xb - xa > 150 and color != GRIS else TINTA
        s.append(f'<text x="{tx:.1f}" y="{y + 12.5}" font-size="9" fill="{fill}">{nota}</text>')
    for a, m, et in [(2016, 9, "sep 2016"), (2017, 1, "2017"), (2018, 1, "2018"), (2019, 1, "2019")]:
        s.append(f'<text x="{xm(a, m):.1f}" y="186" text-anchor="middle" font-size="9.5" fill="{TINTA2}">{et}</text>')
    s.append("</svg></figure>")
    return "".join(s)


def diagrama_arquitectura():
    s = ['<figure class="diagrama"><svg viewBox="0 0 660 250" role="img" aria-label="Arquitectura del proyecto">', DEFS]
    s.append(caja(6, 20, 104, 46, "CSV de Olist", "11 archivos"))
    s.append(caja(134, 20, 104, 46, "olist.duckdb", "cargar.py"))
    s.append(caja(262, 20, 104, 46, "Vistas SQL", "capa/modelos"))
    s.append(caja(390, 20, 112, 46, "metricas.yml", "23 definiciones", color=NARANJA, grosor=2))
    s.append(flecha(110, 43, 132, 43))
    s.append(flecha(238, 43, 260, 43))
    s.append(flecha(366, 43, 388, 43))
    s.append(caja(534, 20, 120, 46, "Tablero / analista", "mismo diccionario", color=GRIS))
    s.append(flecha(502, 43, 532, 43))
    s.append(caja(390, 112, 112, 46, "motor.py", "solo lectura"))
    s.append(flecha(446, 66, 446, 110))
    s.append(flecha(330, 66, 412, 110))
    s.append(caja(534, 112, 120, 46, "Pruebas", "107, contra pandas", color=GRIS))
    s.append(f'<line x1="532" y1="135" x2="504" y2="135" stroke="{TINTA2}" stroke-width="1.3" stroke-dasharray="4 3" marker-end="url(#punta)"/>')
    s.append(caja(390, 194, 112, 46, "servidor_mcp.py", "6 herramientas"))
    s.append(flecha(446, 158, 446, 192))
    s.append(caja(180, 194, 150, 46, "Claude Code", "+ CLAUDE.md (reglas)", color=TINTA, grosor=2))
    s.append(f'<line x1="388" y1="217" x2="332" y2="217" stroke="{TINTA2}" stroke-width="1.3" marker-end="url(#punta)" marker-start="url(#punta)"/>')
    s.append(caja(6, 194, 120, 46, "Persona", "pregunta en español", color=GRIS))
    s.append(f'<line x1="178" y1="217" x2="128" y2="217" stroke="{TINTA2}" stroke-width="1.3" marker-end="url(#punta)" marker-start="url(#punta)"/>')
    s.append(f'<text x="14" y="112" font-size="9.5" fill="{TINTA2}">La respuesta trae el número, la definición</text>')
    s.append(f'<text x="14" y="126" font-size="9.5" fill="{TINTA2}">usada, los criterios de lectura y el SQL</text>')
    s.append(f'<text x="14" y="140" font-size="9.5" fill="{TINTA2}">ejecutado. Claude Code no calcula cifras</text>')
    s.append(f'<text x="14" y="154" font-size="9.5" fill="{TINTA2}">oficiales: se las pide al servidor.</text>')
    s.append("</svg></figure>")
    return "".join(s)


# ----------------------------------------------------------------------------- armado
def main():
    d = recoger()
    g = graficos(d)
    t = d["tablas"]
    cens = {r[0]: r for r in d["censura"]}
    vent = [r[3] for r in d["censura"] if r[4] >= 30]
    an = {mes: {a["metrica"]: a for a in x["alertas"]} for mes, x in d["anom"].items()}
    tard = {f["mes"]: f["valor"] for f in d["tardias_mes"]}
    meses_ret = [k for k in d["churn"] if "2017-02" <= k <= "2018-08"]
    churn = [d["churn"][k]["valor"] for k in meses_ret]
    grr = [d["grr"][k]["valor"] for k in meses_ret]
    origen = d["act_origen"]
    neg = d["act_negocio"]
    g90n = d["gmv90_negocio"]

    valores = {
        "leads": num(t["marketing_qualified_leads"]), "cierres": num(t["closed_deals"]),
        "pedidos": num(t["orders"]), "sdr": d["sdr"], "sr": d["sr"],
        "t_mql": num(t["marketing_qualified_leads"]), "t_cd": num(t["closed_deals"]), "t_sel": num(t["sellers"]),
        "t_ord": num(t["orders"]), "t_it": num(t["order_items"]), "t_pay": num(t["order_payments"]),
        "t_rev": num(t["order_reviews"]), "t_cus": num(t["customers"]), "t_pro": num(t["products"]),
        "t_tr": num(t["product_category_name_translation"]), "t_geo": num(t["geolocation"]),
        "clientes_unicos": num(d["clientes_unicos"]), "con_empresa": d["con_empresa"],
        "declarado_ingreso": d["declarado_ingreso"], "cierres_con_venta": num(d["cierres_con_venta"]),
        "incompleto_min": num(d["incompleto_min"]), "incompleto_max": num(d["incompleto_max"]),
        "inflado": num(d["inflado_pct"], 1), "gmv_pagos": num(d["gmv_con_pagos"] / 1e6, 2),
        "gmv_crudo": num(d["gmv_crudo"] / 1e6, 2), "excluidos": num(d["excluidos"]),
        "sin_items": num(d["sin_items"]),
        "cens_ene": num(cens["2018-01"][2]), "cens_ago": num(cens["2018-08"][2]),
        "cens_min": num(min(vent)), "cens_max": num(max(vent)),
        "act_n": num(d["act_tot"]["muestra"]), "act_tot": num(d["act_tot"]["valor"], 1),
        "gmv90_tot": num(d["gmv90_tot"]["valor"]),
        "act_rev": num(neg["reseller"]["valor"], 1), "gmv_rev": num(g90n["reseller"]["valor"]),
        "n_rev": neg["reseller"]["muestra"],
        "act_fab": num(neg["manufacturer"]["valor"], 1), "gmv_fab": num(g90n["manufacturer"]["valor"]),
        "n_fab": neg["manufacturer"]["muestra"],
        "cierre_unknown": num(next(f["valor"] for f in d["cierre_origen"] if f["origen"] == "unknown"), 1),
        "act_paid": num(origen["paid_search"]["valor"], 1), "act_org": num(origen["organic_search"]["valor"], 1),
        "cierre_tot": num(d["cierre_tot"]["valor"], 1),
        "cierre_may": num(an["2018-05"]["tasa_cierre"]["valor_mes"], 1),
        "cierre_base": num(an["2018-05"]["tasa_cierre"]["linea_base"], 1),
        "nov_gmv": num(an["2017-11"]["gmv"]["valor_mes"]), "nov_base": num(an["2017-11"]["gmv"]["linea_base"]),
        "nov_tard": num(an["2017-11"]["entregas_tardias"]["valor_mes"], 1),
        "nov_tard_base": num(an["2017-11"]["entregas_tardias"]["linea_base"], 1),
        "nov_nota": num(an["2017-11"]["nota_resenas"]["valor_mes"], 2),
        "nov_nota_base": num(an["2017-11"]["nota_resenas"]["linea_base"], 2),
        "nov_nrr": num(d["nrr"]["2017-11"]["valor"]), "dic_nrr": num(d["nrr"]["2017-12"]["valor"]),
        "feb_tard": num(tard["2018-02"], 1), "mar_tard": num(an["2018-03"]["entregas_tardias"]["valor_mes"], 1),
        "mar_tard_base": num(an["2018-03"]["entregas_tardias"]["linea_base"], 1),
        "feb_nota": num(d["nota_mes"]["2018-02"], 2), "mar_nota": num(d["nota_mes"]["2018-03"], 2),
        "churn_min": num(min(churn)), "churn_max": num(max(churn)),
        "grr_min": num(min(grr)), "grr_max": num(max(grr)),
        "ctl_con": d["control"]["con_capa"]["igual"], "ctl_n_con": d["control"]["con_capa"]["n"],
        "ctl_sin": d["control"]["sin_capa"]["igual"], "ctl_n_sin": d["control"]["sin_capa"]["n"],
        "tabla_metricas": tabla_metricas(d["dic"]), "ficha": ficha_metrica(d["dic"], "tasa_activacion_90d"),
        "diagrama_modelo": diagrama_modelo(d), "diagrama_fechas": diagrama_fechas(),
        "diagrama_arquitectura": diagrama_arquitectura(),
        "g_censura": g["censura"], "g_cierre_mes": g["cierre_mes"], "g_act_tipo": g["act_tipo"],
        "g_cierre_origen": g["cierre_origen"], "g_gmv": g["gmv"], "g_tardias": g["tardias"],
        "g_retencion": g["retencion"],
        "leyenda_censura": leyenda([("Sin ventana: cualquier venta hasta agosto de 2018", NARANJA),
                                    ("Con ventana de 90 días", AZUL)]),
        "leyenda_ret": leyenda([("Retención neta", AZUL), ("Retención bruta", NARANJA)]),
    }
    SALIDA.write_text(PLANTILLA.substitute(valores), encoding="utf-8")
    print(f"escrito: {SALIDA}")


if __name__ == "__main__":
    main()
