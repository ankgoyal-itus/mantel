"""How the API is started: the port guard, and where reload is allowed.

The lesson behind these: once com.mantel.api owns :8000, `make dev` used to lose
the port in silence and every new prompt looked like it had never landed.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

import pytest
import uvicorn

from mantel_api import __main__ as entrypoint
from mantel_api.paths import repo_root

PORT_CHECK = repo_root() / "deploy" / "port-check.sh"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class TestThePortGuard:
    def test_it_says_nothing_about_a_free_port(self) -> None:
        result = subprocess.run(
            [str(PORT_CHECK), str(free_port())], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0
        assert result.stderr == ""

    def test_it_refuses_and_names_who_holds_the_port(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = int(sock.getsockname()[1])
            result = subprocess.run(
                [str(PORT_CHECK), str(port)], capture_output=True, text=True, check=False
            )

        assert result.returncode == 1
        assert f":{port} is already in use" in result.stderr
        # The test process is the one holding it, so it must be named.
        assert str(os.getpid()) in result.stderr


class TestReloadScope:
    @pytest.fixture(autouse=True)
    def quiet(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
        """Capture uvicorn's arguments; never read the real .env in a test."""
        captured: dict[str, object] = {}
        monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: captured.update(kw))
        monkeypatch.setattr(entrypoint, "load_dotenv", lambda *a, **kw: None)
        return captured

    def test_the_service_runs_without_a_reloader(
        self, quiet: dict[str, object], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MANTEL_RELOAD", raising=False)
        entrypoint.main()

        assert quiet["reload"] is False
        assert quiet["reload_dirs"] is None

    def test_dev_reloads_on_the_package_only(
        self, quiet: dict[str, object], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MANTEL_RELOAD", "1")
        entrypoint.main()

        assert quiet["reload"] is True
        watched = quiet["reload_dirs"]
        assert isinstance(watched, list)
        assert watched == [str(Path(entrypoint.__file__).resolve().parent)]

        # content/ must not be watched: a parent-mode save would otherwise
        # restart the API and drop the session mid-edit.
        assert not any(Path(directory).name == "content" for directory in watched)
