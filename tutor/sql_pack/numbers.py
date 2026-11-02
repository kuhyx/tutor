# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Number-format drills: ROUND, FORMAT, CAST DECIMAL, division, percent."""

from __future__ import annotations

from typing import Final

from tutor.sql_pack.spec import Spec, predict, write

SPECS: Final[tuple[Spec, ...]] = (
    write(
        "number-format",
        "Gross price with ROUND and FORMAT",
        "`bills` has a net amount and a VAT rate (`0.23` means 23 %).\n\n"
        "Output columns (no header): `id`, gross = net * (1 + rate) "
        "rounded to 2 decimals, the same gross as text with thousands "
        "separators and 2 decimals (like `1,234.50`).\n\n"
        "- Order by `id` ascending.",
        "CREATE TABLE bills (\n  id INT PRIMARY KEY,\n"
        "  net DECIMAL(10,2) NOT NULL,\n  rate DECIMAL(3,2) NOT NULL\n);\n"
        "INSERT INTO bills (id, net, rate) VALUES\n"
        "  (1, 1000.00, 0.23), (2, 19.99, 0.08), (3, 123456.70, 0.23),\n"
        "  (4, 0.50, 0.00);",
        "SELECT id, ROUND(net * (1 + rate), 2),\n"
        "       FORMAT(ROUND(net * (1 + rate), 2), 2)\n"
        "FROM bills ORDER BY id;",
    ),
    write(
        "number-format",
        "Pass rate as a percent string",
        "`attempts` has one row per exam attempt (`passed` is 1 or 0).\n\n"
        "Output columns (no header): `class`, number of attempts, the pass "
        "rate as text with one decimal and a percent sign (like `66.7%`).\n\n"
        "- Order by `class` ascending.\n"
        "- Trap: `/` in MySQL is decimal division, `DIV` is the integer one.",
        "CREATE TABLE attempts (\n  id INT PRIMARY KEY,\n"
        "  class VARCHAR(5) NOT NULL,\n  passed TINYINT NOT NULL\n);\n"
        "INSERT INTO attempts (id, class, passed) VALUES\n"
        "  (1, '1A', 1), (2, '1A', 0), (3, '1A', 1), (4, '1B', 1),\n"
        "  (5, '1B', 1), (6, '1B', 1), (7, '1C', 0), (8, '1C', 1),\n"
        "  (9, '1C', 0), (10, '1C', 0), (11, '1C', 0), (12, '1C', 0);",
        "SELECT class, COUNT(*),\n"
        "       CONCAT(ROUND(100 * SUM(passed) / COUNT(*), 1), '%')\n"
        "FROM attempts GROUP BY class ORDER BY class;",
    ),
    write(
        "number-format",
        "Unit price: the 4-decimal division trap",
        "`lots` has a total price in `DECIMAL(10,2)` and a quantity.\n\n"
        "Output columns (no header): `id`, unit price as `DECIMAL(10,2)` "
        "via `CAST`, the whole-unit price using integer division.\n\n"
        "- Order by `id` ascending.\n"
        "- Trap: `total / qty` returns extra decimals (`3.3333`); "
        "cast it to get exactly two.",
        "CREATE TABLE lots (\n  id INT PRIMARY KEY,\n"
        "  total DECIMAL(10,2) NOT NULL,\n  qty INT NOT NULL\n);\n"
        "INSERT INTO lots (id, total, qty) VALUES\n"
        "  (1, 10.00, 3), (2, 99.99, 4), (3, 5.50, 2), (4, 100.00, 8);",
        "SELECT id, CAST(total / qty AS DECIMAL(10,2)), total DIV qty\n"
        "FROM lots ORDER BY id;",
    ),
    predict(
        "number-format",
        "Predict: division and rounding functions",
        "For each number, what do `/`, `DIV`, `ROUND` with and without "
        "decimals and `TRUNCATE` return? Watch the negative one.",
        "CREATE TABLE nums (x INT PRIMARY KEY);\n"
        "INSERT INTO nums (x) VALUES (10), (7), (-7);",
        "SELECT x, x / 4, x DIV 4, ROUND(x / 4), ROUND(x / 4, 1),\n"
        "       TRUNCATE(x / 4, 1)\nFROM nums ORDER BY x;",
    ),
    predict(
        "number-format",
        "Predict: AVG scale, ROUND and FORMAT",
        "What do `AVG`, `ROUND(AVG)`, `FORMAT(SUM, 0)` and a `$` price "
        "built with `FORMAT(..., 2)` print per department?",
        "CREATE TABLE staff (\n  id INT PRIMARY KEY,\n"
        "  dept VARCHAR(5) NOT NULL,\n  pay INT NOT NULL\n);\n"
        "INSERT INTO staff (id, dept, pay) VALUES\n"
        "  (1, 'ops', 3000), (2, 'ops', 4501), (3, 'dev', 7000),\n"
        "  (4, 'dev', 7500), (5, 'dev', 12345), (6, 'hr', 2999);",
        "SELECT dept, AVG(pay), ROUND(AVG(pay)), FORMAT(SUM(pay), 0),\n"
        "       CONCAT('$', FORMAT(AVG(pay), 2))\n"
        "FROM staff GROUP BY dept ORDER BY dept;",
    ),
)
