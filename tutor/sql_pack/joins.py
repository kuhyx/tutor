# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Join drills: LEFT JOIN counts, anti-joins, COALESCE, ON vs WHERE, fan-out."""

from __future__ import annotations

from typing import Final

from tutor.sql_pack.spec import Spec, predict, write

_SHOP: Final = (
    "CREATE TABLE clients (\n  id INT PRIMARY KEY,\n  name VARCHAR(10) NOT NULL\n);\n"
    "CREATE TABLE purchases (\n  id INT PRIMARY KEY,\n  client_id INT NOT NULL,\n"
    "  status VARCHAR(8) NOT NULL\n);\n"
    "INSERT INTO clients (id, name) VALUES (1, 'ana'), (2, 'bob'), (3, 'cy'), "
    "(4, 'dee');\n"
    "INSERT INTO purchases (id, client_id, status) VALUES\n"
    "  (1, 1, 'paid'), (2, 1, 'open'), (3, 1, 'paid'), (4, 2, 'open'),\n"
    "  (5, 3, 'paid');"
)
SPECS: Final[tuple[Spec, ...]] = (
    write(
        "joins-null",
        "LEFT JOIN count that keeps zeros",
        "Output columns (no header): client `name`, number of purchases "
        "(`clients` and `purchases` as in the schema).\n\n"
        "- Clients without purchases show `0`.\n"
        "- Order by the count descending, then `name`.\n"
        "- Trap: `COUNT(*)` counts the NULL-extended row as 1; count a "
        "column of the right table.",
        _SHOP,
        "SELECT c.name, COUNT(p.id) FROM clients c\n"
        "LEFT JOIN purchases p ON p.client_id = c.id\n"
        "GROUP BY c.id, c.name ORDER BY COUNT(p.id) DESC, c.name;",
    ),
    write(
        "joins-null",
        "Anti-join with the filter in ON",
        "`pupils` and `enrolments` (one row per pupil per course per year).\n\n"
        "Output column (no header): `name` of every pupil with NO enrolment "
        "in year 2024.\n\n"
        "- Order by `name` ascending.\n"
        "- Trap: a `year = 2024` test in `WHERE` on the right table turns "
        "the LEFT JOIN into an inner join; keep it in `ON`.",
        "CREATE TABLE pupils (\n  id INT PRIMARY KEY,\n  name VARCHAR(10) NOT "
        "NULL\n);\n"
        "CREATE TABLE enrolments (\n  pupil_id INT NOT NULL,\n  course "
        "VARCHAR(10) NOT NULL,\n"
        "  year INT NOT NULL\n);\n"
        "INSERT INTO pupils (id, name) VALUES (1, 'ann'), (2, 'ben'), (3, "
        "'cat'), (4, 'dan');\n"
        "INSERT INTO enrolments (pupil_id, course, year) VALUES\n"
        "  (1, 'math', 2024), (1, 'art', 2023), (2, 'math', 2023),\n"
        "  (3, 'art', 2024), (3, 'math', 2024);",
        "SELECT p.name FROM pupils p\n"
        "LEFT JOIN enrolments e ON e.pupil_id = p.id AND e.year = 2024\n"
        "WHERE e.pupil_id IS NULL ORDER BY p.name;",
    ),
    write(
        "joins-null",
        "COALESCE for the missing parent row",
        "`staff.region_id` may be NULL (not assigned yet); `regions` names "
        "the regions.\n\n"
        "Output columns (no header): region name (`Unassigned` when the "
        "person has no region), headcount.\n\n"
        "- Order by headcount descending, then region name.",
        "CREATE TABLE regions (\n  id INT PRIMARY KEY,\n  name VARCHAR(10) "
        "NOT NULL\n);\n"
        "CREATE TABLE staff (\n  id INT PRIMARY KEY,\n  region_id INT\n);\n"
        "INSERT INTO regions (id, name) VALUES (1, 'north'), (2, 'south'), "
        "(3, 'east');\n"
        "INSERT INTO staff (id, region_id) VALUES\n"
        "  (1, 1), (2, 1), (3, 2), (4, NULL), (5, NULL), (6, NULL), (7, 1);",
        "SELECT COALESCE(r.name, 'Unassigned') AS region, COUNT(*)\n"
        "FROM staff s LEFT JOIN regions r ON r.id = s.region_id\n"
        "GROUP BY COALESCE(r.name, 'Unassigned')\n"
        "ORDER BY COUNT(*) DESC, region;",
    ),
    predict(
        "joins-null",
        "Predict: filter in ON versus WHERE",
        "Which rows does this LEFT JOIN return? The status test sits in "
        "the `ON` clause.",
        _SHOP,
        "SELECT c.name, p.id FROM clients c\n"
        "LEFT JOIN purchases p ON p.client_id = c.id AND p.status = 'paid'\n"
        "ORDER BY c.name, p.id;",
    ),
    predict(
        "joins-null",
        "Predict: the join fan-out inflates SUM",
        "`orders` has one row per order with its `total`; `order_lines` "
        "has one row per line. What do these aggregates give per order?",
        "CREATE TABLE orders (\n  id INT PRIMARY KEY,\n  total INT NOT NULL\n);\n"
        "CREATE TABLE order_lines (\n  id INT PRIMARY KEY,\n  order_id INT NOT NULL,\n"
        "  qty INT NOT NULL,\n  price INT NOT NULL\n);\n"
        "INSERT INTO orders (id, total) VALUES (1, 70), (2, 40), (3, 90);\n"
        "INSERT INTO order_lines (id, order_id, qty, price) VALUES\n"
        "  (1, 1, 2, 20), (2, 1, 1, 30), (3, 2, 4, 10), (4, 3, 1, 30),\n"
        "  (5, 3, 1, 30), (6, 3, 1, 30);",
        "SELECT o.id, COUNT(*), SUM(o.total), SUM(l.qty * l.price)\n"
        "FROM orders o JOIN order_lines l ON l.order_id = o.id\n"
        "GROUP BY o.id ORDER BY o.id;",
    ),
)
