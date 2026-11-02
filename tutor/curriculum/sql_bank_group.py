# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""SQL cards for WHERE vs HAVING, pivots, dates, number formats and quotes."""

from __future__ import annotations

from typing import Final

from tutor.curriculum.sql_card_spec import CardSpec

PG: Final = "https://www.postgresql.org/docs/current/"
MARIA: Final = "https://mariadb.com/kb/en/"
_TV: Final = "CREATE TABLE t (v INT); INSERT INTO t VALUES (2),(3);"
_GV: Final = (
    "CREATE TABLE t (g CHAR(1), v INT); INSERT INTO t VALUES ('a',1),('a',2),('b',1);"
)
_X: Final = "CREATE TABLE t (x INT); INSERT INTO t VALUES (1),(2);"
_S3: Final = (
    "CREATE TABLE s (r CHAR(1), cat CHAR(1), v INT); "
    "INSERT INTO s VALUES ('A','x',1),('A','y',2),('B','x',3);"
)
_S2: Final = (
    "CREATE TABLE s (r CHAR(1), cat CHAR(1), v INT); "
    "INSERT INTO s VALUES ('A','x',1),('B','y',2);"
)
_E: Final = "CREATE TABLE e (d DATETIME); INSERT INTO e VALUES ('2026-10-14 15:30:45');"
_ALIAS: Final = (
    "An output column's name can be used to refer to the column's value in "
    "ORDER BY and GROUP BY clauses, but not in the WHERE or HAVING clauses; "
    "there you must write out the expression instead."
)
_PIVOT: Final = "SELECT r, SUM(CASE WHEN cat = 'x' THEN v END) FROM s GROUP BY r"
_ELSE: Final = (
    "If the ELSE clause is omitted and no condition is true, the result is null."
)

HAVING_CARDS: Final = (
    CardSpec(
        "exec-order",
        "In what logical order does SQL evaluate FROM, WHERE, GROUP BY, HAVING, "
        "SELECT, ORDER BY and LIMIT?",
        "FROM/JOIN, WHERE, GROUP BY, HAVING, SELECT, ORDER BY, LIMIT: WHERE sees "
        "no SELECT aliases or aggregates.",
        PG + "sql-select.html",
        "If the HAVING clause is present, it eliminates groups that do not "
        "satisfy the given condition. (See GROUP BY Clause and HAVING Clause "
        "below.) Although query output columns are nominally computed in the "
        "next step",
    ),
    CardSpec(
        "alias-where",
        "t(x): 1,2. What does SELECT x * 2 AS d FROM t WHERE d > 2 return?",
        "WHERE runs before SELECT, so the alias d does not exist yet there.",
        PG + "sql-select.html",
        _ALIAS,
        _X,
        "SELECT x * 2 AS d FROM t WHERE d > 2",
    ),
    CardSpec(
        "agg-where",
        "t(g,v): (a,1),(a,2),(b,1). What does SELECT g FROM t WHERE SUM(v) > 1 "
        "GROUP BY g return?",
        "WHERE runs before grouping, so aggregates are not allowed in it; use HAVING.",
        PG + "tutorial-agg.html",
        "Thus, the WHERE clause must not contain aggregate functions; it makes no "
        "sense to try to use an aggregate to determine which rows will be inputs "
        "to the aggregates.",
        _GV,
        "SELECT g FROM t WHERE SUM(v) > 1 GROUP BY g",
    ),
    CardSpec(
        "having-groups",
        "t(g,v): (a,1),(a,2),(b,1). SELECT g, SUM(v) FROM t GROUP BY g "
        "HAVING SUM(v) > 1 returns?",
        "HAVING filters whole groups after aggregation; WHERE filters rows before.",
        PG + "tutorial-agg.html",
        "WHERE selects input rows before groups and aggregates are computed "
        "(thus, it controls which rows go into the aggregate computation), "
        "whereas HAVING selects group rows after groups and aggregates are computed.",
        _GV,
        "SELECT g, SUM(v) FROM t GROUP BY g HAVING SUM(v) > 1",
    ),
    CardSpec(
        "having-alias",
        "t(g,v): (a,1),(a,2),(b,1). SELECT g, SUM(v) AS s FROM t GROUP BY g "
        "HAVING s > 1 returns?",
        "MySQL allows the alias in HAVING; portable SQL needs HAVING SUM(v) > 1.",
        PG + "sql-select.html",
        _ALIAS,
        _GV,
        "SELECT g, SUM(v) AS s FROM t GROUP BY g HAVING s > 1",
    ),
)

PIVOT_CARDS: Final = (
    CardSpec(
        "pivot-case",
        "s(r,cat,v): (A,x,1),(A,y,2),(B,x,3). SELECT r, SUM(CASE WHEN cat = 'x' "
        "THEN v END) FROM s GROUP BY r returns?",
        "CASE keeps v only where cat = 'x'; SUM per group makes one pivot column.",
        PG + "functions-conditional.html",
        "If the condition's result is true, the value of the CASE expression is "
        "the result that follows the condition, and the remainder of the CASE "
        "expression is not processed.",
        _S3,
        _PIVOT,
    ),
    CardSpec(
        "empty-null",
        "s(r,cat,v): (A,x,1),(B,y,2). SELECT r, SUM(CASE WHEN cat = 'x' "
        "THEN v END) FROM s GROUP BY r returns?",
        "No matching rows leaves SUM(NULLs) = NULL; use ELSE 0 or "
        "COALESCE(SUM(...), 0).",
        PG + "functions-conditional.html",
        _ELSE,
        _S2,
        _PIVOT,
    ),
    CardSpec(
        "null-cat",
        "s(cat,v): (x,1),(NULL,5). SELECT SUM(CASE WHEN cat = 'x' THEN v END), "
        "SUM(v) FROM s returns?",
        "cat = 'x' is UNKNOWN for the NULL category, so that row is in no "
        "pivot column.",
        "https://en.wikipedia.org/wiki/Null_%28SQL%29",
        "Because the expression i = NULL evaluates to Unknown no matter what "
        "value column i contains (even if it contains Null)",
        "CREATE TABLE s (cat CHAR(1), v INT); INSERT INTO s VALUES ('x',1),(NULL,5);",
        "SELECT SUM(CASE WHEN cat = 'x' THEN v END), SUM(v) FROM s",
    ),
)

FORMAT_CARDS: Final = (
    CardSpec(
        "date-ym",
        "e(d) = 2026-10-14 15:30:45. What does SELECT DATE_FORMAT(d, '%Y-%m') "
        "FROM e return?",
        "%Y is the 4-digit year, %m the 2-digit month number: GROUP BY it for months.",
        MARIA + "date_format/",
        "%x Year with 4 digits when first day of the week is Monday. Used with "
        "%v. %Y Year with 4 digits.",
        _E,
        "SELECT DATE_FORMAT(d, '%Y-%m') FROM e",
    ),
    CardSpec(
        "date-month-name",
        "e(d) = 2026-10-14 15:30:45. What does SELECT DATE_FORMAT(d, '%d:%M') "
        "FROM e return?",
        "%M is the month NAME, %m the number: use %d:%m for 14:10.",
        MARIA + "date_format/",
        "%M Full month name in current locale (Variable lc_time_names ). "
        "%m Month with 2 digits.",
        _E,
        "SELECT DATE_FORMAT(d, '%d:%M') FROM e",
    ),
    CardSpec(
        "date-hour-min",
        "e(d) = 2026-10-14 15:30:45. What does SELECT DATE_FORMAT(d, '%H:%i') "
        "FROM e return?",
        "%H is the hour 00-23 and %i the minutes; %m would be the month.",
        MARIA + "date_format/",
        "%H Hour with 2 digits between 00-23. %h Hour with 2 digits between "
        "01-12. %I Hour with 2 digits between 01-12. %i Minute with 2 digits.",
        _E,
        "SELECT DATE_FORMAT(d, '%H:%i') FROM e",
    ),
    CardSpec(
        "avg-int",
        "t(v) holds 2 and 3. What does SELECT AVG(v) FROM t return?",
        "AVG of integers is a decimal with 4 places; ROUND it for output.",
        MARIA + "avg/",
        "This function computes the arithmetic mean of a numeric expression, "
        "ignoring NULL values.",
        _TV,
        "SELECT AVG(v) FROM t",
    ),
    CardSpec(
        "div-int",
        "What does SELECT 5 / 2 return in MySQL: 2, 2.5 or something else?",
        "/ is decimal division with 4 places; DIV is integer division.",
        MARIA + "division-operator/",
        "The result keeps extra decimal places set by div_precision_increment, "
        "and dividing by zero returns NULL.",
        "",
        "SELECT 5 / 2",
    ),
    CardSpec(
        "round-2",
        "What does SELECT ROUND(5 / 2, 2), ROUND(8 / 2, 2) return?",
        "ROUND(x, 2) on a decimal always prints 2 decimals, even 4.00.",
        MARIA + "round/",
        "Rounds the argument X to D decimal places. D defaults to 0 if not specified.",
        "",
        "SELECT ROUND(5 / 2, 2), ROUND(8 / 2, 2)",
    ),
)

QUOTE_CARDS: Final = (
    CardSpec(
        "quotes",
        "Which quotes delimit a string literal in standard SQL, and what do "
        "double quotes mean there?",
        "Single quotes: 'abc'. Double quotes delimit identifiers (names); MySQL "
        "tolerates strings in them, other databases do not.",
        PG + "sql-syntax-lexical.html",
        "A string constant in SQL is an arbitrary sequence of characters bounded "
        "by single quotes ( ' ), for example 'This is a string'",
    ),
)
