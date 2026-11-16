-- Cohortes de vendedores por mes de primera venta.
-- Un renglón por vendedor y por cada mes transcurrido (k) que ya se puede observar.
-- activo = vendió algo en ese mes. k = 0 es el mes de la primera venta (siempre activo).
CREATE OR REPLACE TEMP VIEW v_cohortes AS
WITH primera AS (
    SELECT seller_id, min(mes) AS mes_cohorte FROM v_gmv_vendedor_mes GROUP BY 1
),
malla AS (
    SELECT p.seller_id, p.mes_cohorte, k::INTEGER AS meses_desde_primera_venta,
           (p.mes_cohorte + to_months(k::INTEGER))::DATE AS mes_observado
    FROM primera p,
         generate_series(0, datediff('month', p.mes_cohorte, DATE '2018-08-01')) g(k)
)
SELECT
    m.seller_id,
    m.mes_cohorte AS mes,
    m.meses_desde_primera_venta,
    (g.seller_id IS NOT NULL) AS activo,
    s.seller_state AS estado_vendedor
FROM malla m
LEFT JOIN v_gmv_vendedor_mes g ON g.seller_id = m.seller_id AND g.mes = m.mes_observado
LEFT JOIN sellers s ON s.seller_id = m.seller_id;
