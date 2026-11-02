# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""More "what does this print" seeds; the key is always the real run."""

from __future__ import annotations

from typing import Any, Final

type Seed = dict[str, Any]


def seed(topic: str, code: str, *wrong: str) -> Seed:
    """One seed: its snippet and three plausible wrong outputs."""
    return {"topic": topic, "code": code, "wrong": list(wrong)}


MORE: Final[list[Seed]] = [
    seed(
        "mutable alias",
        "a = [1, 2]\nb = a\nb.append(3)\nprint(a, a is b)",
        "[1, 2] True",
        "[1, 2, 3] False",
        "[1, 2] False",
    ),
    seed(
        "mutable arg",
        "def f(xs):\n    xs += [9]\n    xs = xs + [8]\n    return xs\n\nv = "
        "[1]\nprint(f(v), v)",
        "[1, 9, 8] [1]",
        "[1, 8] [1, 9]",
        "[1, 9] [1, 9, 8]",
    ),
    seed(
        "tuple of list",
        "t = ([1], 2)\nt[0].append(5)\nprint(t)",
        "([1], 2)",
        "TypeError",
        "([5], 2)",
    ),
    seed(
        "default arg",
        "def f(n, seen=set()):\n    seen.add(n)\n    return len(seen)\n\n"
        "f(1)\nf(2)\nprint(f(2))",
        "1",
        "3",
        "2 2",
    ),
    seed(
        "default arg none",
        "def f(n, acc=None):\n    acc = acc or []\n    acc.append(n)\n    "
        "return acc\n\nf(1)\nprint(f(2), f(3, [7]))",
        "[1, 2] [7, 3]",
        "[2] [3]",
        "[1, 2] [3]",
    ),
    seed(
        "default evaluated once",
        "x = 1\ndef f(a=x):\n    return a\n\nx = 2\nprint(f(), f(5))",
        "2 5",
        "1 1",
        "2 2",
    ),
    seed(
        "late binding",
        "fs = []\nfor i in range(3):\n    fs.append(lambda: i * 10)\n"
        "print([f() for f in fs])",
        "[0, 10, 20]",
        "[10, 10, 10]",
        "[0, 0, 0]",
    ),
    seed(
        "bound closure",
        "fs = [lambda i=i: i * 10 for i in range(3)]\nprint([f() for f in fs])",
        "[20, 20, 20]",
        "[0, 10, 20, 30]",
        "[10, 20, 30]",
    ),
    seed(
        "global scope",
        "n = 5\ndef f():\n    global n\n    n += 1\n    return n\n\nprint(f(), n)",
        "6 5",
        "5 5",
        "5 6",
    ),
    seed(
        "scope shadow",
        "x = 'g'\ndef f():\n    print(x)\n    x = 'l'\n\ntry:\n    f()\n"
        "except UnboundLocalError:\n    print('unbound')",
        "g",
        "l",
        "g unbound",
    ),
    seed(
        "copy vs deepcopy",
        "import copy\na = [[1], [2]]\nb = copy.copy(a)\nc = "
        "copy.deepcopy(a)\na[0].append(9)\nprint(b[0], c[0])",
        "[1] [1]",
        "[1, 9] [1, 9]",
        "[1] [1, 9]",
    ),
    seed(
        "shallow copy",
        "a = [1, [2, 3]]\nb = a[:]\nb[0] = 99\nb[1][0] = 77\nprint(a)",
        "[99, [77, 3]]",
        "[1, [2, 3]]",
        "[99, [2, 3]]",
    ),
    seed(
        "dict copy",
        "d = {'k': [1]}\ne = dict(d)\ne['k'].append(2)\ne['z'] = 0\nprint(d)",
        "{'k': [1, 2], 'z': 0}",
        "{'k': [1]}",
        "{'k': [1], 'z': 0}",
    ),
    seed(
        "generator exhausted",
        "g = (n for n in [1, 2, 3])\nprint(list(g), list(g))",
        "[1, 2, 3] [1, 2, 3]",
        "[1, 2, 3] [1]",
        "[] []",
    ),
    seed(
        "generator function",
        "def gen():\n    yield 1\n    return 5\n    yield 2\n\nprint(list(gen()))",
        "[1, 5]",
        "[1, 2]",
        "[5]",
    ),
    seed(
        "lazy generator",
        "def g():\n    print('a')\n    yield 1\n\nx = g()\nprint('b')\nnext(x)",
        "a\nb",
        "b",
        "a",
    ),
    seed(
        "next with default",
        "it = iter([10])\nprint(next(it), next(it, 'end'), next(it, 'end'))",
        "10 10 end",
        "10 None None",
        "StopIteration",
    ),
    seed(
        "floor div negatives",
        "print(-9 // 4, -9 % 4, 9 // -4, 9 % -4)",
        "-2 -1 -2 1",
        "-2 1 -2 -1",
        "-2 3 -2 -3",
    ),
    seed(
        "divmod",
        "print(divmod(-7, 3), divmod(7, -3), divmod(7.5, 2))",
        "(-2, -1) (-2, 1) (3.0, 1.5)",
        "(-3, 2) (-2, 1) (3.0, 1.5)",
        "(-3, 2) (-3, -2) (3, 1.5)",
    ),
    seed(
        "true division",
        "print(7 / 2, 8 / 2, 7 // 2.0, 2 ** -1)",
        "3.5 4 3.0 0.5",
        "3 4.0 3 0",
        "3.5 4.0 3 0.5",
    ),
    seed(
        "bankers rounding",
        "print(round(0.5), round(1.5), round(2.5), round(-1.5))",
        "1 2 3 -2",
        "1 2 3 -1",
        "0 2 3 -2",
    ),
    seed(
        "round digits",
        "print(round(2.675, 2), round(1234, -2), round(0.125, 2))",
        "2.68 1200 0.13",
        "2.68 1230 0.12",
        "2.67 1200 0.13",
    ),
    seed(
        "float equality",
        "print(0.1 + 0.2 == 0.3, abs(0.1 + 0.2 - 0.3) < 1e-9)",
        "True True",
        "False False",
        "True False",
    ),
    seed(
        "dict order",
        "d = {}\nd['b'] = 1\nd['a'] = 2\nd['b'] = 3\nprint(list(d.items()))",
        "[('a', 2), ('b', 3)]",
        "[('b', 1), ('a', 2)]",
        "[('a', 2), ('b', 1)]",
    ),
]
