"""What the About section says about the machine the API runs on.

Both answers are read, never assumed, and neither can fail: the About page is
where a parent goes when something is already wrong, so it must not be one
more thing that breaks.
"""

from __future__ import annotations

import re
import socket
import subprocess

#: The label `make install-service` gives the launchd agent.
LAUNCHD_LABEL = "com.mantel.api"


def lan_address() -> str:
    """The address the other iPad would use to reach this machine.

    A UDP socket "connected" to a private address sends nothing; it only asks
    the kernel which interface would carry the traffic, which is the one the
    iPads are on. 127.0.0.1 when there is no network at all.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def lan_url(port: int | None) -> str:
    host = lan_address()
    return f"http://{host}:{port}/" if port and port != 80 else f"http://{host}/"


def launchd_status(label: str = LAUNCHD_LABEL) -> str:
    """One line on whether the API is running as the login agent.

    `launchctl list <label>` prints the job's dictionary when it is loaded and
    fails when it is not. Off a Mac — Docker, CI — there is no launchctl, and
    that is said rather than treated as an error.
    """
    try:
        done = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except FileNotFoundError:
        return "launchd not available here"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"could not ask launchd: {type(exc).__name__}"
    if done.returncode != 0:
        return f"{label} not loaded"
    pid = re.search(r'"PID"\s*=\s*(\d+)', done.stdout)
    if pid:
        return f"{label} running (pid {pid.group(1)})"
    status = re.search(r'"LastExitStatus"\s*=\s*(-?\d+)', done.stdout)
    last = f", last exit {status.group(1)}" if status else ""
    return f"{label} loaded, not running{last}"
