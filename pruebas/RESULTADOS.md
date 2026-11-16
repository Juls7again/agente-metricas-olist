# Preguntas de control: con capa y sin capa

Corrida con Claude Code (`claude -p`), modelo `sonnet`. Generado por `pruebas/evaluar_agente.py`.

- **Con capa:** el agente solo tiene las herramientas del servidor de métricas.
- **Sin capa:** el agente solo tiene SQL de lectura sobre las tablas crudas, desde una carpeta
  vacía: no ve el diccionario, las vistas, las reglas ni las trampas conocidas.
- Misma pregunta, mismo modelo y misma instrucción de formato en las dos condiciones.
- La cifra oficial es la del diccionario y la calcula el motor. Cada respuesta se clasifica:
  ✅ **igual** a la cifra oficial (salvo redondeo), 🟡 **cerca** (a menos de 0,5 %, pero otra
  cifra) o ❌ **distinta**. Una cifra distinta no siempre es un error de cálculo: muchas veces
  es otra definición (con flete, con cancelados, sin ventana). Justo eso es lo que la capa evita.

## Resumen

| Condición | ✅ Igual | 🟡 Cerca | ❌ Distinta | Segundos promedio | Llamadas a herramientas | Costo estimado (USD) |
|---|---|---|---|---|---|---|
| con capa | **12 de 12** | 0 | 0 | 6 | 2.0 | 0.036 |
| sin capa | **4 de 12** | 1 | 7 | 5 | 1.8 | 0.020 |

Con 12 preguntas, la diferencia sirve para ver dónde y por qué cambian las respuestas, no
para dar un porcentaje de exactitud con precisión. El costo es el estimado que reporta
Claude Code; con suscripción no se cobra aparte, consume el uso del plan.

## Pregunta por pregunta

| Pregunta | Texto | Cifra oficial | Con capa | Sin capa | Trampa que se buscaba |
|---|---|---|---|---|---|
| q01_gmv | ¿Cuánto vendieron en total los vendedores de Olist en marzo de 2018, en reales? | 981.051,06 | ✅ 981.051,06 | 🟡 983.213,44 | incluir flete o pagos, o contar pedidos cancelados |
| q02_pedidos | ¿Cuántos pedidos se hicieron en noviembre de 2017? | 7.421 | ✅ 7.421 | ❌ 7.544 | contar pedidos cancelados, no disponibles o sin ítems |
| q03_ticket | ¿Cuál fue el ticket promedio de los pedidos de mayo de 2018, en reales? | 145,31 | ✅ 145,31 | ❌ 167,90 | incluir flete, dividir por ítems en vez de pedidos o unir con pagos |
| q04_activacion | De los negocios que cerramos en el embudo comercial, ¿qué porcentaje hizo al menos una venta en sus primeros 90 días después del cierre? | 43,33 | ✅ 43,33 | ❌ 38,48 | censura (contar cierres que todavía no tienen 90 días de observación) |
| q05_activacion_online_big | De los negocios cerrados con tipo de lead online_big, ¿qué porcentaje vendió algo en sus primeros 90 días después del cierre? | 62 | ✅ 62 | ❌ 54,76 | censura |
| q06_cierre_paid_search | ¿Qué porcentaje de los leads que llegaron por paid_search terminó cerrando negocio? | 14,81 | ✅ 14,81 | ❌ 12,30 | incluir leads de 2017, cuyos cierres no están registrados |
| q07_cierre_mayo | De los leads que entraron en mayo de 2018, ¿qué porcentaje terminó cerrando negocio? | 9,98 | ✅ 9,98 | ✅ 9,98 | ninguna conocida (control) |
| q08_entregas_tardias | ¿Qué porcentaje de los pedidos comprados en marzo de 2018 llegó después de la fecha de entrega estimada? | 21,36 | ✅ 21,36 | ✅ 21,36 | usar como base todos los pedidos y no solo los entregados |
| q09_nota | ¿Cuál fue la nota promedio de las reseñas de los pedidos comprados en febrero de 2018? | 3,86 | ✅ 3,86 | ❌ 3,83 | contar dos veces los pedidos con varias reseñas, o incluir cancelados |
| q10_churn | ¿Qué porcentaje de los vendedores que vendieron en noviembre de 2017 no vendió nada en diciembre de 2017? | 30,42 | ✅ 30,42 | ❌ 30,67 | contar ventas de pedidos cancelados |
| q11_retencion_neta | ¿Cuál fue la retención neta de GMV de noviembre de 2017? Es decir: de lo que vendían en octubre los vendedores que estaban activos, ¿qué porcentaje vendieron esos mismos vendedores en noviembre? | 126 | ✅ 126 | ✅ 126 | incluir flete o cancelados, o mezclar vendedores nuevos |
| q12_mrr | ¿Cuál fue el MRR de agosto de 2018? | NO_DISPONIBLE | ✅ NO_DISPONIBLE | ✅ NO_DISPONIBLE | llamar MRR al GMV (estos datos no tienen suscripciones) |

## Qué hizo el agente sin capa cuando no dio la cifra oficial

Última consulta SQL que ejecutó antes de responder (recortada). La transcripción completa
está en `pruebas/corridas/<pregunta>__sin_capa.jsonl`.

**q01_gmv**: respondió 983.213,44, la cifra oficial es 981.051,06.

```sql
select order_status, count(*), sum(price) from orders o join order_items i using(order_id) where cast(order_purchase_timestamp as timestamp)>=timestamp '2018-03-01' and cast(order_purchase_timestamp as timestamp)<timestamp '2018-04-01' group by 1
```

**q02_pedidos**: respondió 7.544, la cifra oficial es 7.421.

```sql
select count(*), count(distinct order_id) from orders where order_purchase_timestamp >= '2017-11-01' and order_purchase_timestamp < '2017-12-01'
```

**q03_ticket**: respondió 167,90, la cifra oficial es 145,31.

```sql
with o as (select order_id, order_status from orders where order_purchase_timestamp >= '2018-05-01' and order_purchase_timestamp < '2018-06-01'), p as (select order_id, sum(payment_value) v from order_payments group by 1), i as (select order_id, sum(price) pr, sum(price+freight_value) pf from order_items group by 1) select count(*) n, avg(p.v) pay, avg(i.pr) price, avg(i.pf) price_freight, avg(case when order_status<>'canceled' then p.v end) pay_nocancel, avg(case when order_status not in ('canceled','unavailable') then p.v end) pay_valid from o left join p using(order_id) left join i using(or
```

**q04_activacion**: respondió 38,48, la cifra oficial es 43,33.

```sql
with d as (select distinct seller_id, won_date from closed_deals), x as (select d.seller_id, d.won_date, count(distinct o.order_id) n, count(distinct case when o.order_status not in ('canceled','unavailable') then o.order_id end) n2 from d left join order_items oi on oi.seller_id=d.seller_id left join orders o on o.order_id=oi.order_id and o.order_purchase_timestamp>=d.won_date and o.order_purchase_timestamp<d.won_date+interval 90 day group by 1,2) select count(*), avg((n>0)::int)*100, avg((n2>0)::int)*100, (select count(*) from closed_deals) from x
```

**q05_activacion_online_big**: respondió 54,76, la cifra oficial es 62.

```sql
select lead_type, count(*) from closed_deals group by 1
```

**q06_cierre_paid_search**: respondió 12,30, la cifra oficial es 14,81.

```sql
select count(distinct m.mql_id) leads, count(distinct c.mql_id) cerrados, 100.0*count(distinct c.mql_id)/count(distinct m.mql_id) pct from marketing_qualified_leads m left join closed_deals c on c.mql_id=m.mql_id where m.origin='paid_search'
```

**q09_nota**: respondió 3,83, la cifra oficial es 3,86.

```sql
select avg(r.review_score), count(*), count(distinct o.order_id) from orders o join order_reviews r using(order_id) where o.order_purchase_timestamp >= '2018-02-01' and o.order_purchase_timestamp < '2018-03-01'
```

**q10_churn**: respondió 30,67, la cifra oficial es 30,42.

```sql
with s as (select oi.seller_id, strftime(o.order_purchase_timestamp::timestamp,'%Y-%m') m from orders o join order_items oi using(order_id) where strftime(o.order_purchase_timestamp::timestamp,'%Y-%m') in ('2017-11','2017-12')) select count(distinct case when m='2017-11' then seller_id end) nov, count(distinct case when m='2017-11' and seller_id not in (select seller_id from s where m='2017-12') then seller_id end) perdidos from s
```

