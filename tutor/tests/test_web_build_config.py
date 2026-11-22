# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A release web build must carry the real Firebase identifiers.

2026-11-22 15:09: a deploy from a fresh worktree shipped a bundle compiled
from the ``--placeholder`` ``firebase_local.dart`` that ``e2e_sandbox.sh``
writes when the file is missing. With empty identifiers the app paints only
its "no Firebase identifiers" error glyph on every route, so the lock's learn
button opened a window with no lesson and no plan. ``check_web_build_config.sh``
is what ``deploy.sh`` (the source file, before the build) and
``tutor_deploy.sh`` (the bundle, before the copy) run to refuse that.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
CHECK = SCRIPTS / "check_web_build_config.sh"
URL = "https://example-default-rtdb.europe-west1.firebasedatabase.app"

REAL = f"""const kFirebaseApiKey = 'k';
const kFirebaseDatabaseUrl =
    '{URL}';
const kFirebaseSyncUid = 'u';
"""
PLACEHOLDER = """const kFirebaseApiKey = '';
const kFirebaseDatabaseUrl = '';
const kFirebaseSyncUid = '';
"""


def _app(tmp_path: Path, local: str | None, bundle: str | None) -> Path:
    """An ``app/`` dir with the given config file and web bundle (None: absent)."""
    app = tmp_path / "app"
    (app / "lib/config").mkdir(parents=True)
    (app / "build/web").mkdir(parents=True)
    if local is not None:
        (app / "lib/config/firebase_local.dart").write_text(local, encoding="utf-8")
    if bundle is not None:
        (app / "build/web/main.dart.js").write_text(bundle, encoding="utf-8")
    return app


def _check(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CHECK), *map(str, args)], capture_output=True, text=True, check=False
    )


def test_a_placeholder_config_is_refused(tmp_path: Path) -> None:
    done = _check(_app(tmp_path, PLACEHOLDER, "x"))
    assert done.returncode == 1
    assert "write_firebase_config.dart" in done.stderr


def test_a_missing_config_is_refused(tmp_path: Path) -> None:
    assert _check(_app(tmp_path, None, "x")).returncode == 1


def test_a_bundle_built_without_the_identifiers_is_refused(tmp_path: Path) -> None:
    """The 15:09 deploy: the file is real again but the bundle was built empty."""
    done = _check(_app(tmp_path, REAL, "no url in here"))
    assert done.returncode == 1
    assert "bundle" in done.stderr


def test_a_missing_bundle_is_refused(tmp_path: Path) -> None:
    assert _check(_app(tmp_path, REAL, None)).returncode == 1


def test_a_real_config_and_a_bundle_carrying_it_pass(tmp_path: Path) -> None:
    assert _check(_app(tmp_path, REAL, f'x"{URL}"y')).returncode == 0


def test_source_only_skips_the_bundle(tmp_path: Path) -> None:
    """``deploy.sh`` asks before the build, when no bundle exists yet."""
    real, empty = tmp_path / "real", tmp_path / "empty"
    assert _check("--source-only", _app(real, REAL, None)).returncode == 0
    assert _check("--source-only", _app(empty, PLACEHOLDER, None)).returncode == 1


def test_both_deploy_scripts_run_the_check() -> None:
    """The guard is only worth its tests if the deploy path calls it."""
    deploy = (SCRIPTS / "deploy.sh").read_text(encoding="utf-8")
    tutor_deploy = (SCRIPTS / "tutor_deploy.sh").read_text(encoding="utf-8")
    assert 'check_web_build_config.sh" --source-only' in deploy
    assert deploy.index("check_web_build_config.sh") < deploy.index("flutter build")
    release = tutor_deploy.split("copy_release() {", 1)[1].split("\n}\n", 1)[0]
    assert "check_web_build_config.sh" in release
    assert release.index("check_web_build_config.sh") < release.index("mkdir -p")
