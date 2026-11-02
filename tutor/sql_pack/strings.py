# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""String drills: CONCAT, CONCAT_WS, GROUP_CONCAT, SUBSTRING_INDEX."""

from __future__ import annotations

from typing import Final

from tutor.sql_pack.spec import Spec, predict, write

SPECS: Final[tuple[Spec, ...]] = (
    write(
        "strings",
        "Full name with CONCAT_WS and a NULL middle name",
        "`people` has `first`, `middle` (often NULL) and `last`.\n\n"
        "Output columns (no header): `id`, the full name as "
        "`first middle last` with single spaces and no gap when the "
        "middle name is missing.\n\n"
        "- Order by `id` ascending.\n"
        "- Trap: `CONCAT` returns NULL if any argument is NULL; "
        "`CONCAT_WS` skips NULLs.",
        "CREATE TABLE people (\n  id INT PRIMARY KEY,\n  first VARCHAR(10) NOT NULL,\n"
        "  middle VARCHAR(10),\n  last VARCHAR(10) NOT NULL\n);\n"
        "INSERT INTO people (id, first, middle, last) VALUES\n"
        "  (1, 'Ada', NULL, 'Byron'), (2, 'Alan', 'Mathison', 'Turing'),\n"
        "  (3, 'Grace', 'Brewster', 'Hopper'), (4, 'Linus', NULL, 'Torvalds');",
        "SELECT id, CONCAT_WS(' ', first, middle, last) FROM people ORDER BY id;",
    ),
    write(
        "strings",
        "List members per team with GROUP_CONCAT",
        "`members` has one row per person and team.\n\n"
        "Output columns (no header): `team`, the member names sorted "
        "alphabetically and joined with `, ` (comma and space), how many "
        "members.\n\n"
        "- Order by `team` ascending.\n"
        "- Trap: the default separator is a bare comma and the order is "
        "unspecified; put `ORDER BY` and `SEPARATOR` inside.",
        "CREATE TABLE members (\n  id INT PRIMARY KEY,\n  team VARCHAR(6) NOT NULL,\n"
        "  name VARCHAR(6) NOT NULL\n);\n"
        "INSERT INTO members (id, team, name) VALUES\n"
        "  (1, 'red', 'zoe'), (2, 'red', 'adam'), (3, 'blue', 'mia'),\n"
        "  (4, 'red', 'lee'), (5, 'blue', 'bo'), (6, 'green', 'kim');",
        "SELECT team, GROUP_CONCAT(name ORDER BY name SEPARATOR ', '), COUNT(*)\n"
        "FROM members GROUP BY team ORDER BY team;",
    ),
    write(
        "strings",
        "Email domains with SUBSTRING_INDEX",
        "`accounts.email` holds addresses like `name@domain`.\n\n"
        "Output columns (no header): the domain part (after the `@`, "
        "lower case), how many accounts use it.\n\n"
        "- Order by the count descending, then the domain.",
        "CREATE TABLE accounts (\n  id INT PRIMARY KEY,\n  email VARCHAR(30) "
        "NOT NULL\n);\n"
        "INSERT INTO accounts (id, email) VALUES\n"
        "  (1, 'ann@Mail.com'), (2, 'bob@mail.com'), (3, 'cy@corp.example'),\n"
        "  (4, 'dee@MAIL.com'), (5, 'eli@corp.example'), (6, 'fay@one.org');",
        "SELECT LOWER(SUBSTRING_INDEX(email, '@', -1)) AS domain, COUNT(*)\n"
        "FROM accounts GROUP BY domain ORDER BY COUNT(*) DESC, domain;",
    ),
    predict(
        "strings",
        "Predict: common string functions with NULL",
        "What do `UPPER(LEFT())`, `SUBSTRING` with a negative start, "
        "`LPAD`, `REPLACE` and `LOCATE` (0 = not found) return? Mind the "
        "NULL row.",
        "CREATE TABLE words (\n  n INT PRIMARY KEY,\n  s VARCHAR(10)\n);\n"
        "INSERT INTO words (n, s) VALUES (1, 'banana'), (2, 'kiwi'), (3, NULL),\n"
        "  (4, 'Plum');",
        "SELECT n, UPPER(LEFT(s, 2)), SUBSTRING(s, -3), LPAD(n, 4, '0'),\n"
        "       REPLACE(s, 'a', '*'), LOCATE('i', s)\nFROM words ORDER BY n;",
    ),
    predict(
        "strings",
        "Predict: GROUP_CONCAT with DISTINCT and NULL",
        "`GROUP_CONCAT` skips NULLs and `DISTINCT` drops repeats. What "
        "does each department print?",
        "CREATE TABLE skills (\n  id INT PRIMARY KEY,\n  dept VARCHAR(5) NOT NULL,\n"
        "  skill VARCHAR(8)\n);\n"
        "INSERT INTO skills (id, dept, skill) VALUES\n"
        "  (1, 'dev', 'sql'), (2, 'dev', 'go'), (3, 'dev', 'sql'),\n"
        "  (4, 'ops', NULL), (5, 'ops', 'bash'), (6, 'hr', NULL);",
        "SELECT dept, GROUP_CONCAT(DISTINCT skill ORDER BY skill SEPARATOR '|')\n"
        "FROM skills GROUP BY dept ORDER BY dept;",
    ),
)
