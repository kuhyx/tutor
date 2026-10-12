# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Subject profiles: the subject-specific words of the tutor's rules.

``prompt_rules.TEMPLATE`` is subject-neutral; a profile fills its slots.
``subjects/automation/profile.json`` (repo seed, copied to the data dir by
``migrate``) holds the original PLC wording verbatim. A generated subject's
profile comes from the plan draft (:func:`generated`): its domain, an example
prerequisite chain, concept names, an analogy and picture search terms.
Diagrams are code-drawn circuits (schemdraw), so only an electrical subject
gets them; every other profile says ``diagram`` is always null, and the
engine drops one anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
import functools
import json
from pathlib import Path
from typing import Any, Final

SLOTS: Final = (
    "domain",
    "background",
    "history",
    "prereq_example",
    "drill_example",
    "visuals",
    "check_rule",
    "concepts",
    "specifics",
    "textbook",
    "analogy",
    "neutral_example",
)
MAX_SLOT: Final = 8000
AUTOMATION_FILE: Final = (
    Path(__file__).resolve().parents[2] / "subjects" / "automation" / "profile.json"
)
# Schema of the "profile" part of a plan draft (``planner``).
PROFILE_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "background": {"type": "string"},
        "prereq_chain": {"type": "string"},
        "concepts": {"type": "array", "items": {"type": "string"}},
        "analogy": {"type": "string"},
        "image_terms": {"type": "array", "items": {"type": "string"}},
        "electrical": {"type": "boolean"},
    },
    "required": ["domain", "background", "prereq_chain", "concepts", "analogy"],
    "additionalProperties": False,
}
_VISUALS: Final = (
    "Pictures expose the core idea, and the learner has likely never looked "
    "closely at these things. A turn that introduces or explains a physical "
    "object, a part, a mechanism or a visual layout SHOULD request at least "
    "one image in `images`; there is no cap. That includes the first diagnose "
    'turn: a picture can be the question ("what do you think this is?"). A '
    "turn with nothing new to look at (a check, a recall question, a "
    "correction) may have none. An image already shown this session is not "
    "repeated; refer back to it, but only when it shows exactly the new thing. "
    'Each `images` entry is {{"terms": [...]}}: up to 3 alternative search terms '
    "for the SAME picture, best first, in genuinely different wording (a "
    "synonym, the plural, a part name); the app uses the first that finds a "
    "picture you approve once you have seen it. Commons matches whole words "
    "in file titles, so use the object's usual name in 1-3 plain words{terms}. "
    "You have not seen a picture when you request it, so the `message` of "
    "that turn must not mention pictures at all (not even that some are "
    "coming) and must read complete without one, and so must its `questions`; "
    "if the search fails, that text is sent as is. The app then shows you the "
    "pictures it found; only then do you keep or drop each one, add what is "
    "actually visible in it and, if you like, reword a question to point at "
    "it. Never describe a picture you have not seen, and never guess "
    '("should show", "probably"). {diagram} [Diagrams and pictures for the '
    "core idea]"
)
_NO_DIAGRAM: Final = (
    "This subject has no diagrams: `diagram` is always null, and you never "
    "draw ASCII art or SVG."
)
_DIAGRAM: Final = (
    "A DIAGRAM IS REQUIRED on the turn that first explains how the parts of a "
    "circuit connect: that turn MUST set `diagram`. Circuits go in `diagram` "
    "(never draw ASCII or SVG yourself); the app renders them. Tell the "
    "learner what to look for. Diagram labels: 1-3 words each."
)


@dataclass(frozen=True)
class Profile:
    """A subject's slot texts and whether it gets circuit diagrams."""

    subject: str
    diagrams: bool
    slots: dict[str, str]

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Profile:
        """A stored profile; every slot must be a string under 8000 chars."""
        slots = {name: raw.get(name) for name in SLOTS}
        bad = [
            n for n, v in slots.items() if not isinstance(v, str) or len(v) > MAX_SLOT
        ]
        if bad:
            msg = f"profile slots missing or too long: {bad}"
            raise ValueError(msg)
        return cls(
            subject=str(raw.get("subject", "")),
            diagrams=raw.get("diagrams") is True,
            slots={n: str(v) for n, v in slots.items()},
        )

    def to_json(self) -> dict[str, Any]:
        """The stored shape (``profile.json``)."""
        return {"subject": self.subject, "diagrams": self.diagrams, **self.slots}


@functools.cache
def automation() -> Profile:
    """The PLC / industrial automation profile (the repo seed)."""
    return Profile.from_json(json.loads(AUTOMATION_FILE.read_text(encoding="utf-8")))


def _quoted(items: object, limit: int) -> list[str]:
    if not isinstance(items, list):
        return []
    clean = [" ".join(str(i).split())[:60] for i in items if str(i).strip()]
    return [f'"{c}"' for c in clean[:limit]]


def _line(raw: dict[str, Any], key: str, limit: int = 300) -> str:
    return " ".join(str(raw.get(key, "")).split())[:limit]


def generated(subject: str, raw: dict[str, Any]) -> Profile:
    """A profile for a new subject from the plan draft's ``profile`` object."""
    terms = _quoted(raw.get("image_terms"), 8)
    chain = _line(raw, "prereq_chain")
    analogy = _line(raw, "analogy")
    electrical = raw.get("electrical") is True
    background = _line(raw, "background", 200)
    background = background[:1].lower() + background[1:]
    visuals = _VISUALS.format(
        terms=f"; these suit this subject: {', '.join(terms)}" if terms else "",
        diagram=_DIAGRAM if electrical else _NO_DIAGRAM,
    )
    slots = {
        "domain": _line(raw, "domain", 200) or subject.replace("-", " "),
        "background": background or "assume NO background in this subject",
        "history": "",
        "prereq_example": f" (for example {chain})" if chain else "",
        "drill_example": "",
        "visuals": visuals,
        "check_rule": (
            ' No design tasks, no scenarios, no "predict what goes wrong", no '
            "extra lines on top of the answer."
        ),
        "concepts": ", ".join(_quoted(raw.get("concepts"), 8)) or '"key term"',
        "specifics": "numbers, names, dates",
        "textbook": "Basic textbook facts you may teach directly",
        "analogy": "concrete everyday analogies"
        + (f" ({analogy}, say where they break)" if analogy else ""),
        "neutral_example": "",
    }
    return Profile(subject=subject, diagrams=electrical, slots=slots)
