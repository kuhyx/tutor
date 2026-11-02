# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pivot drills: conditional aggregation, key-value to columns, unpivot."""

from __future__ import annotations

from typing import Final

from tutor.sql_pack.spec import Spec, predict, write

SPECS: Final[tuple[Spec, ...]] = (
    write(
        "pivot",
        "Count orders per status as columns",
        "`shop_orders` has one row per order.\n\n"
        "Output columns (no header): `customer`, `new`, `paid`, `shipped` "
        "(how many orders the customer has in each status).\n\n"
        "- A status with no orders shows `0`.\n"
        "- Order by `customer` ascending.\n"
        "- Trap: `COUNT(CASE ...)` counts every non-NULL branch; "
        "`SUM(status = 'paid')` counts matches.",
        "CREATE TABLE shop_orders (\n  id INT PRIMARY KEY,\n"
        "  customer VARCHAR(20) NOT NULL,\n  status VARCHAR(10) NOT NULL\n);\n"
        "INSERT INTO shop_orders (id, customer, status) VALUES\n"
        "  (1, 'ana', 'new'), (2, 'ana', 'paid'), (3, 'ana', 'paid'),\n"
        "  (4, 'bob', 'shipped'), (5, 'bob', 'shipped'), (6, 'cy', 'new'),\n"
        "  (7, 'cy', 'new'), (8, 'cy', 'paid'), (9, 'cy', 'shipped'),\n"
        "  (10, 'dee', 'paid');",
        "SELECT customer,\n"
        "       SUM(status = 'new') AS new,\n"
        "       SUM(status = 'paid') AS paid,\n"
        "       SUM(status = 'shipped') AS shipped\n"
        "FROM shop_orders GROUP BY customer ORDER BY customer;",
    ),
    write(
        "pivot",
        "Key-value rows to columns with MAX(CASE)",
        "`user_settings` stores one setting per row (`k`, `v`).\n\n"
        "Output columns (no header): `user_id`, `theme`, `lang`, `tz` "
        "(the value of that key for the user).\n\n"
        "- A user without the key shows `NULL`.\n"
        "- Order by `user_id` ascending.\n"
        "- Hint: `MAX` ignores NULLs, so a single match survives.",
        "CREATE TABLE user_settings (\n  user_id INT NOT NULL,\n"
        "  k VARCHAR(10) NOT NULL,\n  v VARCHAR(20) NOT NULL,\n"
        "  PRIMARY KEY (user_id, k)\n);\n"
        "INSERT INTO user_settings (user_id, k, v) VALUES\n"
        "  (1, 'theme', 'dark'), (1, 'lang', 'en'), (1, 'tz', 'UTC'),\n"
        "  (2, 'theme', 'light'), (2, 'lang', 'pl'),\n"
        "  (3, 'tz', 'CET'), (4, 'lang', 'de'), (4, 'theme', 'dark');",
        "SELECT user_id,\n"
        "       MAX(CASE WHEN k = 'theme' THEN v END) AS theme,\n"
        "       MAX(CASE WHEN k = 'lang' THEN v END) AS lang,\n"
        "       MAX(CASE WHEN k = 'tz' THEN v END) AS tz\n"
        "FROM user_settings GROUP BY user_id ORDER BY user_id;",
    ),
    write(
        "pivot",
        "Unpivot wide columns into rows",
        "`marks` has one column per subject.\n\n"
        "Output columns (no header): `student`, `subject` (`math`, `physics` "
        "or `art`), `score`.\n\n"
        "- Skip a subject whose score is `NULL`.\n"
        "- Order by `student`, then `subject` ascending.\n"
        "- Hint: `UNION ALL` of one `SELECT` per column.",
        "CREATE TABLE marks (\n  student VARCHAR(10) PRIMARY KEY,\n"
        "  math INT, physics INT, art INT\n);\n"
        "INSERT INTO marks (student, math, physics, art) VALUES\n"
        "  ('ann', 90, 70, NULL), ('ben', 55, NULL, 80), ('cat', 100, 65, 75);",
        "SELECT student, subject, score FROM (\n"
        "  SELECT student, 'math' AS subject, math AS score FROM marks\n"
        "  UNION ALL SELECT student, 'physics', physics FROM marks\n"
        "  UNION ALL SELECT student, 'art', art FROM marks\n"
        ") t WHERE score IS NOT NULL ORDER BY student, subject;",
    ),
    predict(
        "pivot",
        "Predict: SUM(CASE) without ELSE",
        "`games` holds one result per team per match (`W` or `L`). "
        "What does the pivot return? Watch the teams that never lost.",
        "CREATE TABLE games (\n  id INT PRIMARY KEY,\n"
        "  team VARCHAR(10) NOT NULL,\n  result CHAR(1) NOT NULL\n);\n"
        "INSERT INTO games (id, team, result) VALUES\n"
        "  (1, 'owls', 'W'), (2, 'owls', 'W'), (3, 'hawks', 'W'),\n"
        "  (4, 'hawks', 'L'), (5, 'lions', 'L'), (6, 'lions', 'L'),\n"
        "  (7, 'owls', 'L');",
        "SELECT team,\n"
        "       SUM(CASE WHEN result = 'W' THEN 1 END) AS wins,\n"
        "       SUM(CASE WHEN result = 'L' THEN 1 END) AS losses\n"
        "FROM games GROUP BY team ORDER BY team;",
    ),
    predict(
        "pivot",
        "Predict: COUNT(CASE ... ELSE 0)",
        "Two ways to count the large orders. Which one is wrong, and what "
        "does each print?",
        "CREATE TABLE big_orders (\n  id INT PRIMARY KEY,\n"
        "  region VARCHAR(10) NOT NULL,\n  amount INT NOT NULL\n);\n"
        "INSERT INTO big_orders (id, region, amount) VALUES\n"
        "  (1, 'east', 500), (2, 'east', 40), (3, 'east', 700),\n"
        "  (4, 'west', 30), (5, 'west', 20), (6, 'north', 900);",
        "SELECT region,\n"
        "       COUNT(CASE WHEN amount >= 100 THEN 1 ELSE 0 END) AS wrong,\n"
        "       COUNT(CASE WHEN amount >= 100 THEN 1 END) AS right_one,\n"
        "       SUM(amount >= 100) AS also_right\n"
        "FROM big_orders GROUP BY region ORDER BY region;",
    ),
)
