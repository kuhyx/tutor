# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The shape of one drill spec (the keys ``save_generated`` takes)."""

from __future__ import annotations

from typing import Final, NotRequired, TypedDict


class Spec(TypedDict):
    """A drill: ``reference_sql`` is the answer (write) or the query to predict."""

    kind: str
    topic: str
    title: str
    task_md: str
    schema_sql: str
    reference_sql: str
    expect_error: NotRequired[bool]


EMP_TABLE: Final = (
    "CREATE TABLE emp (\n  id INT PRIMARY KEY,\n  name VARCHAR(10) NOT NULL,\n"
    "  dept VARCHAR(5) NOT NULL,\n  salary INT NOT NULL\n);\n"
)


type Fields = tuple[str, str, str, str, str]


def _spec(kind: str, fields: Fields) -> Spec:
    topic, title, task, schema, sql = fields
    return {
        "kind": kind,
        "topic": topic,
        "title": title,
        "task_md": task,
        "schema_sql": schema,
        "reference_sql": sql,
    }


def write(topic: str, title: str, task: str, schema: str, sql: str) -> Spec:
    """A write drill: the learner must produce ``sql``'s output."""
    return _spec("write", (topic, title, task, schema, sql))


def predict(topic: str, title: str, task: str, schema: str, sql: str) -> Spec:
    """A predict drill: the learner types what ``sql`` prints."""
    return _spec("predict", (topic, title, task, schema, sql))


def failing(spec: Spec) -> Spec:
    """``spec`` whose query is expected to fail (the learner types ``ERROR``)."""
    return {**spec, "expect_error": True}
