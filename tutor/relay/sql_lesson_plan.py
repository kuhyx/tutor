# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Concepts of the guided SQL lessons: a goal and a builtin drill's dataset each."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Concept:
    """A concept; ``dataset`` names the builtin drill whose tables it uses."""

    title: str
    dataset: str
    goal: str


PLAN: Final[dict[str, tuple[Concept, ...]]] = {
    "basics": (
        Concept(
            "NULL comparisons",
            "t01_null_not_equal",
            "A comparison with NULL (=, !=, <, NOT ...) is UNKNOWN, never true or "
            "false; WHERE keeps only rows that are TRUE; IS NULL is the only test.",
        ),
        Concept(
            "JOIN ON vs WHERE",
            "t03_left_join_on",
            "In a LEFT JOIN a condition in ON only decides which right rows match "
            "(unmatched left rows survive with NULLs); the same condition in WHERE "
            "filters the joined rows and drops them.",
        ),
    ),
    "joins-null": (
        Concept(
            "anti-join",
            "t05_anti_join",
            "Rows with no match: LEFT JOIN then WHERE right.key IS NULL (or NOT "
            "EXISTS); NOT IN breaks when the subquery yields a NULL.",
        ),
    ),
    "group-having": (
        Concept(
            "WHERE vs HAVING",
            "09_group_having",
            "WHERE filters rows before grouping, HAVING filters groups after "
            "aggregation; aggregates are only allowed in HAVING.",
        ),
    ),
    "pivot": (
        Concept(
            "pivot with SUM(CASE WHEN)",
            "01_pivot_sum",
            "One output column per category via SUM(CASE WHEN cat = x THEN v "
            "ELSE 0 END) with GROUP BY the row key; ELSE NULL vs 0 changes empty "
            "cells.",
        ),
    ),
    "dates": (
        Concept(
            "date bucketing",
            "03_month_bucket",
            "Group by a month with DATE_FORMAT / YEAR+MONTH, never by raw "
            "datetimes; boundaries (first/last day, BETWEEN with times) matter.",
        ),
    ),
    "number-format": (
        Concept(
            "integer division and rounding",
            "06_number_traps",
            "/ is decimal division in MySQL, DIV is integer; ROUND and CAST "
            "change what is printed; AVG of integers is decimal.",
        ),
    ),
    "window": (
        Concept(
            "top-N per group with window functions",
            "10_window_topn",
            "ROW_NUMBER/RANK/DENSE_RANK with PARTITION BY and ORDER BY; ties are "
            "where the three differ; WHERE cannot filter a window result directly.",
        ),
    ),
    "strings": (
        Concept(
            "CONCAT, percentages and formatting",
            "12_concat_percent",
            "CONCAT with NULL is NULL; percent = part * 100.0 / total; ROUND and "
            "CONCAT decide the exact printed text.",
        ),
    ),
}
