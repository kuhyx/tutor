# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Window-function drills: ROW_NUMBER, DENSE_RANK, LAG, running totals."""

from __future__ import annotations

from typing import Final

from tutor.sql_pack.spec import EMP_TABLE, Spec, predict, write

_EMP: Final = EMP_TABLE + (
    "INSERT INTO emp (id, name, dept, salary) VALUES\n"
    "  (1, 'ann', 'dev', 90), (2, 'ben', 'dev', 40), (3, 'cat', 'dev', 70),\n"
    "  (4, 'dan', 'ops', 55), (5, 'eve', 'ops', 55), (6, 'fay', 'hr', 60),\n"
    "  (7, 'gus', 'hr', 30), (8, 'hal', 'dev', 70);"
)
_SCORES: Final = (
    "CREATE TABLE results (\n  id INT PRIMARY KEY,\n  course VARCHAR(5) NOT NULL,\n"
    "  student VARCHAR(5) NOT NULL,\n  score INT NOT NULL\n);\n"
    "INSERT INTO results (id, course, student, score) VALUES\n"
    "  (1, 'db', 'ann', 90), (2, 'db', 'ben', 85), (3, 'db', 'cat', 90),\n"
    "  (4, 'db', 'dan', 70), (5, 'ai', 'ann', 60), (6, 'ai', 'ben', 95),\n"
    "  (7, 'ai', 'cat', 95), (8, 'ai', 'dan', 80);"
)
SPECS: Final[tuple[Spec, ...]] = (
    write(
        "window",
        "Top 2 per group with ROW_NUMBER",
        "`emp` has one row per employee.\n\n"
        "Output columns (no header): `dept`, `name`, `salary` of the two "
        "best-paid people in each department.\n\n"
        "- Break salary ties by the smaller `id` first.\n"
        "- Order by `dept` ascending, then salary descending, then `id`.",
        _EMP,
        "SELECT dept, name, salary FROM (\n"
        "  SELECT dept, name, salary, id,\n"
        "         ROW_NUMBER() OVER (PARTITION BY dept\n"
        "                            ORDER BY salary DESC, id) AS rn\n"
        "  FROM emp) t WHERE rn <= 2 ORDER BY dept, salary DESC, id;",
    ),
    write(
        "window",
        "Second highest distinct score with DENSE_RANK",
        "`results` has one score per student per course.\n\n"
        "Output columns (no header): `course`, `student`, `score` of "
        "everyone holding the SECOND highest distinct score of their "
        "course.\n\n"
        "- Order by `course`, then `student` ascending.\n"
        "- Trap: with ties, `ROW_NUMBER` or `RANK` skip or miss the "
        "second level; `DENSE_RANK` does not.",
        _SCORES,
        "SELECT course, student, score FROM (\n"
        "  SELECT course, student, score,\n"
        "         DENSE_RANK() OVER (PARTITION BY course\n"
        "                            ORDER BY score DESC) AS r\n"
        "  FROM results) t WHERE r = 2 ORDER BY course, student;",
    ),
    write(
        "window",
        "Day-over-day change with LAG",
        "`visits` has one row per day.\n\n"
        "Output columns (no header): `day`, `visits`, the change against "
        "the previous day (`NULL` for the first day).\n\n"
        "- Order by `day` ascending.",
        "CREATE TABLE visits (\n  day DATE PRIMARY KEY,\n  visits INT NOT NULL\n);\n"
        "INSERT INTO visits (day, visits) VALUES\n"
        "  ('2024-03-01', 120), ('2024-03-02', 150), ('2024-03-03', 90),\n"
        "  ('2024-03-04', 90), ('2024-03-05', 200);",
        "SELECT day, visits, visits - LAG(visits) OVER (ORDER BY day)\n"
        "FROM visits ORDER BY day;",
    ),
    predict(
        "window",
        "Predict: ROW_NUMBER, RANK and DENSE_RANK on ties",
        "Three ranking functions over the same ordering, with a tie. "
        "What does each print?",
        _SCORES,
        "SELECT student, score,\n"
        "       ROW_NUMBER() OVER (ORDER BY score DESC, id),\n"
        "       RANK() OVER (ORDER BY score DESC),\n"
        "       DENSE_RANK() OVER (ORDER BY score DESC)\n"
        "FROM results WHERE course = 'db' ORDER BY score DESC, id;",
    ),
    predict(
        "window",
        "Predict: running total with tied days",
        "`SUM() OVER (ORDER BY day)` uses the default frame. What running "
        "total do the two rows of the same day get?",
        "CREATE TABLE tx (\n  id INT PRIMARY KEY,\n  day DATE NOT NULL,\n"
        "  amt INT NOT NULL\n);\n"
        "INSERT INTO tx (id, day, amt) VALUES\n"
        "  (1, '2024-01-01', 10), (2, '2024-01-02', 5), (3, '2024-01-02', 20),\n"
        "  (4, '2024-01-03', 1);",
        "SELECT id, day, amt, SUM(amt) OVER (ORDER BY day) FROM tx ORDER BY id;",
    ),
)
