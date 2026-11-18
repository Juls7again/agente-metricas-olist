# Hallazgos de la exploración (15-nov-2026)

Todo lo de esta hoja salió de los datos reales de Olist. Nada se sembró. Cada cifra se puede
reproducir con el motor (`capa/motor.py`) y está cubierta por `pruebas/test_motor.py`, salvo
donde se indica "exploratorio".

## Carga

11 tablas, todas cuadran con su CSV: 8.000 leads, 842 cierres, 99.441 pedidos, 112.650 ítems,
103.886 pagos, 99.224 reseñas, 3.095 vendedores.

## Trampas reales encontradas

| Trampa | Qué pasa si se ignora | Dónde quedó resuelta |
|---|---|---|
| Unir ítems con pagos | El GMV sale 4,5 % más alto (14,21 M en vez de 13,59 M) | `v_items` nunca toca pagos |
| Pedidos cancelados o no disponibles | Entran 1.234 pedidos que no son venta | `v_pedidos` los excluye |
| Meses incompletos | 2016 y sep-oct de 2018 tienen entre 1 y 324 pedidos | Meses completos: 2017-01 a 2018-08 |
| Censura en la activación | Parece caer de 56 % (enero) a 6 % (agosto de 2018) y a 0 % después | Ventana fija de 90 días: se mantiene entre 39 % y 51 % |
| Cierres registrados solo desde dic-2017 | Los leads de 2017 muestran tasa de cierre de 1 % a 5 % | Ventana válida de la tasa de cierre: 2018-01 a 2018-05 |
| Muestras pequeñas | 6 cierres de "display" dan 16,7 % de activación | Bandera `fiable` con mínimo por métrica |

## Hallazgos de negocio

### 1. Menos de la mitad de los cierres termina vendiendo
- Activación a 90 días: **43,3 %** de 667 cierres. GMV por cierre a 90 días: **510 BRL**.
- Por tipo de lead:

| Tipo de lead | Cierres | Activación 90 d | GMV por cierre 90 d (BRL) |
|---|---|---|---|
| online_big | 100 | 62,0 % | 1.605 |
| online_medium | 270 | 46,7 % | 343 |
| online_small | 63 | 38,1 % | 326 |
| online_beginner | 43 | 37,2 % | 276 |
| industry | 92 | 34,8 % | 176 |
| offline | 83 | 25,3 % | 88 |

- Por tipo de negocio: revendedor 48,8 % y 671 BRL (459 cierres); fabricante 31,7 % y 161 BRL (199).
- Por origen: paid_search 54,8 % (146 cierres); organic_search 38,9 % (208).
- Límite: el tipo de lead solo existe en los negocios cerrados. Se sabe que venden más, no si cierran más.
- Exploratorio: el GMV de online_big está muy concentrado en un vendedor.

### 2. La tasa de cierre depende mucho del origen
Leads de 2018-01 a 2018-05: organic_search 14,7 %, paid_search 14,8 %, direct_traffic 14,2 %,
social 6,3 %, email 4,0 %. El grupo "unknown" cierra 20,7 %.
En mayo de 2018 la tasa total baja a 10,0 % frente a una base de 13,9 %. Es una alerta real del motor.

### 3. Noviembre de 2017 se sale de lo normal
- GMV: 1.003.862 BRL frente a una base de 535.702.
- Entregas tardías: 14,3 % frente a 3,7 %. Nota de reseñas: 3,95 frente a 4,20.
- Retención neta: 126 %. En diciembre cae a 67 %.

### 4. Febrero y marzo de 2018: las entregas se retrasan
- Entregas tardías: 16,0 % en febrero y **21,4 % en marzo**, frente a una base de 7,5 % (mediana de los
  seis meses anteriores a marzo).
- La nota de reseñas baja a 3,86 y 3,76.
- Los datos no dicen la causa. No afirmar ninguna.

### 5. Los vendedores venden de forma intermitente
- Churn mensual de vendedores entre 21 % y 33 %. Retención bruta entre 55 % y 74 %.
- Cada mes vuelve una parte: el GMV de reactivación va de 8 mil a 79 mil BRL.
- Retención por cohorte: cerca de la mitad sigue vendiendo a los 3 meses.

## Primera prueba de punta a punta

Pregunta hecha por `claude -p` con el servidor MCP: "Los negocios que cerramos, ¿de verdad
terminan vendiendo? ¿A qué tipo de lead le debería dedicar más tiempo el equipo de ventas?"

Respondió en 49 segundos con la definición usada, la tabla por tipo de lead, los criterios de
lectura, una recomendación y cómo medirla. Las cifras coinciden con las de esta hoja.

## Preguntas candidatas para la demo

1. "Los negocios que cerramos, ¿de verdad terminan vendiendo? ¿A quién le dedico más tiempo?"
   (hallazgo 1; termina en una decisión).
2. "¿Por qué parece que la activación se desplomó en los cierres de julio y agosto?"
   (la trampa de censura; muestra que el agente no cae en ella).
3. "¿Qué se salió de lo normal en marzo de 2018?" (hallazgo 4; anomalías y luego la causa por estado).
