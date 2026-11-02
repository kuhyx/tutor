# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Date drills: DATE_FORMAT, STR_TO_DATE, DATEDIFF, TIMESTAMPDIFF, buckets."""

from __future__ import annotations

from typing import Final

from tutor.sql_pack.spec import Spec, predict, write

SPECS: Final[tuple[Spec, ...]] = (
    write(
        "dates",
        "Format a DATETIME with DATE_FORMAT",
        "`tickets.opened_at` is a `DATETIME`.\n\n"
        "Output columns (no header): `id`, then the time as text like "
        "`Mon 04 Mar 2024, 07:05 PM` (weekday abbreviation, 2-digit day, "
        "month abbreviation, year, 12-hour clock with minutes and AM/PM).\n\n"
        "- Order by `id` ascending.\n"
        "- Trap: `%h` is the 12-hour clock, `%H` the 24-hour one; `%i` is "
        "minutes, `%m` is the month.",
        "CREATE TABLE tickets (\n  id INT PRIMARY KEY,\n"
        "  opened_at DATETIME NOT NULL\n);\n"
        "INSERT INTO tickets (id, opened_at) VALUES\n"
        "  (1, '2024-03-04 19:05:00'), (2, '2023-12-31 00:30:00'),\n"
        "  (3, '2024-07-09 12:00:00'), (4, '2022-01-01 08:45:30');",
        "SELECT id, DATE_FORMAT(opened_at, '%a %d %b %Y, %h:%i %p')\n"
        "FROM tickets ORDER BY id;",
    ),
    write(
        "dates",
        "Parse DD-Mon-YY text with STR_TO_DATE",
        "`entries.logged` stores a date as text like `05-Mar-24` "
        "(day, month abbreviation, 2-digit year).\n\n"
        "Output columns (no header): `id`, the date as `YYYY/MM/DD`.\n\n"
        "- Keep only entries logged in 2024 or later (compare real dates).\n"
        "- Order by the parsed date ascending, then `id`.\n"
        "- Hint: `%d-%b-%y` parses it, `%Y/%m/%d` prints it.",
        "CREATE TABLE entries (\n  id INT PRIMARY KEY,\n"
        "  logged VARCHAR(10) NOT NULL\n);\n"
        "INSERT INTO entries (id, logged) VALUES\n"
        "  (1, '05-Mar-24'), (2, '28-Dec-23'), (3, '01-Jan-24'),\n"
        "  (4, '15-Aug-25'), (5, '30-Nov-22'), (6, '01-Jan-24');",
        "SELECT id, DATE_FORMAT(STR_TO_DATE(logged, '%d-%b-%y'), '%Y/%m/%d')\n"
        "FROM entries WHERE STR_TO_DATE(logged, '%d-%b-%y') >= '2024-01-01'\n"
        "ORDER BY STR_TO_DATE(logged, '%d-%b-%y'), id;",
    ),
    write(
        "dates",
        "Days between dates with DATEDIFF",
        "`loans` has `borrowed` and `returned` dates (`returned` is NULL "
        "while the book is out).\n\n"
        "Output columns (no header): `id`, days kept, `late` or `ok`.\n\n"
        "- Only returned loans. Late means more than 14 days kept.\n"
        "- Order by `id` ascending.\n"
        "- Trap: `DATEDIFF(a, b)` is `a - b`; the later date goes first.",
        "CREATE TABLE loans (\n  id INT PRIMARY KEY,\n"
        "  borrowed DATE NOT NULL,\n  returned DATE\n);\n"
        "INSERT INTO loans (id, borrowed, returned) VALUES\n"
        "  (1, '2024-01-10', '2024-01-24'), (2, '2024-01-31', '2024-03-01'),\n"
        "  (3, '2024-02-01', NULL), (4, '2023-12-20', '2024-01-02'),\n"
        "  (5, '2024-02-27', '2024-03-12');",
        "SELECT id, DATEDIFF(returned, borrowed),\n"
        "       IF(DATEDIFF(returned, borrowed) > 14, 'late', 'ok')\n"
        "FROM loans WHERE returned IS NOT NULL ORDER BY id;",
    ),
    write(
        "dates",
        "Elapsed time with TIMESTAMPDIFF",
        "`sessions` has `started` and `ended` as `DATETIME`.\n\n"
        "Output columns (no header): `id`, whole minutes elapsed, whole "
        "hours elapsed.\n\n"
        "- Order by `id` ascending.\n"
        "- Trap: `TIMESTAMPDIFF` truncates toward zero, it never rounds, "
        "and sessions may cross midnight.",
        "CREATE TABLE sessions (\n  id INT PRIMARY KEY,\n"
        "  started DATETIME NOT NULL,\n  ended DATETIME NOT NULL\n);\n"
        "INSERT INTO sessions (id, started, ended) VALUES\n"
        "  (1, '2024-05-01 09:00:00', '2024-05-01 10:59:59'),\n"
        "  (2, '2024-05-01 23:30:00', '2024-05-02 01:10:00'),\n"
        "  (3, '2024-05-03 08:00:00', '2024-05-03 08:00:30'),\n"
        "  (4, '2024-05-04 00:00:00', '2024-05-06 12:15:00');",
        "SELECT id, TIMESTAMPDIFF(MINUTE, started, ended),\n"
        "       TIMESTAMPDIFF(HOUR, started, ended)\n"
        "FROM sessions ORDER BY id;",
    ),
    write(
        "dates",
        "Monthly totals: bucket by year and month",
        "`payments` has one row per payment.\n\n"
        "Output columns (no header): `month` as `YYYY-MM`, the total "
        "`amount` of that month, the number of payments.\n\n"
        "- Only months that have payments.\n"
        "- Order by `month` ascending.\n"
        "- Trap: grouping by month number alone merges January 2023 with "
        "January 2024.",
        "CREATE TABLE payments (\n  id INT PRIMARY KEY,\n"
        "  paid_on DATE NOT NULL,\n  amount INT NOT NULL\n);\n"
        "INSERT INTO payments (id, paid_on, amount) VALUES\n"
        "  (1, '2023-01-15', 100), (2, '2023-01-31', 50), (3, '2023-02-01', 70),\n"
        "  (4, '2024-01-02', 200), (5, '2024-01-20', 25), (6, '2024-03-09', 60),\n"
        "  (7, '2023-12-31', 10);",
        "SELECT DATE_FORMAT(paid_on, '%Y-%m') AS month, SUM(amount), COUNT(*)\n"
        "FROM payments GROUP BY DATE_FORMAT(paid_on, '%Y-%m') ORDER BY month;",
    ),
    predict(
        "dates",
        "Predict: month-end and weekday arithmetic",
        "What do `DATE_ADD` over a month, `LAST_DAY`, `DAYNAME` and "
        "`WEEKDAY` (Monday is 0) return for these dates?",
        "CREATE TABLE some_days (d DATE PRIMARY KEY);\n"
        "INSERT INTO some_days (d) VALUES\n"
        "  ('2024-01-31'), ('2024-02-29'), ('2023-12-31');",
        "SELECT d, DATE_ADD(d, INTERVAL 1 MONTH), LAST_DAY(d), DAYNAME(d),\n"
        "       WEEKDAY(d)\nFROM some_days ORDER BY d;",
    ),
    predict(
        "dates",
        "Predict: STR_TO_DATE with the wrong format",
        "The format string says `DD/MM/YYYY`. What comes back for each "
        "text, including the ones that do not fit?",
        "CREATE TABLE raw_dates (\n  id INT PRIMARY KEY,\n"
        "  txt VARCHAR(12) NOT NULL\n);\n"
        "INSERT INTO raw_dates (id, txt) VALUES\n"
        "  (1, '05/03/2024'), (2, '2024-03-05'), (3, '5.3.2024'),\n"
        "  (4, '1/2/2024');",
        "SELECT id, STR_TO_DATE(txt, '%d/%m/%Y') FROM raw_dates ORDER BY id;",
    ),
)
