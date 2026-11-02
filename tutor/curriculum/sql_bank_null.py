# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""SQL cards for the NULL, JOIN and anti-join concepts of the guided lessons."""

from __future__ import annotations

from typing import Final

from tutor.curriculum.sql_card_spec import CardSpec

NULL_WIKI: Final = "https://en.wikipedia.org/wiki/Null_%28SQL%29"
JOIN_WIKI: Final = "https://en.wikipedia.org/wiki/Join_%28SQL%29"
SELECT_WIKI: Final = "https://en.wikipedia.org/wiki/Select_%28SQL%29"
_T1: Final = "CREATE TABLE t (x INT); INSERT INTO t VALUES (1),(NULL);"
_T12: Final = "CREATE TABLE t (x INT); INSERT INTO t VALUES (1),(2),(NULL);"
_AB: Final = (
    "CREATE TABLE a (id INT); CREATE TABLE b (a_id INT, v CHAR(1)); "
    "INSERT INTO a VALUES (1),(2); INSERT INTO b VALUES (1,'x');"
)
_TRUTH: Final = "True True True True True True False True False False True Unknown "

NULL_CARDS: Final = (
    CardSpec(
        "null-eq",
        "t(x) holds 1 and NULL. What does SELECT x = NULL FROM t return?",
        "A comparison with NULL is UNKNOWN, never TRUE; test with IS NULL.",
        NULL_WIKI,
        "which compares the value 10 to Null, is Unknown: SELECT 10 = NULL -- "
        "Results in Unknown",
        _T1,
        "SELECT x = NULL FROM t",
    ),
    CardSpec(
        "not-unknown",
        "t(x) holds 1 and NULL. What does SELECT NOT (x = 1) FROM t return?",
        "NOT UNKNOWN is still UNKNOWN (NULL); only the TRUE row flips.",
        NULL_WIKI,
        "p NOT p True False False True Unknown Unknown",
        _T1,
        "SELECT NOT (x = 1) FROM t",
    ),
    CardSpec(
        "or-true",
        "What does SELECT NULL OR TRUE return, and why?",
        "UNKNOWN OR TRUE is TRUE: one TRUE side decides an OR.",
        NULL_WIKI,
        "SELECT NULL OR TRUE -- Results in True In this case, the fact that the "
        "value on the left of OR is unknowable is irrelevant",
        "",
        "SELECT NULL OR TRUE",
    ),
    CardSpec(
        "and-true",
        "What does SELECT NULL AND TRUE return, and why?",
        "UNKNOWN AND TRUE is UNKNOWN: an AND needs both sides TRUE.",
        NULL_WIKI,
        "p q p OR q p AND q p = q " + _TRUTH + "True Unknown Unknown",
        "",
        "SELECT NULL AND TRUE",
    ),
    CardSpec(
        "and-false",
        "What does SELECT NULL AND FALSE return, and why?",
        "UNKNOWN AND FALSE is FALSE (0): one FALSE side decides an AND.",
        NULL_WIKI,
        "False True True False False False False False False True False "
        "Unknown Unknown False Unknown",
        "",
        "SELECT NULL AND FALSE",
    ),
    CardSpec(
        "where-true-only",
        "t(x) holds 1, 2 and NULL. What does SELECT x FROM t WHERE x != 1 return?",
        "WHERE keeps only TRUE rows; NULL != 1 is UNKNOWN, so that row is dropped.",
        NULL_WIKI,
        "The WHERE clause causes the DML statement to act on only those rows for "
        "which the predicate evaluates to True.",
        _T12,
        "SELECT x FROM t WHERE x != 1",
    ),
    CardSpec(
        "is-null-fix",
        "t(x) holds 1, 2 and NULL. What does WHERE x != 1 OR x IS NULL keep?",
        "IS NULL is TRUE for the NULL row, and UNKNOWN OR TRUE is TRUE.",
        NULL_WIKI,
        "The IS NULL and IS NOT NULL predicates (which use a postfix syntax) "
        "test whether data is, or is not, Null.",
        _T12,
        "SELECT x FROM t WHERE x != 1 OR x IS NULL",
    ),
)

JOIN_CARDS: Final = (
    CardSpec(
        "join-on",
        "a(id): 1,2; b(a_id,v): (1,x). SELECT a.id, b.v FROM a LEFT JOIN b "
        "ON b.a_id = a.id AND b.v = 'y' returns?",
        "A condition in ON only decides matches: every left row survives, with NULLs.",
        JOIN_WIKI,
        'always contains all rows of the "left" table (A), even if the '
        'join-condition does not find any matching row in the "right" table (B).',
        _AB,
        "SELECT a.id, b.v FROM a LEFT JOIN b ON b.a_id = a.id AND b.v = 'y'",
    ),
    CardSpec(
        "join-where",
        "a(id): 1,2; b(a_id,v): (1,x). SELECT a.id, b.v FROM a LEFT JOIN b "
        "ON b.a_id = a.id WHERE b.v = 'y' returns?",
        "WHERE filters after the join: NULL-extended rows fail it, so LEFT acts "
        "like INNER.",
        SELECT_WIKI,
        "The WHERE clause eliminates all rows from the result set where the "
        "comparison predicate does not evaluate to True.",
        _AB,
        "SELECT a.id, b.v FROM a LEFT JOIN b ON b.a_id = a.id WHERE b.v = 'y'",
    ),
    CardSpec(
        "anti-join",
        "a(id): 1,2; b(a_id,v): (1,x). SELECT a.id FROM a LEFT JOIN b "
        "ON b.a_id = a.id WHERE b.a_id IS NULL returns?",
        "Unmatched left rows get NULL right columns; IS NULL on the key keeps "
        "only them.",
        JOIN_WIKI,
        "if the ON clause matches 0 (zero) rows in B (for a given row in A), the "
        "join will still return a row in the result (for that row)—but with "
        "NULL in each column from B.",
        _AB,
        "SELECT a.id FROM a LEFT JOIN b ON b.a_id = a.id WHERE b.a_id IS NULL",
    ),
)
