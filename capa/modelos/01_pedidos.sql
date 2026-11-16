-- Pedidos válidos: un renglón por pedido.
-- Convención: un pedido cancelado o no disponible no es venta. Se excluyen aquí, una sola vez,
-- para que ninguna métrica tenga que acordarse de hacerlo.
CREATE OR REPLACE TEMP VIEW v_pedidos AS
SELECT
    o.order_id,
    date_trunc('month', o.order_purchase_timestamp)::DATE               AS mes,
    o.order_purchase_timestamp                                          AS fecha_compra,
    o.order_status                                                      AS estado_pedido,
    c.customer_state                                                    AS estado_cliente,
    (o.order_delivered_customer_date IS NOT NULL)                       AS entregado,
    (o.order_delivered_customer_date > o.order_estimated_delivery_date) AS tarde,
    r.nota
FROM orders o
LEFT JOIN customers c USING (customer_id)
-- Un pedido puede tener varias reseñas: se promedian antes de unir para no duplicar pedidos.
LEFT JOIN (SELECT order_id, avg(review_score) AS nota FROM order_reviews GROUP BY 1) r USING (order_id)
WHERE o.order_status NOT IN ('canceled', 'unavailable');
