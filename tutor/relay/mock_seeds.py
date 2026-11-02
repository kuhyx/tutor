# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Seed bank of "what does this print" snippets (keys come from running them)."""

from __future__ import annotations

from typing import Any, Final

type Seed = dict[str, Any]
SEEDS: Final[list[Seed]] = [
    {
        "topic": "mutable default",
        "code": "def add(x, acc=[]):\n    acc.append(x)\n    return acc\n\n"
        "add(1)\nprint(add(2))",
        "wrong": ["[2]", "[1]", "[2, 1]"],
    },
    {
        "topic": "slicing",
        "code": "s = 'abcdefg'\nprint(s[1:6:2], s[::-3])",
        "wrong": ["ace gda", "bdf geb", "bdf ged"],
    },
    {
        "topic": "integer division",
        "code": "print(-7 // 2, -7 % 2, 7 // -2)",
        "wrong": ["-3 -1 -3", "-4 1 -3", "-3 1 -4"],
    },
    {
        "topic": "rounding",
        "code": "print(round(2.5), round(3.5), round(-0.5))",
        "wrong": ["3 4 -1", "2 4 -1", "3 4 0"],
    },
    {
        "topic": "list aliasing",
        "code": "a = [[0] * 2] * 2\na[0][0] = 1\nprint(a)",
        "wrong": ["[[1, 0], [0, 0]]", "[[0, 0], [1, 0]]", "[[1, 1], [0, 0]]"],
    },
    {
        "topic": "closures",
        "code": "fs = [lambda: i for i in range(3)]\nprint([f() for f in fs])",
        "wrong": ["[0, 1, 2]", "[0, 0, 0]", "[1, 1, 1]"],
    },
    {
        "topic": "sort stability",
        "code": "w = ['bb', 'a', 'cc', 'd']\nprint(sorted(w, key=len, reverse=True))",
        "wrong": [
            "['cc', 'bb', 'd', 'a']",
            "['a', 'd', 'bb', 'cc']",
            "['bb', 'cc', 'd', 'a']",
        ],
    },
    {
        "topic": "dict methods",
        "code": "d = {'a': 1}\nd.setdefault('a', 5)\nd.setdefault('b', 7)\nprint(d)",
        "wrong": ["{'a': 5, 'b': 7}", "{'a': 1}", "{'b': 7, 'a': 1}"],
    },
    {
        "topic": "string methods",
        "code": "print('a,b,,c'.split(','), 'x  y'.split(' '))",
        "wrong": [
            "['a', 'b', 'c'] ['x', 'y']",
            "['a', 'b', '', 'c'] ['x', 'y']",
            "['a', 'b', 'c'] ['x', '', 'y']",
        ],
    },
    {
        "topic": "generators",
        "code": "g = (x * x for x in range(4))\nnext(g)\nprint(sum(g), sum(g))",
        "wrong": ["14 14", "13 0", "15 0"],
    },
    {
        "topic": "boolean logic",
        "code": "print(0 or 'x', '' and 5, None or 0 or [])",
        "wrong": ["x 5 []", "0  0", "x  0"],
    },
    {
        "topic": "set operations",
        "code": "print(sorted({1, 2, 3} ^ {2, 3, 4}), len({1, 2} | {2, 3}))",
        "wrong": ["[1, 4] 4", "[2, 3] 3", "[1, 2, 3, 4] 3"],
    },
    {
        "topic": "tuple unpacking",
        "code": "a, *b, c = range(5)\nprint(a, b, c)",
        "wrong": ["0 [1, 2, 3] 3", "0 [1, 2, 3, 4] 4", "0 (1, 2, 3) 4"],
    },
    {
        "topic": "f-string format",
        "code": "n = 1234.5678\nprint(f'{n:,.1f}|{n:>10.2f}|{7:03d}')",
        "wrong": [
            "1,234.6|   1234.57|7",
            "1234.6|1234.57|007",
            "1,234.5|  1234.57|007",
        ],
    },
    {
        "topic": "scope",
        "code": "x = 1\ndef f():\n    x = 2\n    def g():\n        nonlocal x\n"
        "        x += 1\n    g()\n    return x\n\nprint(f(), x)",
        "wrong": ["2 1", "3 3", "2 2"],
    },
    {
        "topic": "comprehension",
        "code": "print({k: v for k, v in zip('abc', [1, 2])}, "
        "[i for i in range(10) if i % 3 == 0][-1])",
        "wrong": [
            "{'a': 1, 'b': 2, 'c': None} 9",
            "{'a': 1, 'b': 2} 6",
            "{'a': 1, 'b': 2, 'c': 3} 9",
        ],
    },
]
