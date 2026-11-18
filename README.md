# Agente de métricas sobre datos reales de Olist

Un analista al que se le pregunta en español. Responde con cifras de datos reales, dice qué
definición usó y con qué versión del diccionario, avisa cuando un número no es fiable y termina
en una recomendación con su forma de medirla.

Construido con Claude Code por Julián Martínez Ortiz para el reto del cargo Business Intelligence &
Analytics Partner de Alegra (noviembre de 2026).

## Para quien evalúa

| Lo que pide el reto | Respuesta |
|---|---|
| **Qué problema resuelve** | Un asistente de IA que escribe su propio SQL da cifras con su propia definición: dos personas que preguntan lo mismo reciben números distintos. |
| **Cómo se abordó** | Una capa de métricas con una sola definición de cada una (vistas SQL + diccionario + motor), servida al agente por MCP. El agente pide la métrica; no la calcula. |
| **Herramientas usadas** | Claude Code (para construir y como agente, con Claude Sonnet), MCP, Python, DuckDB, SQL, YAML, pandas, pytest y uv. |
| **Resultado obtenido** | Mismas 12 preguntas de negocio: **12 de 12 con la cifra oficial usando la capa, 4 de 12 sin ella**. 107 pruebas automáticas contra un cálculo aparte en pandas. |
| **Dónde leer más** | [Guía del proyecto en PDF](docs/guia-datos-y-proyecto.pdf) (completa, con la evidencia en el anexo) y [resultados de las preguntas de control](pruebas/RESULTADOS.md). |

Julián tomó las decisiones de producto y de datos (un agente nuevo, datos reales y no simulados,
Olist, la forma de entrega). Claude Code escribió el código, el SQL y las pruebas a partir de
ellas.

## El problema

Cuando un asistente de IA escribe su propio SQL, responde rápido, pero con su propia versión de
cada métrica. Dos personas que preguntan lo mismo pueden recibir dos números distintos, y ninguno
dice qué contó ni qué dejó por fuera: pedidos cancelados, flete, meses incompletos, cierres que
todavía no han tenido tiempo de vender.

Aquí el asistente no inventa la métrica: se la pide a una capa que tiene una sola definición de
cada una. Es la misma que usaría un tablero o un analista.

## Cómo funciona

```
CSV de Olist -> datos/cargar.py -> olist.duckdb -> vistas SQL (capa/modelos)
             -> diccionario (capa/metricas.yml) -> motor (capa/motor.py)
             -> servidor MCP (servidor_mcp.py) -> Claude Code u otro asistente compatible
```

- **Vistas SQL** (`capa/modelos/`): limpian los datos una sola vez. Excluyen pedidos cancelados y
  no disponibles, nunca unen ítems con pagos, fijan la ventana de 90 días de la activación.
- **Diccionario** (`capa/metricas.yml`): 23 métricas de embudo, activación, ingresos, movimientos
  de GMV, retención y calidad. Cada una con definición de negocio, fórmula, dueño, dimensiones
  permitidas, muestra mínima, criterios de lectura, con qué no confundirla y su equivalente en SaaS.
- **Motor** (`capa/motor.py`): valida cada pedido contra el diccionario, arma el SQL con
  parámetros, marca las filas con poca muestra como no fiables y devuelve el número con su
  definición, el SQL ejecutado y la versión de la capa. Abre la base en solo lectura.
- **Servidor MCP** (`servidor_mcp.py`): seis herramientas (`listar_metricas`, `definir_metrica`,
  `consultar_metrica`, `descomponer_cambio`, `detectar_anomalias`, `sql_exploratorio`). Las reglas
  para responder viajan en las instrucciones del servidor, así que las recibe cualquier asistente
  que se conecte.

La guía completa, con diagramas, las trampas de los datos y los hallazgos, está en
`docs/guia-datos-y-proyecto.pdf`.

## Datos

Datos reales, públicos y anonimizados publicados por Olist en Kaggle:

- "Marketing Funnel by Olist": https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist
- "Brazilian E-Commerce Public Dataset by Olist": https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Licencia **CC BY-NC-SA 4.0** (uso no comercial, con atribución a Olist). Los datos no vienen en
este paquete: se descargan con los comandos de abajo.

Estos datos no tienen suscripciones, precios ni gasto de adquisición. Por eso no se calcula MRR,
ARR, CAC ni LTV, y el GMV nunca se llama MRR. La mecánica de cohortes, retención neta y bruta,
churn y expansión sí se muestra, sobre el GMV de los vendedores.

## Cómo correrlo

Requiere Python 3.13, [uv](https://docs.astral.sh/uv/) y Claude Code. Los comandos son para
Windows (Git Bash); en macOS o Linux, `.venv/Scripts/python.exe` es `.venv/bin/python`.

```bash
uv venv .venv
uv pip install -r requirements.txt

# Descarga de los datos (enlace público de Kaggle, sin iniciar sesión)
mkdir -p datos/crudos
curl -L -o datos/crudos/embudo.zip  https://www.kaggle.com/api/v1/datasets/download/olistbr/marketing-funnel-olist
curl -L -o datos/crudos/pedidos.zip https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce

# Carga a DuckDB, con chequeo de filas contra cada CSV
.venv/Scripts/python.exe -I datos/cargar.py datos/crudos datos/olist.duckdb

# Pruebas: cada métrica contra un cálculo aparte en pandas sobre los CSV crudos
.venv/Scripts/python.exe -m pytest pruebas -q

# Llama a las seis herramientas del servidor como lo haría un asistente
.venv/Scripts/python.exe pruebas/probar_servidor.py
```

`.mcp.json` registra el servidor con rutas absolutas de la máquina donde se construyó. En otra
máquina, cambia las dos rutas por las de tu carpeta. Después abre Claude Code en la carpeta del
proyecto (`claude`), aprueba el servidor `metricas` y pregunta, por ejemplo:

> Los negocios que cerramos, ¿de verdad terminan vendiendo? ¿A qué tipo de lead le debería
> dedicar más tiempo el equipo de ventas?

## Cómo se comprobó

- **Carga:** las 11 tablas tienen las mismas filas que sus CSV.
- **107 pruebas** (`pruebas/test_motor.py`): cada métrica contra un cálculo independiente en
  pandas, conciliación mensual de los movimientos de GMV, las trampas documentadas, la seguridad
  del SQL libre, la marca de muestra pequeña y la versión que viaja en cada respuesta.
- **Prueba de mutación:** al quitar a propósito la exclusión de pedidos no disponibles, 12 pruebas
  fallan.
- **Preguntas de control** (`pruebas/evaluar_agente.py`): las mismas 12 preguntas de negocio a
  Claude Code (Sonnet) con la capa y solo con SQL libre sobre las tablas crudas. **Con la capa,
  12 de 12 respuestas dieron la cifra oficial. Sin la capa, 4 de 12**: las demás contaron pedidos
  cancelados, usaron pagos con flete, cayeron en la censura de la activación o incluyeron leads
  de 2017 cuyos cierres no están registrados. Detalle, SQL usado y transcripciones en
  `pruebas/RESULTADOS.md` y `pruebas/corridas/`.

## Estructura

```
capa/metricas.yml         diccionario: fuente única de las definiciones
capa/modelos/*.sql        vistas que limpian los datos
capa/motor.py             motor de consultas, descomposición y anomalías
servidor_mcp.py           servidor MCP con las seis herramientas y las reglas para responder
datos/cargar.py           carga de los CSV a DuckDB
datos/hallazgos.md        lo que mostró la exploración de los datos
pruebas/                  pruebas del motor, prueba del servidor y preguntas de control
docs/                     guía de datos y proyecto (PDF) y el script que la genera
CLAUDE.md                 reglas para quien cambie el código
```

## Límites

- Los leads son una muestra aleatoria de 8.000, no el total.
- Hay pocos cierres por mes. Por eso cada métrica tiene una muestra mínima y marca lo que no es
  fiable.
- `sql_exploratorio` deja mirar las tablas crudas a propósito, solo en lectura y con un tope de
  500 filas. Cada respuesta avisa que no es una cifra oficial.
- La capa corre en local. Para un equipo, el diccionario iría en un repositorio con revisión de
  cambios, los datos en el warehouse y el servidor desplegado con una URL compartida.
