# -*- coding: utf-8 -*-
"""Preguntas de control: ¿la capa de métricas cambia las respuestas del agente?

Corre cada pregunta de pruebas/preguntas_control.yml con Claude Code (`claude -p`) en dos
condiciones, con el mismo modelo y la misma instrucción de formato:

  con_capa   solo las herramientas del servidor de métricas (servidor_mcp.py), desde la
             carpeta del proyecto.
  sin_capa   solo SQL de lectura sobre las tablas crudas (pruebas/servidor_sql_crudo.py),
             desde una carpeta temporal vacía: sin diccionario, sin vistas, sin CLAUDE.md.

La cifra esperada la calcula el motor. Cada corrida guarda su transcripción completa en
pruebas/corridas/ y una fila en resultados.jsonl apenas termina; si se interrumpe, al volver a
correrlo salta lo que ya está hecho. Al final escribe pruebas/RESULTADOS.md.

Uso: .venv/Scripts/python.exe pruebas/evaluar_agente.py [--modelo sonnet] [--solo q01_gmv,...]
                                                          [--informe]   (solo rehace el informe)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from capa.motor import Motor  # noqa: E402

PREGUNTAS = RAIZ / "pruebas" / "preguntas_control.yml"
CORRIDAS = RAIZ / "pruebas" / "corridas"
RESULTADOS = CORRIDAS / "resultados.jsonl"
INFORME = RAIZ / "pruebas" / "RESULTADOS.md"
PYTHON = RAIZ / ".venv" / "Scripts" / "python.exe"
CONDICIONES = ("con_capa", "sin_capa")
TOL_REL = 0.005
TIEMPO_MAX = 600

FORMATO = (
    "\n\nAl final de tu respuesta, en una línea aparte, escribe exactamente `RESPUESTA_FINAL: ` "
    "seguido del número, sin unidades ni separador de miles y con punto decimal (por ejemplo "
    "`RESPUESTA_FINAL: 1234.5`; para un porcentaje, solo el número: `RESPUESTA_FINAL: 12.3`). "
    "Si los datos no permiten calcularlo, escribe `RESPUESTA_FINAL: NO_DISPONIBLE`."
)


# ----------------------------------------------------------------------------- esperado y nota
def esperado(motor: Motor, spec: dict):
    if spec.get("no_disponible"):
        return "NO_DISPONIBLE"
    r = motor.consultar(spec["metrica"], spec.get("desde"), spec.get("hasta"),
                        filtros=spec.get("filtros"), por_mes=False)
    return r["filas"][0]["valor"]


def leer_numero(texto: str):
    """Saca el valor de la línea RESPUESTA_FINAL. Devuelve número, 'NO_DISPONIBLE' o None."""
    hallados = re.findall(r"RESPUESTA_FINAL:\s*`?\s*([^\s`]+)", texto or "")
    if not hallados:
        return None
    v = hallados[-1].strip().rstrip(".").replace("%", "")
    if v.upper().startswith("NO_DISPONIBLE"):
        return "NO_DISPONIBLE"
    if "," in v and "." in v:
        v = v.replace(",", "")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})+", v):
        v = v.replace(",", "")
    else:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


# Margen de redondeo para "igual": lo que cambia al escribir la cifra con menos decimales.
REDONDEO = {"%": 0.051, "puntos": 0.006, "conteo": 0.5, "BRL": 0.51, "días": 0.5}


def clasificar(valor, objetivo, unidad: str | None, tol_abs: float = 0.0) -> str:
    """igual: la cifra oficial (salvo redondeo). cerca: a menos de 0,5 %. distinta: lo demás."""
    if valor is None:
        return "sin_respuesta"
    if objetivo == "NO_DISPONIBLE" or valor == "NO_DISPONIBLE":
        return "igual" if valor == objetivo else "distinta"
    if objetivo is None:
        return "distinta"
    d = abs(valor - objetivo)
    if d <= REDONDEO.get(unidad, 0.0) or d <= 1e-9:
        return "igual"
    if d <= max(TOL_REL * abs(objetivo), tol_abs):
        return "cerca"
    return "distinta"


# ----------------------------------------------------------------------------- corrida
def comando(cond: str, pregunta: str, modelo: str, carpeta_sin_capa: Path) -> tuple[list[str], Path]:
    base = [shutil.which("claude") or "claude", "-p", pregunta + FORMATO, "--model", modelo,
            "--output-format", "stream-json", "--verbose", "--strict-mcp-config", "--tools", "",
            "--no-session-persistence", "--setting-sources", "project,local"]
    if cond == "con_capa":
        return base + ["--mcp-config", str(RAIZ / ".mcp.json"),
                       "--allowedTools", "mcp__metricas__*"], RAIZ
    return base + ["--mcp-config", str(carpeta_sin_capa / "mcp.json"),
                   "--allowedTools", "mcp__crudo__*"], carpeta_sin_capa


def correr(q: dict, cond: str, modelo: str, carpeta_sin_capa: Path) -> dict:
    cmd, cwd = comando(cond, q["pregunta"].strip(), modelo, carpeta_sin_capa)
    traza = CORRIDAS / f"{q['id']}__{cond}.jsonl"
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           timeout=TIEMPO_MAX, env={**__import__("os").environ, "PYTHONUTF8": "1"})
        salida, err = p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        salida, err = (e.stdout or ""), f"timeout {TIEMPO_MAX}s"
    # Se guarda la conversación sin el evento de arranque, que trae rutas y configuración de la máquina.
    conversacion = [l for l in salida.splitlines() if '"type":"system"' not in l.replace(" ", "")]
    traza.write_text(chr(10).join(conversacion), encoding="utf-8")
    fila = {"id": q["id"], "condicion": cond, "modelo": modelo, "segundos_reloj": round(time.time() - t0, 1)}
    llamadas, final = [], None
    for linea in salida.splitlines():
        try:
            e = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            fila["modelo_real"] = e.get("model")
        if e.get("type") == "assistant":
            for b in e["message"].get("content", []):
                if b.get("type") == "tool_use":
                    llamadas.append({"herramienta": b["name"], "entrada": b.get("input")})
        if e.get("type") == "result":
            final = e
    if final is None or final.get("is_error") or not final.get("duration_ms"):
        fila.update({"estado": "error", "detalle": (err or "sin evento result")[-500:]})
        return fila
    fila.update({
        "estado": "ok",
        "respuesta": final.get("result", ""),
        "segundos": round(final["duration_ms"] / 1000, 1),
        "turnos": final.get("num_turns"),
        "costo_usd_estimado": final.get("total_cost_usd"),
        "llamadas": llamadas,
    })
    return fila


# ----------------------------------------------------------------------------- informe
def fmt(v):
    if v is None:
        return "sin respuesta"
    if isinstance(v, str):
        return v
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s[:-3] if s.endswith(",00") else s


def informe(preguntas: list[dict], filas: list[dict], modelo: str) -> str:
    por = {(f["id"], f["condicion"]): f for f in filas}
    tot = {c: {"igual": 0, "cerca": 0, "distinta": 0, "sin_respuesta": 0, "n": 0, "err": 0,
               "seg": [], "llamadas": [], "costo": []} for c in CONDICIONES}
    simbolo = {"igual": "✅", "cerca": "🟡", "distinta": "❌", "sin_respuesta": "❌"}
    lineas_tabla = []
    for q in preguntas:
        celdas = []
        for c in CONDICIONES:
            f = por.get((q["id"], c))
            if not f:
                celdas.append("no corrida")
                continue
            if f["estado"] != "ok":
                tot[c]["err"] += 1
                celdas.append("error de corrida")
                continue
            tot[c]["n"] += 1
            tot[c][f["nota"]] += 1
            tot[c]["seg"].append(f["segundos"])
            tot[c]["llamadas"].append(len(f["llamadas"]))
            if f.get("costo_usd_estimado") is not None:
                tot[c]["costo"].append(f["costo_usd_estimado"])
            celdas.append(f"{simbolo[f['nota']]} {fmt(f['valor'])}")
        esp = next((f["esperado"] for f in filas if f["id"] == q["id"] and "esperado" in f), None)
        lineas_tabla.append(f"| {q['id']} | {q['pregunta'].strip()} | {fmt(esp)} | {celdas[0]} | {celdas[1]} | {q['trampa']} |")

    def prom(xs):
        return sum(xs) / len(xs) if xs else 0

    out = [
        "# Preguntas de control: con capa y sin capa",
        "",
        f"Corrida con Claude Code (`claude -p`), modelo `{modelo}`. Generado por `pruebas/evaluar_agente.py`.",
        "",
        "- **Con capa:** el agente solo tiene las herramientas del servidor de métricas.",
        "- **Sin capa:** el agente solo tiene SQL de lectura sobre las tablas crudas, desde una carpeta",
        "  vacía: no ve el diccionario, las vistas, las reglas ni las trampas conocidas.",
        "- Misma pregunta, mismo modelo y misma instrucción de formato en las dos condiciones.",
        "- La cifra oficial es la del diccionario y la calcula el motor. Cada respuesta se clasifica:",
        "  ✅ **igual** a la cifra oficial (salvo redondeo), 🟡 **cerca** (a menos de 0,5 %, pero otra",
        "  cifra) o ❌ **distinta**. Una cifra distinta no siempre es un error de cálculo: muchas veces",
        "  es otra definición (con flete, con cancelados, sin ventana). Justo eso es lo que la capa evita.",
        "",
        "## Resumen",
        "",
        "| Condición | ✅ Igual | 🟡 Cerca | ❌ Distinta | Segundos promedio | Llamadas a herramientas | Costo estimado (USD) |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in CONDICIONES:
        t = tot[c]
        err = f" ({t['err']} corridas con error, fuera del conteo)" if t["err"] else ""
        out.append(f"| {c.replace('_', ' ')}{err} | **{t['igual']} de {t['n']}** | {t['cerca']} | "
                   f"{t['distinta'] + t['sin_respuesta']} | {prom(t['seg']):.0f} | {prom(t['llamadas']):.1f} | "
                   f"{prom(t['costo']):.3f} |")
    out += [
        "",
        "Con 12 preguntas, la diferencia sirve para ver dónde y por qué cambian las respuestas, no",
        "para dar un porcentaje de exactitud con precisión. El costo es el estimado que reporta",
        "Claude Code; con suscripción no se cobra aparte, consume el uso del plan.",
        "",
        "## Pregunta por pregunta",
        "",
        "| Pregunta | Texto | Cifra oficial | Con capa | Sin capa | Trampa que se buscaba |",
        "|---|---|---|---|---|---|",
        *lineas_tabla,
        "",
        "## Qué hizo el agente sin capa cuando no dio la cifra oficial",
        "",
        "Última consulta SQL que ejecutó antes de responder (recortada). La transcripción completa",
        "está en `pruebas/corridas/<pregunta>__sin_capa.jsonl`.",
        "",
    ]
    for q in preguntas:
        f = por.get((q["id"], "sin_capa"))
        if not f or f["estado"] != "ok" or f["nota"] == "igual":
            continue
        sqls = [ll["entrada"].get("sql", "") for ll in f["llamadas"] if isinstance(ll.get("entrada"), dict)]
        ultimo = re.sub(r"\s+", " ", sqls[-1]).strip() if sqls else "(no ejecutó SQL)"
        out += [f"**{q['id']}**: respondió {fmt(f['valor'])}, la cifra oficial es {fmt(f['esperado'])}.",
                "", f"```sql\n{ultimo[:600]}\n```", ""]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- principal
def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="sonnet")
    ap.add_argument("--solo", default="", help="ids separados por coma")
    ap.add_argument("--paralelo", type=int, default=2)
    ap.add_argument("--informe", action="store_true", help="solo rehace RESULTADOS.md")
    a = ap.parse_args()

    preguntas = yaml.safe_load(PREGUNTAS.read_text(encoding="utf-8"))["preguntas"]
    dic = yaml.safe_load((RAIZ / "capa" / "metricas.yml").read_text(encoding="utf-8"))["metricas"]
    unidades = {q["id"]: dic[q["esperado"]["metrica"]]["unidad"] if "metrica" in q["esperado"] else None
                for q in preguntas}
    if a.solo:
        elegidos = set(a.solo.split(","))
        preguntas_correr = [q for q in preguntas if q["id"] in elegidos]
    else:
        preguntas_correr = preguntas
    CORRIDAS.mkdir(exist_ok=True)
    hechas = []
    if RESULTADOS.exists():
        hechas = [json.loads(l) for l in RESULTADOS.read_text(encoding="utf-8").splitlines() if l.strip()]
    hechas = [f for f in hechas if f["estado"] == "ok"]          # las corridas con error se repiten
    claves = {(f["id"], f["condicion"]) for f in hechas}

    if not a.informe:
        motor = Motor()
        objetivos = {q["id"]: esperado(motor, q["esperado"]) for q in preguntas}
        carpeta = Path(tempfile.mkdtemp(prefix="sin_capa_"))       # fuera del proyecto: sin CLAUDE.md
        (carpeta / "mcp.json").write_text(json.dumps({"mcpServers": {"crudo": {
            "command": str(PYTHON), "args": [str(RAIZ / "pruebas" / "servidor_sql_crudo.py")],
            "env": {"PYTHONUTF8": "1"}}}}), encoding="utf-8")
        pendientes = [(q, c) for q in preguntas_correr for c in CONDICIONES if (q["id"], c) not in claves]
        print(f"{len(pendientes)} corridas pendientes, modelo {a.modelo}, {a.paralelo} a la vez", flush=True)

        def tarea(par):
            q, c = par
            f = correr(q, c, a.modelo, carpeta)
            f["esperado"] = objetivos[q["id"]]
            if f["estado"] == "ok":
                f["valor"] = leer_numero(f["respuesta"])
                f["nota"] = clasificar(f["valor"], f["esperado"], unidades[q["id"]], q.get("tol_abs", 0.0))
            with RESULTADOS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(f, ensure_ascii=False, default=str) + "\n")
            marca = f.get("nota") if f["estado"] == "ok" else "ERROR"
            print(f"{q['id']:28} {c:9} {marca!s:6} valor={f.get('valor')} esperado={f['esperado']} "
                  f"{f.get('segundos', '-')}s", flush=True)
            return f

        with ThreadPoolExecutor(max_workers=a.paralelo) as ex:
            list(ex.map(tarea, pendientes))
        hechas = [json.loads(l) for l in RESULTADOS.read_text(encoding="utf-8").splitlines() if l.strip()]

    # La última fila de cada (pregunta, condición) es la que cuenta.
    ultimas = {}
    for f in hechas:
        ultimas[(f["id"], f["condicion"])] = f
    for f in ultimas.values():                                   # la nota se recalcula siempre
        if f["estado"] == "ok":
            q = next(x for x in preguntas if x["id"] == f["id"])
            f["nota"] = clasificar(f.get("valor"), f.get("esperado"), unidades[f["id"]], q.get("tol_abs", 0.0))
    INFORME.write_text(informe(preguntas, list(ultimas.values()), a.modelo), encoding="utf-8")
    print(f"informe: {INFORME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
