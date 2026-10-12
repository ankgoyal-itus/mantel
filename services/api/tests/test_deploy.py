"""What Albert relies on: where the API listens, the container's shape, and where the
Mac's nightly Photos export sends its uploads. See docs/DEPLOY.md."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mantel_api.__main__ import listen_address

REPO = Path(__file__).resolve().parents[3]


def test_listens_on_every_interface_on_8000_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MANTEL_BIND", raising=False)
    monkeypatch.delenv("MANTEL_PORT", raising=False)
    assert listen_address() == ("0.0.0.0", 8000)  # noqa: S104


def test_bind_and_port_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANTEL_BIND", "127.0.0.1")
    monkeypatch.setenv("MANTEL_PORT", "8100")
    assert listen_address() == ("127.0.0.1", 8100)


def test_compose_takes_bind_port_and_home_from_the_environment() -> None:
    compose = (REPO / "docker-compose.yml").read_text()
    assert '"${MANTEL_BIND:-0.0.0.0}:${MANTEL_PORT:-8000}:8000"' in compose
    assert '"${MANTEL_HOME:-./home}:/app/home"' in compose
    assert 'user: "${MANTEL_UID:-10001}:${MANTEL_GID:-10001}"' in compose


def test_image_runs_as_a_non_root_user_and_checks_its_own_port() -> None:
    dockerfile = (REPO / "Dockerfile").read_text()
    assert "\nUSER mantel\n" in dockerfile
    assert "MANTEL_PORT" in dockerfile.split("HEALTHCHECK", 1)[1]


def test_nothing_mac_only_on_the_container_path() -> None:
    """The image carries services/api/mantel_api only. launchctl is asked politely and
    absence is reported (system.launchd_status); nothing else may need macOS."""
    for path in (REPO / "services" / "api" / "mantel_api").rglob("*.py"):
        text = path.read_text()
        for word in ("osascript", "sips ", "ipconfig", "scutil", "/Users/", "Photos.app"):
            assert word not in text, f"{path.name} uses {word}"


def _sync(tmp_path: Path, env_lines: str, **environ: str) -> str:
    (tmp_path / "deploy").mkdir()
    shutil.copy(REPO / "deploy" / "photos-sync.sh", tmp_path / "deploy" / "photos-sync.sh")
    (tmp_path / ".env").write_text("MANTEL_UPLOAD_TOKEN=test-token\n" + env_lines)
    env = {k: v for k, v in os.environ.items() if not k.startswith("MANTEL_")}
    done = subprocess.run(
        ["sh", str(tmp_path / "deploy" / "photos-sync.sh")],
        capture_output=True,
        text=True,
        env={**env, **environ},
        timeout=30,
        check=False,
    )
    assert done.returncode == 1  # nothing answers on port 9: it stops before sending anything
    return done.stderr


def test_photos_export_address_is_a_setting(tmp_path: Path) -> None:
    assert "http://127.0.0.1:9 " in _sync(tmp_path, "MANTEL_PHOTOS_URL=http://127.0.0.1:9/\n")


def test_photos_export_environment_beats_dotenv(tmp_path: Path) -> None:
    out = _sync(
        tmp_path,
        "MANTEL_PHOTOS_URL=http://127.0.0.1:7\n",
        MANTEL_PHOTOS_URL="http://127.0.0.1:9",
    )
    assert "http://127.0.0.1:9 " in out and ":7" not in out


def test_version_names_the_release_beside_the_screens_number(client: TestClient) -> None:
    body = client.get("/api/version").json()
    assert isinstance(body["version"], int)
    assert body["release"] == (REPO / "VERSION").read_text().strip()


def test_photos_export_goes_to_memories_by_default() -> None:
    """Not run against the default: if Albert answered, the script would export the album."""
    script = (REPO / "deploy" / "photos-sync.sh").read_text()
    assert "${MANTEL_API:-http://albert.local:8002}" in script
    assert "printf 'X-Memories-Token: %s\\n' \"$TOKEN\" | curl" in script
    assert "-H @-" in script


FAKE_CURL = """#!/bin/sh
# Records every call's arguments; reads the header only when told it is on stdin.
n=$(ls "$CALLS" | wc -l | tr -d ' ')
printf '%s\\n' "$@" >"$CALLS/argv-$n"
for arg in "$@"; do
  if [ "$arg" = "@-" ]; then cat >"$CALLS/stdin-$n"; fi
done
case "$*" in
  *api/photos*) printf '{"added": ["p1"], "skipped": []}' ;;
esac
exit 0
"""


def test_photos_export_keeps_the_token_out_of_every_command_line(tmp_path: Path) -> None:
    """The process list shows argv to anyone on the Mac: the token travels on stdin only."""
    repo = tmp_path / "repo"
    (repo / "deploy").mkdir(parents=True)
    shutil.copy(REPO / "deploy" / "photos-sync.sh", repo / "deploy" / "photos-sync.sh")
    (repo / ".env").write_text("MEMORIES_UPLOAD_TOKEN=s3cret-token-value\n")
    (repo / "inbox").mkdir()
    (repo / "inbox" / "a.jpg").write_bytes(b"\xff\xd8\xff")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("curl", FAKE_CURL), ("osascript", "#!/bin/sh\necho 'error: no album'\n")):
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    calls = tmp_path / "calls"
    calls.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("MANTEL_")}
    done = subprocess.run(
        ["sh", str(repo / "deploy" / "photos-sync.sh")],
        capture_output=True,
        text=True,
        env={
            **env,
            "PATH": f"{bin_dir}:{env['PATH']}",
            "HOME": str(tmp_path),
            "CALLS": str(calls),
            "MANTEL_PHOTOS_URL": "http://memories.test:8002",
        },
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "uploaded: 1" in done.stdout and "new: 1" in done.stdout
    argvs = [p.read_text() for p in sorted(calls.glob("argv-*"))]
    stdins = [p.read_text() for p in sorted(calls.glob("stdin-*"))]
    assert len(argvs) == 2  # the health check, then one upload
    assert all("s3cret-token-value" not in a and "X-Memories-Token" not in a for a in argvs)
    assert stdins == ["X-Memories-Token: s3cret-token-value\n"]
    assert "s3cret-token-value" not in done.stdout + done.stderr
    log = (tmp_path / "Library" / "Logs" / "mantel" / "photos.log").read_text()
    assert "s3cret-token-value" not in log


def test_compose_mounts_the_photo_folder_read_only() -> None:
    compose = (REPO / "docker-compose.yml").read_text()
    assert '"${MANTEL_PHOTOS:-./home/photos}:/app/home/photos:ro"' in compose
