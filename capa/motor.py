# -*- coding: utf-8 -*-
"""Motor de la capa de métricas.

Convierte una petición (métrica, periodo, dimensiones, filtros) en una consulta SQL sobre las
vistas de capa/modelos, usando solo lo que declara capa/metricas.yml. Devuelve el número, el
tamaño de muestra, si es fiable, el SQL ejecutado y la definición usada.

Reglas de diseño:
  * La base se abre en solo lectura y sin acceso a archivos externos.
  * Métrica, dimensiones y filtros se validan contra el diccionario (lista cerrada). Los valores
    de filtro viajan como parámetros, nunca pegados al SQL.
  * Un ratio con denominador 0 devuelve vacío, no 0. Un grupo con poca muestra se marca como no
    fiable en vez de ocultarse.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from statistics import median

import duckdb
import yaml

RAIZ = Path(__file__).resolve().parent.parent
BD = RAIZ / "datos" / "olist.duckdb"
MODELOS = RAIZ / "capa" / "modelos"
DICCIONARIO = RAIZ / "capa" / "metricas.yml"

_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_PROHIBIDO = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|install|load|pragma|set|"
    r"call|export|import|truncate|grant|vacuum|checkpoint|read_csv|read_parquet|read_json|"
    r"read_text|read_blob|glob)\b",
    re.IGNORECASE,
)


class ErrorDeMetrica(ValueError):
    """Petición que el diccionario no permite. El mensaje dice qué sí se puede pedir."""


def _a_fecha(mes: str) -> date:
    if not isinstance(mes, str) or not _MES.match(mes):
        raise ErrorDeMetrica(f"Mes inválido: {mes!r}. El formato es AAAA-MM, por ejemplo 2018-03.")
    return date(int(mes[:4]), int(mes[5:7]), 1)


def _mes_txt(d) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _sumar_meses(d: date, n: int) -> date:
    t = d.year * 12 + (d.month - 1) + n
    return date(t // 12, t % 12 + 1, 1)


def _limpio(v):
    """Números legibles: redondea decimales y convierte tipos de numpy/Decimal a nativos."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int,)):
        return int(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v if isinstance(v, str) else str(v)
    if f != f:                      # NaN
        return None
    return int(f) if f == int(f) and abs(f) < 1e15 else round(f, 2)


def huella_capa(diccionario: Path = DICCIONARIO, modelos: Path = MODELOS) -> str:
    """Huella corta del diccionario y de las vistas SQL. Cambia con cualquier edición de la capa.

    Normaliza los saltos de línea para que la misma capa dé la misma huella en Windows y Linux.
    """
    h = hashlib.sha256()
    for archivo in [Path(diccionario), *sorted(Path(modelos).glob("*.sql"))]:
        h.update(archivo.name.encode("utf-8"))
        h.update(archivo.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


class Motor:
    def __init__(self, bd: Path = BD, modelos: Path = MODELOS, diccionario: Path = DICCIONARIO,
                 con_modelos: bool = True):
        if not Path(bd).exists():
            raise FileNotFoundError(
                f"No existe {bd}. Corre primero: python -I datos/cargar.py datos/crudos datos/olist.duckdb")
        doc = yaml.safe_load(Path(diccionario).read_text(encoding="utf-8"))
        self.general: dict = doc["general"]
        self.metricas: dict = doc["metricas"]
        # Sello que viaja en cada respuesta: con qué versión de la capa se calculó el número.
        self.sello = {"version": str(self.general.get("version", "sin versión")),
                      "huella": huella_capa(diccionario, modelos)}
        self.primer_mes = _a_fecha(self.general["primer_mes_completo"])
        self.ultimo_mes = _a_fecha(self.general["ultimo_mes_completo"])
        self.con = duckdb.connect(str(bd), read_only=True)
        if con_modelos:
            for archivo in sorted(Path(modelos).glob("*.sql")):
                self.con.execute(archivo.read_text(encoding="utf-8"))
        # Después de crear las vistas se cierra el acceso a archivos y se bloquea la configuración.
        self.con.execute("SET enable_external_access = false")
        self.con.execute("SET lock_configuration = true")

    # ------------------------------------------------------------------ diccionario
    def _def(self, nombre: str) -> dict:
        if nombre not in self.metricas:
            raise ErrorDeMetrica(
                f"La métrica {nombre!r} no existe en el diccionario. Disponibles: "
                + ", ".join(sorted(self.metricas)))
        return self.metricas[nombre]

    def listar(self) -> dict:
        return {
            "diccionario": self.sello,
            "general": self.general,
            "metricas": [
                {"nombre": n, "etiqueta": m["etiqueta"], "grupo": m["grupo"], "unidad": m["unidad"],
                 "definicion": m["definicion"], "dimensiones": m["dimensiones"]}
                for n, m in self.metricas.items()
            ],
        }

    def definir(self, nombre: str) -> dict:
        m = self._def(nombre)
        campos = ["etiqueta", "grupo", "dueno", "definicion", "formula", "unidad", "aditiva",
                  "dimensiones", "muestra_minima", "criterios_de_lectura", "no_confundir_con",
                  "equivalente_saas"]
        out = {"nombre": nombre, **{c: m.get(c) for c in campos}}
        out["sql_valor"] = m["valor"]
        out["vista"] = m["vista"]
        out["filtro_fijo"] = m.get("filtro")
        out["ventana_valida"] = m.get("ventana_valida")
        out["periodo_con_meses_completos"] = f"{_mes_txt(self.primer_mes)} a {_mes_txt(self.ultimo_mes)}"
        out["diccionario"] = self.sello
        return out

    # --------------------------------------------------------------------- consulta
    def consultar(self, metrica: str, desde: str | None = None, hasta: str | None = None,
                  dimensiones: list[str] | None = None, filtros: dict | None = None,
                  por_mes: bool = True) -> dict:
        m = self._def(metrica)
        dimensiones = list(dimensiones or [])
        filtros = dict(filtros or {})
        permitidas = m["dimensiones"]
        for d in dimensiones + list(filtros):
            if d not in permitidas:
                raise ErrorDeMetrica(
                    f"{metrica!r} no se puede abrir ni filtrar por {d!r}. Dimensiones permitidas: "
                    + (", ".join(permitidas) or "ninguna"))
        ventana = m.get("ventana_valida")
        v_desde = _a_fecha(ventana["desde"]) if ventana else None
        v_hasta = _a_fecha(ventana["hasta"]) if ventana else None
        f_desde = _a_fecha(desde) if desde else (v_desde or self.primer_mes)
        f_hasta = _a_fecha(hasta) if hasta else (v_hasta or self.ultimo_mes)
        if f_desde > f_hasta:
            raise ErrorDeMetrica("El mes inicial es posterior al mes final.")
        advertencias = []
        fuera_total = bool(ventana and (f_desde < v_desde or f_hasta > v_hasta))
        if fuera_total:
            advertencias.append(
                f"El periodo pedido incluye meses fuera de la ventana válida de esta métrica "
                f"({ventana['desde']} a {ventana['hasta']}). Esos meses no son fiables.")

        columnas = (["mes"] if por_mes else []) + dimensiones
        donde = ["mes BETWEEN ? AND ?"]
        params: list = [f_desde, f_hasta]
        if m.get("filtro"):
            donde.append(f"({m['filtro']})")
        for d, v in filtros.items():
            donde.append(f"{d} = ?")
            params.append(v)
        sel = ", ".join(columnas + [f"{m['valor']} AS valor", f"{m['muestra']} AS muestra"])
        sql = f"SELECT {sel}\nFROM {m['vista']}\nWHERE {' AND '.join(donde)}"
        if columnas:
            sql += f"\nGROUP BY {', '.join(columnas)}\nORDER BY {', '.join(columnas)}"

        cur = self.con.execute(sql, params)
        nombres = [c[0] for c in cur.description]
        minimo = m.get("muestra_minima", 1)
        filas = []
        for r in cur.fetchall():
            fila = dict(zip(nombres, r))
            if "mes" in fila:
                completo = self.primer_mes <= fila["mes"] <= self.ultimo_mes
                fila["mes"] = _mes_txt(fila["mes"])
                if not completo and m["vista"] in ("v_items", "v_pedidos", "v_mov"):
                    fila["mes_incompleto"] = True
            fila["valor"] = _limpio(fila["valor"])
            fila["muestra"] = _limpio(fila["muestra"])
            fila["fiable"] = bool(fila["muestra"] is not None and fila["muestra"] >= minimo
                                  and fila["valor"] is not None)
            if ventana:
                fuera = (not (v_desde <= _a_fecha(fila["mes"]) <= v_hasta)) if "mes" in fila else fuera_total
                if fuera:
                    fila["fuera_de_ventana"] = True
                    fila["fiable"] = False
            for d in dimensiones:
                fila[d] = _limpio(fila[d])
            filas.append(fila)

        return {
            "metrica": metrica,
            "etiqueta": m["etiqueta"],
            "unidad": m["unidad"],
            "definicion": m["definicion"],
            "formula": m["formula"],
            "criterios_de_lectura": m["criterios_de_lectura"],
            "periodo": {"desde": _mes_txt(f_desde), "hasta": _mes_txt(f_hasta), "por_mes": por_mes},
            "filtros": filtros,
            "muestra_minima": minimo,
            "advertencias": advertencias,
            "filas": filas,
            "sql": self._sql_legible(sql, params),
            "diccionario": self.sello,
        }

    @staticmethod
    def _sql_legible(sql: str, params: list) -> str:
        """SQL con los parámetros puestos, solo para mostrarlo. No es el que se ejecuta."""
        partes = sql.split("?")
        out = partes[0]
        for p, resto in zip(params, partes[1:]):
            if isinstance(p, date):
                lit = f"DATE '{p.isoformat()}'"
            elif isinstance(p, bool):
                lit = "true" if p else "false"
            elif isinstance(p, (int, float)):
                lit = str(p)
            else:
                lit = "'" + str(p).replace("'", "''") + "'"
            out += lit + resto
        return out

    def valor(self, metrica: str, mes: str, filtros: dict | None = None) -> dict:
        """Un solo número: la métrica en un mes."""
        r = self.consultar(metrica, mes, mes, filtros=filtros, por_mes=False)
        return r["filas"][0] if r["filas"] else {"valor": None, "muestra": 0, "fiable": False}

    # ---------------------------------------------------------------- descomposición
    def descomponer(self, metrica: str, mes_base: str, mes_comparado: str, dimension: str) -> dict:
        """Abre el cambio de una métrica entre dos meses por una dimensión.

        Métrica aditiva: cuánto aporta cada segmento al cambio total (los aportes suman 100 %).
        Métrica de tasa: valor de cada segmento en ambos meses, con su muestra. Una tasa no se
        reparte en aportes, así que se muestra dónde cambió más y con cuánta muestra.
        """
        m = self._def(metrica)
        a = self.consultar(metrica, mes_base, mes_base, [dimension], por_mes=False)
        b = self.consultar(metrica, mes_comparado, mes_comparado, [dimension], por_mes=False)
        tot_a = self.valor(metrica, mes_base)
        tot_b = self.valor(metrica, mes_comparado)
        por_a = {f[dimension]: f for f in a["filas"]}
        por_b = {f[dimension]: f for f in b["filas"]}
        cambio_total = None
        if tot_a["valor"] is not None and tot_b["valor"] is not None:
            cambio_total = round(tot_b["valor"] - tot_a["valor"], 2)

        segmentos = []
        for clave in sorted(set(por_a) | set(por_b), key=str):
            fa, fb = por_a.get(clave), por_b.get(clave)
            va = fa["valor"] if fa else None
            vb = fb["valor"] if fb else None
            if m["aditiva"]:
                va, vb = va or 0, vb or 0
            cambio = round(vb - va, 2) if va is not None and vb is not None else None
            seg = {
                dimension: clave,
                "valor_base": va, "valor_comparado": vb, "cambio": cambio,
                "muestra_base": fa["muestra"] if fa else 0,
                "muestra_comparado": fb["muestra"] if fb else 0,
                "fiable": bool((fa is None or fa["fiable"]) and (fb is None or fb["fiable"])
                               and (fa or fb)) if m["aditiva"]
                          else bool(fa and fb and fa["fiable"] and fb["fiable"]),
            }
            if m["aditiva"] and cambio_total:
                seg["aporte_al_cambio_pct"] = round(100.0 * cambio / cambio_total, 1)
            segmentos.append(seg)
        segmentos.sort(key=lambda s: -abs(s["cambio"]) if s["cambio"] is not None else 0)

        return {
            "metrica": metrica, "etiqueta": m["etiqueta"], "unidad": m["unidad"],
            "definicion": m["definicion"], "dimension": dimension,
            "mes_base": mes_base, "mes_comparado": mes_comparado,
            "total_base": tot_a["valor"], "total_comparado": tot_b["valor"],
            "cambio_total": cambio_total,
            "como_leer": (
                "Métrica aditiva: aporte_al_cambio_pct dice qué parte del cambio total explica cada "
                "segmento. Los aportes suman 100." if m["aditiva"] else
                "Métrica de tasa: no se reparte en aportes. Mira en qué segmentos cambió más y "
                "descarta los que no son fiables por poca muestra."),
            "segmentos": segmentos[:25],
            "segmentos_omitidos": max(0, len(segmentos) - 25),
            "criterios_de_lectura": m["criterios_de_lectura"],
            "diccionario": self.sello,
        }

    # --------------------------------------------------------------------- anomalías
    def anomalias(self, mes: str, meses_base: int = 6) -> dict:
        """Compara cada métrica vigilada contra la mediana de sus meses anteriores.

        Dispara solo si se cumplen las dos condiciones a la vez: desvío relativo (ratio) y
        desvío absoluto mínimo. Así un cambio grande en porcentaje pero irrelevante en tamaño
        no genera ruido. Usa la mediana para que un mes raro no mueva la línea base.
        """
        f_mes = _a_fecha(mes)
        base_meses = [_sumar_meses(f_mes, -k) for k in range(meses_base, 0, -1)]
        base_meses = [b for b in base_meses if b >= self.primer_mes]
        alertas, sin_alerta, no_evaluadas = [], [], []

        for nombre, m in self.metricas.items():
            regla = m.get("vigilar")
            if not regla:
                continue
            actual = self.valor(nombre, mes)
            previos = [self.valor(nombre, _mes_txt(b)) for b in base_meses]
            validos = [p["valor"] for p in previos if p.get("fiable") and p["valor"] is not None]
            if actual["valor"] is None or not actual.get("fiable") or len(validos) < 3:
                no_evaluadas.append({"metrica": nombre, "motivo":
                                     "sin dato fiable en el mes" if len(validos) >= 3
                                     else "menos de 3 meses fiables de base"})
                continue
            base = float(median(validos))
            a = float(actual["valor"])
            ratio, minimo, sentido = regla["ratio"], regla["minimo"], regla["sentido"]
            sube = base > 0 and a >= base * ratio and (a - base) >= minimo
            baja = base > 0 and a <= base / ratio and (base - a) >= minimo
            dispara = (sube and sentido in ("sube", "ambos")) or (baja and sentido in ("baja", "ambos"))
            fila = {
                "metrica": nombre, "etiqueta": m["etiqueta"], "unidad": m["unidad"],
                "valor_mes": _limpio(a), "linea_base": _limpio(base),
                "cambio": _limpio(a - base),
                "cambio_pct": _limpio(100.0 * (a - base) / base) if base else None,
                "meses_en_la_base": len(validos),
            }
            if dispara:
                fila["direccion"] = "sube" if sube else "baja"
                fila["regla"] = f"desvío de al menos {ratio}x y de al menos {minimo} {m['unidad']}"
                alertas.append(fila)
            else:
                sin_alerta.append(fila)

        alertas.sort(key=lambda f: -abs(f["cambio_pct"] or 0))
        return {
            "mes": mes,
            "linea_base": f"mediana de los {len(base_meses)} meses anteriores",
            "alertas": alertas,
            "sin_alerta": sin_alerta,
            "no_evaluadas": no_evaluadas,
            "como_leer": "Una alerta dice que el mes se salió de su propia historia, no por qué. "
                         "Para la causa, usa descomponer_cambio sobre la métrica alertada.",
            "diccionario": self.sello,
        }

    # ------------------------------------------------------------------ SQL libre
    def sql_libre(self, sql: str, limite: int = 200) -> dict:
        """Consulta de exploración. Solo un SELECT, con tope de filas. No es cifra oficial."""
        texto = sql.strip().rstrip(";").strip()
        if ";" in texto:
            raise ErrorDeMetrica("Solo se permite una sentencia.")
        if not re.match(r"^(select|with)\b", texto, re.IGNORECASE):
            raise ErrorDeMetrica("Solo se permiten consultas SELECT.")
        if _PROHIBIDO.search(texto):
            raise ErrorDeMetrica("La consulta usa una operación no permitida. Solo lectura de tablas y vistas.")
        limite = max(1, min(int(limite), 500))
        cur = self.con.execute(f"SELECT * FROM ({texto}) AS t LIMIT {limite + 1}")
        nombres = [c[0] for c in cur.description]
        datos = cur.fetchall()
        truncado = len(datos) > limite
        filas = [{n: _limpio(v) if not hasattr(v, "isoformat") else v.isoformat()
                  for n, v in zip(nombres, r)} for r in datos[:limite]]
        return {
            "aviso": "Consulta exploratoria. No es una métrica oficial: no aplica las definiciones "
                     "ni las exclusiones del diccionario. Para una cifra oficial usa consultar_metrica.",
            "filas": filas,
            "truncado": truncado,
        }
