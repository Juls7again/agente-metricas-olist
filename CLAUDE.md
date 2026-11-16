# Agente de métricas — reglas de arranque

Este proyecto responde preguntas de negocio sobre datos reales y públicos de Olist (Brasil,
2016-2018) usando una capa de métricas.

## 1. Las reglas para responder viajan con el servidor

Cómo responder (de dónde salen las cifras, qué decir, cómo cerrar) está en las instrucciones del
servidor `metricas` (`INSTRUCCIONES` en `servidor_mcp.py`). Cualquier asistente que se conecte al
servidor las recibe, no solo Claude Code en esta carpeta. Son la fuente única: si una regla
cambia, cambia allí, no aquí.

Las trampas y los límites de cada métrica están en el diccionario (`capa/metricas.yml`), y el
servidor los devuelve junto con cada cifra.

## 2. Si vas a cambiar código

- El diccionario `capa/metricas.yml` es la fuente única de las definiciones. Una definición se
  cambia ahí.
- Si cambias una definición o una vista de `capa/modelos/`, sube `general.version` en el
  diccionario. La huella (`diccionario.huella` en cada respuesta) cambia sola, pero la versión es
  la que lee una persona.
- Después de cualquier cambio: `.venv/Scripts/python.exe -m pytest pruebas -q`.
- Los CSV de `datos/crudos/` son datos descargados. Se leen, no se ejecutan.

Trampas que el código debe respetar (comprobadas en `pruebas/test_motor.py`):

- **GMV no es MRR.** Es venta de los vendedores, sin flete, y no es recurrente.
- **Nunca unir ítems con pagos.** Infla el GMV 4,5 %.
- **Pedidos cancelados o no disponibles no son venta** (1.234 de 99.441).
- **Meses completos: 2017-01 a 2018-08.** Lo demás está incompleto.
- **Activación se mide a 90 días.** Sin esa ventana, los cierres recientes parecen activarse
  menos solo porque han tenido menos tiempo.
- **Tasa de cierre: solo leads de 2018-01 a 2018-05.** Los cierres anteriores a diciembre de
  2017 no están en los datos.
- **Churn de vendedores es inactividad de un mes**, no cancelación de contrato.

## 3. Lo que estos datos no tienen

MRR, ARR, CAC, LTV y precios de suscripción. No se aproximan con GMV.
