-- =====================================================================
--  Brazilian E-Commerce Public Dataset by Olist
--  MySQL 8.0 schema and import script
--
--  Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
--  Data period: October 2016 - August 2018
--
--  How to run:
--      mysql -u root -p < schema.sql
--
--  Notes:
--    * LOAD DATA LOCAL INFILE requires local_infile = 1 on both the
--      server and the client:
--          SET GLOBAL local_infile = 1;
--          mysql --local-infile=1 -u root -p < schema.sql
--    * Put the six CSV files in a `data/` folder next to this script.
--    * All six files come from the original Olist dataset; no rows are
--      added or removed, and every foreign key is verified below.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS olist
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE olist;

-- Drop in dependency order so the script can be re-run safely.
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS order_payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS customers;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- Dimension tables
-- ---------------------------------------------------------------------
CREATE TABLE customers (
    customer_id              VARCHAR(32)  NOT NULL,
    customer_unique_id       VARCHAR(32)  NOT NULL,
    customer_zip_code_prefix VARCHAR(10)           ,
    customer_city            VARCHAR(100)          ,
    customer_state           VARCHAR(5)            ,
    PRIMARY KEY (customer_id)
) ENGINE = InnoDB;

CREATE TABLE sellers (
    seller_id              VARCHAR(32) NOT NULL,
    seller_zip_code_prefix VARCHAR(10)          ,
    seller_city            VARCHAR(100)         ,
    seller_state           VARCHAR(5)           ,
    PRIMARY KEY (seller_id)
) ENGINE = InnoDB;

CREATE TABLE products (
    product_id                 VARCHAR(32) NOT NULL,
    product_category_name      VARCHAR(100)         ,
    product_name_lenght        INT                  ,
    product_description_lenght INT                  ,
    product_photos_qty         INT                  ,
    product_weight_g           DECIMAL(10,2)        ,
    product_length_cm          DECIMAL(10,2)        ,
    product_height_cm          DECIMAL(10,2)        ,
    product_width_cm           DECIMAL(10,2)        ,
    PRIMARY KEY (product_id)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Fact tables
-- ---------------------------------------------------------------------
CREATE TABLE orders (
    order_id                         VARCHAR(32) NOT NULL,
    customer_id                      VARCHAR(32) NOT NULL,
    order_status                     VARCHAR(20)          ,
    order_purchase_timestamp         DATETIME             ,
    order_approved_at                DATETIME             ,
    order_delivered_carrier_date     DATETIME             ,
    order_delivered_customer_date    DATETIME             ,
    order_estimated_delivery_date    DATETIME             ,
    PRIMARY KEY (order_id),
    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
) ENGINE = InnoDB;

CREATE TABLE order_items (
    order_id             VARCHAR(32) NOT NULL,
    order_item_id        INT         NOT NULL,
    product_id           VARCHAR(32) NOT NULL,
    seller_id            VARCHAR(32) NOT NULL,
    shipping_limit_date  DATETIME             ,
    price                DECIMAL(10,2)        ,
    freight_value        DECIMAL(10,2)        ,
    PRIMARY KEY (order_id, order_item_id),
    CONSTRAINT fk_items_order
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
    CONSTRAINT fk_items_product
        FOREIGN KEY (product_id) REFERENCES products (product_id),
    CONSTRAINT fk_items_seller
        FOREIGN KEY (seller_id) REFERENCES sellers (seller_id)
) ENGINE = InnoDB;

CREATE TABLE order_payments (
    order_id             VARCHAR(32) NOT NULL,
    payment_sequential   INT         NOT NULL,
    payment_type         VARCHAR(20)          ,
    payment_installments INT                  ,
    payment_value        DECIMAL(10,2)        ,
    PRIMARY KEY (order_id, payment_sequential),
    CONSTRAINT fk_payments_order
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- Import the six CSV files
-- ---------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'data/olist_customers_dataset.csv'
INTO TABLE customers
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/olist_sellers_dataset.csv'
INTO TABLE sellers
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/olist_products_dataset.csv'
INTO TABLE products
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/olist_orders_dataset.csv'
INTO TABLE orders
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/olist_order_items_dataset.csv'
INTO TABLE order_items
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/olist_order_payments_dataset.csv'
INTO TABLE order_payments
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

-- ---------------------------------------------------------------------
-- Row-count checks (expected values from the source files)
-- ---------------------------------------------------------------------
SELECT 'customers' AS table_name, COUNT(*) AS rows_loaded FROM customers
UNION ALL SELECT 'sellers', COUNT(*) FROM sellers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'order_payments', COUNT(*) FROM order_payments;

-- Expected:
--   customers       99,441
--   sellers          3,095
--   products        32,951
--   orders          99,441
--   order_items    112,650
--   order_payments 103,886

-- ---------------------------------------------------------------------
-- Referential-integrity checks (all should return 0)
-- ---------------------------------------------------------------------
SELECT 'orders without customer' AS check_name, COUNT(*) AS bad_rows
FROM orders o LEFT JOIN customers c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL
UNION ALL
SELECT 'items without order', COUNT(*)
FROM order_items oi LEFT JOIN orders o ON o.order_id = oi.order_id
WHERE o.order_id IS NULL
UNION ALL
SELECT 'items without product', COUNT(*)
FROM order_items oi LEFT JOIN products p ON p.product_id = oi.product_id
WHERE p.product_id IS NULL
UNION ALL
SELECT 'items without seller', COUNT(*)
FROM order_items oi LEFT JOIN sellers s ON s.seller_id = oi.seller_id
WHERE s.seller_id IS NULL
UNION ALL
SELECT 'payments without order', COUNT(*)
FROM order_payments op LEFT JOIN orders o ON o.order_id = op.order_id
WHERE o.order_id IS NULL;
