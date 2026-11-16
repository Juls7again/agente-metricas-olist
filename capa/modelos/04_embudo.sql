-- Embudo comercial. Dos granos:
--   v_leads    un renglón por lead calificado; el mes es el del primer contacto
--   v_cierres  un renglón por negocio cerrado; el mes es el del cierre
-- La muestra de leads cubre primeros contactos de jun-2017 a may-2018.
CREATE OR REPLACE TEMP VIEW v_leads AS
SELECT
    m.mql_id,
    date_trunc('month', m.first_contact_date)::DATE AS mes,
    coalesce(m.origin, 'sin_dato')                  AS origen,
    m.landing_page_id                               AS landing,
    (d.mql_id IS NOT NULL)                          AS cerrado
FROM marketing_qualified_leads m
LEFT JOIN closed_deals d USING (mql_id);

-- Activación con ventana fija de 90 días.
-- Los pedidos terminan el 2018-08-31. Un cierre de julio tuvo menos tiempo para vender que
-- uno de enero; compararlos sin ventana hace ver una caída que no existe (sesgo de censura).
-- Regla: solo se miden los cierres con 90 días completos de observación, y solo cuentan
-- las ventas de esos 90 días.
CREATE OR REPLACE TEMP VIEW v_cierres AS
WITH ventas AS (
    SELECT i.seller_id, p.fecha_compra, i.precio
    FROM v_items i JOIN v_pedidos p USING (order_id)
),
por_vendedor AS (
    SELECT d.seller_id,
        min(v.fecha_compra) AS primera_venta,
        sum(v.precio)       AS gmv_total,
        sum(v.precio) FILTER (WHERE v.fecha_compra < d.won_date + INTERVAL 90 DAY) AS gmv_90d,
        count(*)      FILTER (WHERE v.fecha_compra < d.won_date + INTERVAL 90 DAY) AS items_90d
    FROM closed_deals d
    JOIN ventas v USING (seller_id)
    GROUP BY 1
)
SELECT
    d.mql_id,
    d.seller_id,
    date_trunc('month', d.won_date)::DATE                    AS mes,
    d.won_date                                               AS fecha_cierre,
    coalesce(m.origin, 'sin_dato')                           AS origen,
    coalesce(d.business_segment, 'sin_dato')                 AS segmento,
    coalesce(d.lead_type, 'sin_dato')                        AS tipo_lead,
    coalesce(d.business_type, 'sin_dato')                    AS tipo_negocio,
    d.sdr_id,
    d.sr_id,
    datediff('day', m.first_contact_date, d.won_date::DATE)  AS dias_cierre,
    v.primera_venta,
    datediff('day', d.won_date::DATE, v.primera_venta::DATE) AS dias_primera_venta,
    (d.won_date + INTERVAL 90 DAY <= TIMESTAMP '2018-09-01 00:00:00') AS observable_90d,
    (coalesce(v.items_90d, 0) > 0)                           AS activado_90d,
    coalesce(v.gmv_90d, 0)                                   AS gmv_90d,
    coalesce(v.gmv_total, 0)                                 AS gmv_total
FROM closed_deals d
JOIN marketing_qualified_leads m USING (mql_id)
LEFT JOIN por_vendedor v USING (seller_id);
