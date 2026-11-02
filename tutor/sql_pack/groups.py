# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""GROUP BY / HAVING drills."""

from __future__ import annotations

from typing import Final

from tutor.sql_pack.spec import EMP_TABLE, Spec, failing, predict, write

_EMP: Final = EMP_TABLE + (
    "INSERT INTO emp (id, name, dept, salary) VALUES\n"
    "  (1, 'ann', 'dev', 90), (2, 'ben', 'dev', 40), (3, 'cat', 'dev', 70),\n"
    "  (4, 'dan', 'ops', 55), (5, 'eve', 'ops', 45), (6, 'fay', 'hr', 60),\n"
    "  (7, 'gus', 'hr', 30), (8, 'hal', 'hr', 65), (9, 'ivy', 'hr', 52);"
)
SPECS: Final[tuple[Spec, ...]] = (
    write(
        "group-having",
        "HAVING on count and average",
        "`emp` has one row per employee.\n\n"
        "Output columns (no header): `dept`, headcount, average salary "
        "`ROUND`ed to 1 decimal.\n\n"
        "- Only departments with at least 3 people and an average salary "
        "above 55.\n"
        "- Order by `dept` ascending.",
        _EMP,
        "SELECT dept, COUNT(*), ROUND(AVG(salary), 1) FROM emp\n"
        "GROUP BY dept HAVING COUNT(*) >= 3 AND AVG(salary) > 55\n"
        "ORDER BY dept;",
    ),
    write(
        "group-having",
        "Find duplicates with HAVING COUNT(*) > 1",
        "`contacts` may list the same email several times.\n\n"
        "Output columns (no header): `email`, how many rows have it.\n\n"
        "- Only emails that appear more than once.\n"
        "- Order by the count descending, then `email`.",
        "CREATE TABLE contacts (\n  id INT PRIMARY KEY,\n  email VARCHAR(20) "
        "NOT NULL\n);\n"
        "INSERT INTO contacts (id, email) VALUES\n"
        "  (1, 'a@x.org'), (2, 'b@x.org'), (3, 'a@x.org'), (4, 'c@x.org'),\n"
        "  (5, 'b@x.org'), (6, 'a@x.org'), (7, 'd@x.org'), (8, 'c@x.org');",
        "SELECT email, COUNT(*) FROM contacts GROUP BY email\n"
        "HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC, email;",
    ),
    write(
        "group-having",
        "The group(s) with the highest total",
        "`sales` has one row per sale.\n\n"
        "Output columns (no header): `category`, its total `amount`, only "
        "for the category (or categories, on a tie) with the highest "
        "total.\n\n"
        "- Order by `category` ascending.\n"
        "- Hint: compare `HAVING SUM(amount)` to a subquery of the maximum "
        "total.",
        "CREATE TABLE sales (\n  id INT PRIMARY KEY,\n  category VARCHAR(10) "
        "NOT NULL,\n"
        "  amount INT NOT NULL\n);\n"
        "INSERT INTO sales (id, category, amount) VALUES\n"
        "  (1, 'books', 40), (2, 'books', 60), (3, 'games', 100),\n"
        "  (4, 'toys', 30), (5, 'toys', 20), (6, 'toys', 50), (7, 'food', 99);",
        "SELECT category, SUM(amount) FROM sales GROUP BY category\n"
        "HAVING SUM(amount) = (\n"
        "  SELECT MAX(t) FROM (SELECT SUM(amount) AS t FROM sales\n"
        "                      GROUP BY category) x)\n"
        "ORDER BY category;",
    ),
    predict(
        "group-having",
        "Predict: WHERE filters rows, HAVING filters groups",
        "The salary filter runs before grouping and the count filter after. "
        "What is left?",
        _EMP,
        "SELECT dept, COUNT(*), SUM(salary) FROM emp\n"
        "WHERE salary > 50 GROUP BY dept HAVING COUNT(*) >= 2\n"
        "ORDER BY dept;",
    ),
    predict(
        "group-having",
        "Predict: COUNT(*), COUNT(col), COUNT(DISTINCT col)",
        "`pets.owner` may be NULL and one `kind` repeats. A NULL key forms "
        "its own group. What is printed?",
        "CREATE TABLE pets (\n  id INT PRIMARY KEY,\n  kind VARCHAR(5) NOT NULL,\n"
        "  owner VARCHAR(5)\n);\n"
        "INSERT INTO pets (id, kind, owner) VALUES\n"
        "  (1, 'cat', 'ann'), (2, 'cat', 'ann'), (3, 'dog', NULL),\n"
        "  (4, 'cat', NULL), (5, 'dog', 'ben'), (6, 'cat', 'ben');",
        "SELECT kind, COUNT(*), COUNT(owner), COUNT(DISTINCT owner)\n"
        "FROM pets GROUP BY kind ORDER BY kind;",
    ),
    failing(
        predict(
            "group-having",
            "Predict: a bare column next to GROUP BY",
            "`name` is neither grouped nor aggregated. With the default "
            "`ONLY_FULL_GROUP_BY` mode of MySQL 8, what does the server do?",
            _EMP,
            "SELECT dept, name, COUNT(*) FROM emp GROUP BY dept;",
        )
    ),
)
