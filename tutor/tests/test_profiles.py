# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Subject profiles: automation is today's prompt byte for byte; others generic."""

from __future__ import annotations

from pathlib import Path

import pytest

from tutor.curriculum import profiles
from tutor.prompt_rules import render_system

FROZEN = Path(__file__).parent / "data" / "automation_system.txt"


def test_automation_profile_reproduces_the_plc_prompt_exactly() -> None:
    assert render_system(profiles.automation()) == FROZEN.read_text(encoding="utf-8")
    assert profiles.automation().diagrams


def test_profile_round_trip_and_validation() -> None:
    auto = profiles.automation()
    assert profiles.Profile.from_json(auto.to_json()) == auto
    with pytest.raises(ValueError, match="domain"):
        profiles.Profile.from_json({**auto.to_json(), "domain": 3})


def test_generated_profile_is_subject_neutral() -> None:
    raw = {
        "domain": "how cars work (engine, brakes)",
        "background": "Assume NO mechanical background",
        "prereq_chain": "force, pressure, piston",
        "concepts": ["piston", "  ", "crankshaft"],
        "analogy": "a bicycle pump",
        "image_terms": ["piston", "disc brake"],
    }
    prof = profiles.generated("car", raw)
    text = render_system(prof)
    assert not prof.diagrams
    assert "automation" not in text.lower()
    assert "PLC" not in text
    assert "but assume NO mechanical background." in text
    assert '"piston", "crankshaft"' in text
    assert 'these suit this subject: "piston", "disc brake"' in text
    assert "`diagram` is always null" in text
    assert "(for example force, pressure, piston)" in text
    assert "(a bicycle pump, say where they break)" in text


def test_generated_profile_defaults_and_electrical() -> None:
    prof = profiles.generated("ohm-law", {"electrical": True, "concepts": "x"})
    text = render_system(prof)
    assert prof.diagrams
    assert "A DIAGRAM IS REQUIRED" in text
    assert "for ohm law." in text
    assert "assume NO background in this subject" in text
    assert '"key term"' in text
    assert "concrete everyday analogies." in text
