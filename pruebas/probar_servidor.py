# -*- coding: utf-8 -*-
"""Arranca el servidor MCP como lo haría un asistente y llama a cada herramienta una vez.

Uso: .venv/Scripts/python.exe pruebas/probar_servidor.py
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent

LLAMADAS = [
    ("listar_metricas", {}),
    ("definir_metrica", {"nombre": "tasa_activacion_90d"}),
    ("consultar_metrica", {"metrica": "gmv", "desde": "2018-03", "hasta": "2018-03", "por_mes": False}),
    ("consultar_metrica", {"metrica": "mrr"}),
    ("descomponer_cambio", {"metrica": "gmv", "mes_base": "2017-10", "mes_comparado": "2017-11",
                            "dimension": "estado_vendedor"}),
    ("detectar_anomalias", {"mes": "2018-03"}),
    ("sql_exploratorio", {"sql": "select count(*) n from orders"}),
    ("sql_exploratorio", {"sql": "drop table orders"}),
]


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(RAIZ / "servidor_mcp.py")],
                                   env={"PYTHONUTF8": "1"})
    async with stdio_client(params) as (lectura, escritura):
        async with ClientSession(lectura, escritura) as sesion:
            await sesion.initialize()
            herramientas = (await sesion.list_tools()).tools
            print("herramientas:", [h.name for h in herramientas])
            for nombre, args in LLAMADAS:
                r = await sesion.call_tool(nombre, args)
                texto = r.content[0].text if r.content else ""
                try:
                    dato = json.loads(texto)
                    resumen = {k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} {len(v)}>")
                               for k, v in dato.items()}
                except Exception:  # noqa: BLE001
                    resumen = texto[:200]
                print(f"\n{nombre}({args})\n  -> {str(resumen)[:420]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
