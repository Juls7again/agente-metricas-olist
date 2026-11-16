-- Ítems vendidos: un renglón por ítem de un pedido válido. Es el grano del GMV.
-- GMV = precio del ítem. No incluye flete. NUNCA se une con order_payments:
-- un pedido tiene varios pagos y la unión duplica ítems (infla el GMV 4,5 %).
CREATE OR REPLACE TEMP VIEW v_items AS
SELECT
    i.order_id,
    i.seller_id,
    p.mes,
    i.price                                               AS precio,
    s.seller_state                                        AS estado_vendedor,
    coalesce(t.product_category_name_english, 'sin_dato') AS categoria,
    (d.seller_id IS NOT NULL)                             AS del_embudo,
    coalesce(d.lead_type,
             CASE WHEN d.seller_id IS NULL THEN 'fuera_del_embudo' ELSE 'sin_dato' END) AS tipo_lead
FROM order_items i
JOIN v_pedidos p USING (order_id)
LEFT JOIN sellers s USING (seller_id)
LEFT JOIN products pr USING (product_id)
LEFT JOIN product_category_name_translation t ON t.product_category_name = pr.product_category_name
LEFT JOIN closed_deals d ON d.seller_id = i.seller_id;

-- GMV por vendedor y mes: base de retención, movimientos y cohortes.
CREATE OR REPLACE TEMP VIEW v_gmv_vendedor_mes AS
SELECT seller_id, mes, sum(precio) AS gmv, count(DISTINCT order_id) AS pedidos
FROM v_items
GROUP BY 1, 2;
