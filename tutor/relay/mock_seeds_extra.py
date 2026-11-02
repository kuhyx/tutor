# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Further "what does this print" seeds; the key is always the real run."""

from __future__ import annotations

from typing import Final

from tutor.relay.mock_seeds_more import Seed, seed

EXTRA: Final[list[Seed]] = [
    seed(
        "dict pop order",
        "d = {'x': 1, 'y': 2}\nd.pop('x')\nd['x'] = 3\nprint(list(d))",
        "['x', 'y']",
        "['y']",
        "['x']",
    ),
    seed(
        "dict get",
        "d = {'a': 0}\nprint(d.get('a', 5), d.get('b', 5), d.get('b'))",
        "5 5 None",
        "0 5 0",
        "0 None None",
    ),
    seed(
        "string slicing",
        "s = 'abcdef'\nprint(s[2:], s[:-2], s[-3:-1], s[::2])",
        "cdef abcde de ace",
        "cdef abcd ef ace",
        "cdef abcd de bdf",
    ),
    seed(
        "slice out of range",
        "s = 'abc'\nprint(s[1:100], repr(s[5:]), repr(s[-10:2]))",
        "bc IndexError 'ab'",
        "bc None 'ab'",
        "bc '' 'abc'",
    ),
    seed(
        "string immutable",
        "s = 'hello'\nt = s.upper()\nprint(s, t, s.replace('l', 'L', 1))",
        "HELLO HELLO heLlo",
        "hello HELLO heLLo",
        "hello HELLO HELLO",
    ),
    seed(
        "is vs ==",
        "a = [1]\nb = [1]\nc = a\nprint(a == b, a is b, a is c)",
        "True True True",
        "False False True",
        "True False False",
    ),
    seed(
        "is none",
        "x = []\nprint(x == None, x is None, not x)",
        "True False True",
        "False True False",
        "False False False",
    ),
    seed(
        "try finally return",
        "def f():\n    try:\n        return 'try'\n    finally:\n        "
        "print('fin')\n\nprint(f())",
        "try",
        "fin",
        "try\nfin",
    ),
    seed(
        "finally overrides",
        "def f():\n    try:\n        return 1\n    finally:\n        return "
        "2\n\nprint(f())",
        "1",
        "None",
        "1 2",
    ),
    seed(
        "except order",
        "try:\n    {}['k']\nexcept LookupError:\n    print('lookup')\nexcept "
        "KeyError:\n    print('key')\nelse:\n    print('else')\nfinally:\n   "
        " print('done')",
        "key\ndone",
        "lookup",
        "lookup\nelse\ndone",
    ),
    seed(
        "try else",
        "try:\n    x = int('7')\nexcept ValueError:\n    print('bad')\n"
        "else:\n    print('ok', x)\nfinally:\n    print('end')",
        "ok 7",
        "bad\nend",
        "ok 7\nend\nbad",
    ),
    seed(
        "sort in place",
        "xs = [3, 1, 2]\nr = xs.sort()\nprint(r, xs, sorted(xs, reverse=True))",
        "[1, 2, 3] [1, 2, 3] [3, 2, 1]",
        "None [3, 1, 2] [3, 2, 1]",
        "None [1, 2, 3] [1, 2, 3]",
    ),
    seed(
        "list multiply",
        "a = [0] * 3\na[1] = 5\nb = [[0]] * 2\nb[0].append(1)\nprint(a, b)",
        "[0, 5, 0] [[0, 1], [0]]",
        "[5, 5, 5] [[0, 1], [0, 1]]",
        "[0, 5, 0] [[0], [0]]",
    ),
    seed(
        "list slice assign",
        "xs = [1, 2, 3, 4]\nxs[1:3] = [9]\nprint(xs, xs[::-1])",
        "[1, 9, 3, 4] [4, 3, 9, 1]",
        "[1, 9, 9, 4] [4, 9, 9, 1]",
        "[1, 9, 4] [1, 9, 4]",
    ),
    seed(
        "star args",
        "def f(*a, **k):\n    return len(a), sorted(k)\n\nprint(f(1, 2, x=3, "
        "y=4), f())",
        "(4, []) (0, [])",
        "(2, {'x', 'y'}) (0, set())",
        "(2, ['x', 'y']) (0, None)",
    ),
    seed(
        "tuple augmented",
        "t = (1, 2)\nu = t\nt += (3,)\nprint(t, u)",
        "(1, 2, 3) (1, 2, 3)",
        "(1, 2) (1, 2)",
        "(1, 2) (1, 2, 3)",
    ),
    seed(
        "comprehension scope",
        "x = 'out'\nr = [x for x in range(3)]\nprint(x, r)",
        "2 [0, 1, 2]",
        "out [1, 2, 3]",
        "2 [1, 2, 3]",
    ),
    seed(
        "truthiness",
        "print(bool([]), bool([0]), bool(''), bool(' '), bool(0.0))",
        "False False False True False",
        "True True False True False",
        "False True False False False",
    ),
    seed(
        "chained compare",
        "print(1 < 2 < 3, 3 > 2 > 2, 1 == 1 != 2)",
        "True True True",
        "False False True",
        "True False False",
    ),
    seed(
        "string multiply",
        "print('ab' * 2 + 'c' * 0, 'x'.join(['1', '2', '3']), 'a-b'.split('-', 1))",
        "ab 1x2x3 ['a', 'b']",
        "abab x1x2x3 ['a-b']",
        "abab 1x2x3 ['a-b']",
    ),
    seed(
        "set order free",
        "s = {3, 1, 2, 3}\nprint(sorted(s), len(s), 2 in s)",
        "[1, 2, 3, 3] 4 True",
        "[1, 2, 3] 3 False",
        "[1, 2, 3] 4 True",
    ),
    seed(
        "int string",
        "print('3' + '4', int('3') + int('4'), '3' * 3, int('1_0'))",
        "7 7 9 10",
        "34 7 9 10",
        "34 7 333 ValueError",
    ),
    seed(
        "while else",
        "n = 0\nwhile n < 3:\n    n += 1\n    if n == 5:\n        break\n"
        "else:\n    print('else', n)",
        "3",
        "else 5",
        "else 4",
    ),
    seed(
        "enumerate zip",
        "print(list(enumerate('ab', 1)), list(zip('abc', [1, 2])))",
        "[(0, 'a'), (1, 'b')] [('a', 1), ('b', 2)]",
        "[(1, 'a'), (2, 'b')] [('a', 1), ('b', 2), ('c', None)]",
        "[(1, 'a'), (2, 'b')] [('a', 1), ('b', 2), ('c', 3)]",
    ),
]
