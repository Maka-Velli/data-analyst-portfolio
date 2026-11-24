-- =====================================================================
--  Capstone: Global CO2 priorities
--  MySQL 8.0
--
--  Source: Our World in Data — CO2 and Greenhouse Gas Emissions data
--          https://github.com/owid/co2-data
--
--  The CSV has 79 columns. The staging table keeps the 17 that the
--  analysis needs; the rest are skipped with @dummy variables.
--
--  Run:
--      mysql --local-infile=1 -u root -p < capstone_analysis.sql
--
--  Put owid-co2-data.csv in a `data/` folder next to this script.
-- =====================================================================

DROP TABLE IF EXISTS co2_data;

CREATE TABLE co2_data (
    country                      VARCHAR(100),
    year                         INT,
    iso_code                     VARCHAR(8),
    population                   DOUBLE,
    gdp                          DOUBLE,
    co2                          DOUBLE,
    co2_per_capita               DOUBLE,
    co2_per_gdp                  DOUBLE,
    cumulative_co2               DOUBLE,
    share_global_co2             DOUBLE,
    coal_co2                     DOUBLE,
    gas_co2                      DOUBLE,
    oil_co2                      DOUBLE,
    cement_co2                   DOUBLE,
    flaring_co2                  DOUBLE,
    energy_per_capita            DOUBLE,
    primary_energy_consumption   DOUBLE
) ENGINE = InnoDB;

LOAD DATA LOCAL INFILE 'data/owid-co2-data.csv'
INTO TABLE co2_data
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(
    country,
    year,
    iso_code,
    population,
    gdp,
    cement_co2,
    @dummy,
    co2,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    co2_per_capita,
    co2_per_gdp,
    @dummy,
    coal_co2,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    cumulative_co2,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    energy_per_capita,
    @dummy,
    flaring_co2,
    @dummy,
    gas_co2,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    oil_co2,
    @dummy,
    @dummy,
    @dummy,
    primary_energy_consumption,
    @dummy,
    share_global_co2,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy,
    @dummy
);

-- ---------------------------------------------------------------------
-- Q1. How large is global CO2, and how concentrated is it?
-- ---------------------------------------------------------------------
WITH latest AS (
    SELECT country, iso_code, co2
    FROM co2_data
    WHERE year = 2023
      AND iso_code IS NOT NULL
      AND iso_code NOT LIKE 'OWID%'
),
ranked AS (
    SELECT country, co2,
           RANK() OVER (ORDER BY co2 DESC) AS rnk
    FROM latest
)
SELECT ROUND(SUM(co2), 1)                                              AS global_co2_mt,
       ROUND(100.0 * SUM(CASE WHEN rnk <= 3  THEN co2 ELSE 0 END)
                   / SUM(co2), 1)                                     AS top3_share_pct,
       ROUND(100.0 * SUM(CASE WHEN rnk <= 10 THEN co2 ELSE 0 END)
                   / SUM(co2), 1)                                     AS top10_share_pct,
       COUNT(*)                                                        AS countries
FROM ranked;

-- ---------------------------------------------------------------------
-- Q2. Who are the top 15 emitters?
-- ---------------------------------------------------------------------
SELECT country,
       ROUND(co2, 1)                                    AS co2_mt,
       ROUND(co2_per_capita, 2)                         AS co2_per_capita,
       ROUND(100.0 * co2 / SUM(co2) OVER (), 2)         AS pct_of_global
FROM co2_data
WHERE year = 2023
  AND iso_code IS NOT NULL
  AND iso_code NOT LIKE 'OWID%'
ORDER BY co2 DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q3. Who added and who cut emissions between 2013 and 2023?
-- ---------------------------------------------------------------------
WITH y2023 AS (
    SELECT country, iso_code, co2 AS co2_2023
    FROM co2_data
    WHERE year = 2023 AND iso_code IS NOT NULL AND iso_code NOT LIKE 'OWID%'
),
y2013 AS (
    SELECT country, iso_code, co2 AS co2_2013
    FROM co2_data
    WHERE year = 2013 AND iso_code IS NOT NULL AND iso_code NOT LIKE 'OWID%'
)
SELECT y2023.country,
       ROUND(y2023.co2_2023, 1)                                   AS co2_2023_mt,
       ROUND(y2013.co2_2013, 1)                                   AS co2_2013_mt,
       ROUND(y2023.co2_2023 - y2013.co2_2013, 1)                  AS change_mt,
       ROUND(100.0 * (y2023.co2_2023 - y2013.co2_2013)
                   / y2013.co2_2013, 1)                           AS change_pct
FROM y2023
JOIN y2013 ON y2023.iso_code = y2013.iso_code
WHERE y2023.co2_2023 >= 20
ORDER BY change_mt DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q4. Which countries should a climate fund prioritise?
--     Priority score (0-100) among countries emitting >= 100 Mt:
--       40% absolute CO2 + 30% growth 2013-2023
--     + 20% carbon intensity (CO2 per GDP, 2022) + 10% coal share
-- ---------------------------------------------------------------------
WITH latest AS (
    SELECT *
    FROM co2_data
    WHERE year = 2023
      AND iso_code IS NOT NULL
      AND iso_code NOT LIKE 'OWID%'
      AND co2 >= 100
),
base AS (
    SELECT l.country,
           l.co2,
           l.co2 - y.co2                      AS growth_abs,
           100.0 * l.coal_co2 / l.co2        AS coal_share,
           g.co2_per_gdp                     AS co2_per_gdp_2022
    FROM latest l
    LEFT JOIN co2_data g ON g.iso_code = l.iso_code AND g.year = 2022
    LEFT JOIN co2_data y ON y.iso_code = l.iso_code AND y.year = 2013
),
scored AS (
    SELECT country, co2, growth_abs, coal_share, co2_per_gdp_2022,
           100.0 * PERCENT_RANK() OVER (ORDER BY co2)                 AS co2_pct,
           100.0 * PERCENT_RANK() OVER (ORDER BY growth_abs)          AS growth_pct,
           100.0 * PERCENT_RANK() OVER (ORDER BY co2_per_gdp_2022)    AS intensity_pct,
           100.0 * PERCENT_RANK() OVER (ORDER BY coal_share)          AS coal_pct
    FROM base
)
SELECT country,
       ROUND(co2, 1)                AS co2_mt,
       ROUND(growth_abs, 1)         AS growth_mt,
       ROUND(coal_share, 1)         AS coal_share_pct,
       ROUND(co2_per_gdp_2022, 2)   AS co2_per_gdp,
       ROUND(0.40 * co2_pct + 0.30 * growth_pct
             + 0.20 * intensity_pct + 0.10 * coal_pct, 1) AS priority_score
FROM scored
ORDER BY priority_score DESC;

-- ---------------------------------------------------------------------
-- Q5. How do the four country segments compare?
-- ---------------------------------------------------------------------
WITH latest AS (
    SELECT *
    FROM co2_data
    WHERE year = 2023
      AND iso_code IS NOT NULL
      AND iso_code NOT LIKE 'OWID%'
),
growth AS (
    SELECT l.country,
           l.co2,
           l.co2 - y.co2 AS growth_abs,
           CASE
               WHEN l.co2 >= 100 AND l.co2 - y.co2 > 0 THEN 'Growth engine'
               WHEN l.co2 >= 100 AND l.co2 - y.co2 <= 0 THEN 'Managed decline'
               WHEN l.co2 < 100 AND l.co2 - y.co2 > 0 THEN 'Watchlist'
               ELSE 'On track'
           END AS segment
    FROM latest l
    LEFT JOIN co2_data y ON y.iso_code = l.iso_code AND y.year = 2013
),
segment_totals AS (
    SELECT segment,
           COUNT(*)        AS countries,
           SUM(co2)        AS co2_mt,
           SUM(growth_abs) AS net_change_mt
    FROM growth
    GROUP BY segment
)
SELECT segment,
       countries,
       ROUND(co2_mt, 1)                                  AS co2_mt,
       ROUND(100.0 * co2_mt / SUM(co2_mt) OVER (), 1)    AS pct_of_global,
       ROUND(net_change_mt, 1)                           AS net_change_mt
FROM segment_totals
ORDER BY co2_mt DESC;
