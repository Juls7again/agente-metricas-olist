# -*- coding: utf-8 -*-
"""Servidor MCP de control: SQL libre sobre las tablas crudas, sin capa de métricas.

Es la condición "sin capa" de pruebas/evaluar_agente.py. Representa a un asistente que solo
tiene acceso de lectura a la base: no ve el diccionario, ni las vistas, ni las reglas, ni las
trampas conocidas. Tiene las mismas protecciones de solo lectura que la capa.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import duckdb  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

from capa.motor import BD, _PROHIBIDO, _limpio  # noqa: E402

INSTRUCCIONES = """\
Base DuckDB de solo lectura con los datos públicos de Olist (Brasil, 2016-2018), en reales (BRL).
Tablas: marketing_qualified_leads y closed_deals (embudo comercial de vendedores); orders,
order_items, order_payments, order_reviews, customers, sellers, products,
product_category_name_translation y geolocation (pedidos del marketplace).
Puedes consultar information_schema para ver las columnas.
"""

mcp = MCPServer("crudo", instructions=INSTRUCCIONES)
_con = None


def _conexion():
    global _con
    if _con is None:
        _con = duckdb.connect(str(BD), read_only=True)
        _con.execute("SET enable_external_access = false")
        _con.execute("SET lock_configuration = true")
    return _con


@mcp.tool()
def consultar_sql(sql: str, limite: int = 200) -> dict[str, Any]:
    """Ejecuta una consulta SELECT de solo lectura sobre la base y devuelve hasta 500 filas."""
    texto = sql.strip().rstrip(";").strip()
    if ";" in texto or not texto.lower().startswith(("select", "with")) or _PROHIBIDO.search(texto):
        return {"error": "Solo se permite una consulta SELECT de lectura."}
    limite = max(1, min(int(limite), 500))
    try:
        cur = _conexion().execute(f"SELECT * FROM ({texto}) AS t LIMIT {limite + 1}")
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    nombres = [c[0] for c in cur.description]
    datos = cur.fetchall()
    filas = [{n: (v.isoformat() if hasattr(v, "isoformat") else _limpio(v)) for n, v in zip(nombres, r)}
             for r in datos[:limite]]
    return {"filas": filas, "truncado": len(datos) > limite}


if __name__ == "__main__":
    mcp.run("stdio")
