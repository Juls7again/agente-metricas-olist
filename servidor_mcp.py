# -*- coding: utf-8 -*-
"""Servidor MCP de la capa de métricas.

Expone el diccionario y el motor como herramientas que cualquier asistente compatible con MCP
puede usar (Claude Code, Claude Desktop u otro). El asistente no necesita conocer las tablas:
pide una métrica por su nombre y recibe el número, la muestra, si es fiable, la definición
usada y el SQL ejecutado.

Se lanza solo desde .mcp.json. No imprime nada por la salida estándar: ese canal es del protocolo.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from capa.motor import ErrorDeMetrica, Motor  # noqa: E402

INSTRUCCIONES = """\
Capa de métricas sobre datos reales y públicos de Olist (Brasil, 2016-2018): embudo comercial,
activación, GMV, retención de vendedores y calidad de entrega.

Cómo usarla:
1. Para saber qué existe, llama a listar_metricas. Para entender una métrica, definir_metrica.
2. Toda cifra oficial sale de consultar_metrica. No la recalcules con SQL propio.
3. Al responder, di qué definición usaste y menciona los criterios de lectura que apliquen.
4. Si una fila viene con fiable=false, dilo y no saques conclusiones de ella.
5. Para explicar un cambio, usa descomponer_cambio. Para ver qué se salió de lo normal,
   detectar_anomalias.
6. sql_exploratorio es solo para explorar. Lo que salga de ahí no es una cifra oficial.
Estos datos no tienen MRR, ARR, CAC ni LTV. Si te los piden, dilo; no los aproximes.
"""

mcp = MCPServer("metricas", instructions=INSTRUCCIONES)
_motor: Motor | None = None


def motor() -> Motor:
    global _motor
    if _motor is None:
        _motor = Motor()
    return _motor


def _seguro(fn, *args, **kwargs) -> dict[str, Any]:
    """Los errores de uso vuelven como texto útil para el asistente, no como excepción."""
    try:
        return fn(*args, **kwargs)
    except ErrorDeMetrica as e:
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


@mcp.tool()
def listar_metricas() -> dict[str, Any]:
    """Lista todas las métricas del diccionario, con su definición corta, unidad y dimensiones.

    Úsala primero, antes de elegir una métrica. También devuelve la fuente de los datos, el
    periodo con meses completos y lo que estos datos NO permiten calcular.
    """
    return _seguro(motor().listar)


@mcp.tool()
def definir_metrica(nombre: str) -> dict[str, Any]:
    """Definición completa de una métrica: qué mide, fórmula, dueño, criterios de lectura
    (trampas), con qué no confundirla, su equivalente en SaaS y la expresión SQL que la calcula.

    Úsala cuando el usuario pregunte "¿cómo se define X?" o antes de interpretar un resultado.
    """
    return _seguro(motor().definir, nombre)


@mcp.tool()
def consultar_metrica(
    metrica: str,
    desde: str | None = None,
    hasta: str | None = None,
    dimensiones: list[str] | None = None,
    filtros: dict[str, Any] | None = None,
    por_mes: bool = True,
) -> dict[str, Any]:
    """Calcula una métrica oficial. Es la única fuente válida de cifras.

    Args:
        metrica: nombre exacto, de listar_metricas (por ejemplo "gmv" o "tasa_activacion_90d").
        desde, hasta: meses en formato AAAA-MM. Si se omiten, usa todo el periodo válido.
        dimensiones: columnas por las que abrir el resultado. Solo las que la métrica permite.
        filtros: {dimension: valor} para quedarse con un segmento.
        por_mes: true devuelve una fila por mes; false devuelve un solo valor para todo el periodo.

    Devuelve filas con valor, muestra y fiable, más la definición, los criterios de lectura y el
    SQL ejecutado. fiable=false significa poca muestra o mes fuera de la ventana válida.
    """
    return _seguro(motor().consultar, metrica, desde, hasta, dimensiones, filtros, por_mes)


@mcp.tool()
def descomponer_cambio(metrica: str, mes_base: str, mes_comparado: str, dimension: str) -> dict[str, Any]:
    """Explica el cambio de una métrica entre dos meses, abierto por una dimensión.

    En métricas aditivas (GMV, conteos) dice qué porcentaje del cambio aporta cada segmento.
    En tasas muestra el valor de cada segmento en ambos meses y su muestra.
    Úsala para responder "¿por qué subió o bajó X?". Prueba varias dimensiones antes de concluir.
    """
    return _seguro(motor().descomponer, metrica, mes_base, mes_comparado, dimension)


@mcp.tool()
def detectar_anomalias(mes: str, meses_base: int = 6) -> dict[str, Any]:
    """Revisa las métricas vigiladas de un mes contra la mediana de sus meses anteriores.

    Una métrica alerta solo si se desvía en proporción y además en tamaño absoluto. Devuelve las
    alertas, las que están normales y las que no se pudieron evaluar. Dice qué se salió de lo
    normal, no por qué: para la causa, sigue con descomponer_cambio.
    """
    return _seguro(motor().anomalias, mes, meses_base)


@mcp.tool()
def sql_exploratorio(sql: str, limite: int = 200) -> dict[str, Any]:
    """Ejecuta un SELECT de solo lectura sobre las tablas crudas y las vistas (v_pedidos, v_items,
    v_gmv_vendedor_mes, v_mov, v_leads, v_cierres, v_cohortes). Máximo 500 filas.

    Solo para explorar o revisar un detalle. El resultado NO es una cifra oficial: no aplica las
    definiciones del diccionario. Para cifras, usa consultar_metrica.
    """
    return _seguro(motor().sql_libre, sql, limite)


if __name__ == "__main__":
    mcp.run("stdio")
