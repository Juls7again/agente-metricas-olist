-- Movimientos de GMV: un renglón por vendedor y mes en que pasó algo.
-- Cada vendedor se compara contra su propio mes anterior:
--   nuevo         no vendía el mes anterior y nunca había vendido
--   reactivacion  no vendía el mes anterior pero sí antes
--   expansion     vendía y vendió más
--   contraccion   vendía y vendió menos
--   baja          vendía y este mes no vendió nada
-- delta = GMV del mes − GMV del mes anterior. La suma de los delta de un mes es
-- exactamente el cambio del GMV total (prueba de conciliación).
-- El calendario llega hasta el último mes completo (2018-08).
CREATE OR REPLACE TEMP VIEW v_mov AS
WITH calendario AS (
    SELECT m::DATE AS mes
    FROM generate_series(
        (SELECT min(mes) FROM v_gmv_vendedor_mes),
        DATE '2018-08-01',
        INTERVAL 1 MONTH) g(m)
),
vendedores AS (SELECT DISTINCT seller_id FROM v_gmv_vendedor_mes),
malla AS (
    SELECT v.seller_id, c.mes, coalesce(g.gmv, 0) AS gmv
    FROM vendedores v
    CROSS JOIN calendario c
    LEFT JOIN v_gmv_vendedor_mes g ON g.seller_id = v.seller_id AND g.mes = c.mes
),
con_previo AS (
    SELECT *,
        coalesce(lag(gmv) OVER w, 0) AS gmv_previo,
        coalesce(sum(gmv) OVER (PARTITION BY seller_id ORDER BY mes
                                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS gmv_historico
    FROM malla
    WINDOW w AS (PARTITION BY seller_id ORDER BY mes)
)
SELECT
    c.seller_id,
    c.mes,
    c.gmv,
    c.gmv_previo,
    c.gmv - c.gmv_previo AS delta,
    CASE
        WHEN c.gmv_previo = 0 AND c.gmv_historico = 0 THEN 'nuevo'
        WHEN c.gmv_previo = 0                         THEN 'reactivacion'
        WHEN c.gmv = 0                                THEN 'baja'
        WHEN c.gmv > c.gmv_previo                     THEN 'expansion'
        WHEN c.gmv < c.gmv_previo                     THEN 'contraccion'
        ELSE 'igual'
    END AS tipo,
    s.seller_state AS estado_vendedor,
    (d.seller_id IS NOT NULL) AS del_embudo,
    coalesce(d.lead_type,
             CASE WHEN d.seller_id IS NULL THEN 'fuera_del_embudo' ELSE 'sin_dato' END) AS tipo_lead
FROM con_previo c
LEFT JOIN sellers s USING (seller_id)
LEFT JOIN closed_deals d ON d.seller_id = c.seller_id
WHERE NOT (c.gmv = 0 AND c.gmv_previo = 0);
