-- =====================================================================
--  Olist Brazilian E-Commerce — 8 business questions
--  MySQL 8.0
--
--  Run after schema.sql:
--      mysql --local-infile=1 -u root -p olist < queries.sql
--
--  Conventions:
--    * "Revenue" = item price only (freight excluded), delivered orders.
--    * Cancelled, unavailable and undelivered orders are excluded.
--    * Currency is Brazilian reais (R$).
--  The expected output of every query is in expected_results.md.
-- =====================================================================

USE olist;

-- ---------------------------------------------------------------------
-- Q1. How much revenue and how many delivered orders are there?
-- ---------------------------------------------------------------------
SELECT COUNT(DISTINCT o.order_id)                                AS delivered_orders,
       ROUND(SUM(oi.price), 2)                                   AS revenue,
       ROUND(SUM(oi.price) / COUNT(DISTINCT o.order_id), 2)      AS avg_order_value,
       ROUND(AVG(oi.price), 2)                                   AS avg_item_price
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered';

-- Finding: 96,478 delivered orders and R$13.22M of revenue. The average
-- order is worth R$137 and the average item R$119.80.

-- ---------------------------------------------------------------------
-- Q2. Which product categories bring in the most revenue?
-- ---------------------------------------------------------------------
WITH category_revenue AS (
    SELECT p.product_category_name AS category,
           COUNT(*)                AS items_sold,
           SUM(oi.price)           AS revenue
    FROM order_items oi
    JOIN orders   o ON o.order_id  = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    WHERE o.order_status = 'delivered'
    GROUP BY p.product_category_name
)
SELECT category,
       items_sold,
       ROUND(revenue, 2)                                   AS revenue,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 2)    AS pct_of_revenue,
       ROUND(revenue / items_sold, 2)                      AS avg_item_price
FROM category_revenue
ORDER BY revenue DESC
LIMIT 10;

-- Finding: the top 10 of 73 categories bring in 63.2% of revenue.
-- Health and beauty is first (R$1.23M). Watches and gifts is second with
-- only 5,859 items because each item sells for about R$199, against R$93
-- for bed, bath and table (third, 10,953 items).

-- ---------------------------------------------------------------------
-- Q3. How did revenue grow month over month?
-- ---------------------------------------------------------------------
WITH monthly AS (
    SELECT DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS order_month,
           SUM(oi.price)                                    AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= '2017-01-01'
    GROUP BY order_month
)
SELECT order_month,
       ROUND(revenue, 2)                                         AS revenue,
       ROUND(LAG(revenue) OVER (ORDER BY order_month), 2)        AS previous_month_revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month))
                   / LAG(revenue) OVER (ORDER BY order_month), 1) AS mom_growth_pct
FROM monthly
ORDER BY order_month;

-- Finding: revenue jumped 52.4% in November 2017, then fell 26.5% in
-- December. One day explains it: 24 November 2017 (Black Friday) had
-- 1,147 orders, against a 243-order daily average for the month.

-- ---------------------------------------------------------------------
-- Q4. How does delivery performance vary by customer state?
-- (states with at least 100 delivered orders)
-- ---------------------------------------------------------------------
SELECT c.customer_state AS state,
       COUNT(*)         AS orders,
       ROUND(AVG(DATEDIFF(o.order_delivered_customer_date,
                          o.order_purchase_timestamp)), 1) AS avg_days,
       ROUND(100.0 * SUM(o.order_delivered_customer_date >
                          o.order_estimated_delivery_date)
                   / COUNT(*), 1)                             AS pct_late
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
HAVING COUNT(*) >= 100
ORDER BY avg_days DESC;

-- Finding: the average delivery takes 12.6 days and 8.1% of orders are
-- late. São Paulo averages 8.8 days and 5.9% late; Alagoas takes 24.5
-- days and is late 23.9% of the time, the worst of the larger states.

-- ---------------------------------------------------------------------
-- Q5. Is shipping faster and cheaper inside the same state?
-- ---------------------------------------------------------------------
WITH shipping AS (
    SELECT CASE WHEN s.seller_state = c.customer_state
                THEN 'Same state' ELSE 'Different state' END AS shipping_type,
           DATEDIFF(o.order_delivered_customer_date,
                    o.order_purchase_timestamp)             AS days,
           (o.order_delivered_customer_date >
            o.order_estimated_delivery_date)               AS is_late,
           oi.freight_value,
           oi.price
    FROM order_items oi
    JOIN orders    o ON o.order_id   = oi.order_id
    JOIN sellers   s ON s.seller_id  = oi.seller_id
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
)
SELECT shipping_type,
       COUNT(*)                                              AS items,
       ROUND(AVG(days), 1)                                   AS avg_days,
       ROUND(100.0 * SUM(is_late) / COUNT(*), 1)             AS pct_late,
       ROUND(AVG(freight_value), 2)                          AS avg_freight,
       ROUND(100.0 * SUM(freight_value) / SUM(price), 1)     AS freight_pct_of_price
FROM shipping
GROUP BY shipping_type
ORDER BY shipping_type;

-- Finding: same-state items arrive in 7.9 days against 15.0 days across
-- states, are late less often (6.0% against 9.0%) and cost less to ship
-- (R$13.42 against R$23.64, or 13.0% of the price against 18.3%).
-- Only 36.2% of items travel within their own state.

-- ---------------------------------------------------------------------
-- Q6. How often do customers come back?
-- ---------------------------------------------------------------------
WITH orders_per_customer AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS order_count
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
),
buckets AS (
    SELECT CASE WHEN order_count = 1 THEN '1 order'
                WHEN order_count = 2 THEN '2 orders'
                ELSE '3+ orders' END AS repeat_bucket,
           COUNT(*)                  AS customers
    FROM orders_per_customer
    GROUP BY 1
)
SELECT repeat_bucket,
       customers,
       ROUND(100.0 * customers / SUM(customers) OVER (), 1) AS pct_of_customers
FROM buckets
ORDER BY CASE repeat_bucket WHEN '1 order' THEN 1 WHEN '2 orders' THEN 2 ELSE 3 END;

-- Finding: 97.0% of customers ordered once, 2.8% twice and 0.2% three or
-- more times. Repeat purchase is the clearest growth opportunity.

-- ---------------------------------------------------------------------
-- Q7. Who are the top 10 sellers by revenue, and how concentrated is it?
-- ---------------------------------------------------------------------
SELECT RANK() OVER (ORDER BY SUM(oi.price) DESC)                      AS revenue_rank,
       s.seller_id,
       s.seller_state,
       COUNT(DISTINCT oi.order_id)                                    AS orders,
       ROUND(SUM(oi.price), 2)                                        AS revenue,
       ROUND(100.0 * SUM(oi.price) / SUM(SUM(oi.price)) OVER (), 2)   AS pct_of_revenue
FROM order_items oi
JOIN orders  o ON o.order_id  = oi.order_id
JOIN sellers s ON s.seller_id = oi.seller_id
WHERE o.order_status = 'delivered'
GROUP BY s.seller_id, s.seller_state
ORDER BY revenue_rank
LIMIT 10;

-- Finding: the top 10 sellers together make up only 13.3% of revenue and
-- none is above 1.72%, so the marketplace does not depend on a few
-- sellers. Nine of the ten are in São Paulo state.

-- ---------------------------------------------------------------------
-- Q8. How do customers pay?
-- ---------------------------------------------------------------------
WITH payment_totals AS (
    SELECT p.payment_type,
           COUNT(*)                AS payments,
           SUM(p.payment_value)    AS value,
           AVG(p.payment_installments) AS avg_installments
    FROM order_payments p
    JOIN orders o ON o.order_id = p.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY p.payment_type
)
SELECT payment_type,
       payments,
       ROUND(value, 2)                                  AS value,
       ROUND(100.0 * value / SUM(value) OVER (), 2)     AS pct_of_value,
       ROUND(avg_installments, 1)                       AS avg_installments
FROM payment_totals
ORDER BY value DESC;

-- Finding: credit cards account for 78.5% of payment value, with an
-- average of 3.5 installments. Boleto is next at 18.0%, then vouchers
-- (2.2%) and debit cards (1.4%).
