"""How many days in a row a kid did everything the day asked of them.

Computed from the claims table every time it is read, never stored. A stored
streak is a number that has to be maintained, and the day it disagrees with
the claims behind it is the day a child is told they lost a run they did not.

Two rules make it fair rather than merely strict:

* **A day that asked for nothing cannot break it.** Sunday requires no
  homework, so a Sunday is stepped over rather than counted against.
* **Today is only counted once it is finished.** A streak checked at
  breakfast would be broken by homework that is not due until the evening,
  so today extends a run but never ends one.

Only the tasks done every day count: the day's own list (weekdays, or the
weekend's on a Saturday, a Sunday or a day off school), less anything done
once a week. Homework spread over three evenings is a week's job, and the
evenings it was not touched are not days the child failed.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import date as Date
from datetime import timedelta

from .models import TaskItem, Tasks
from .today import tasks_on

#: How far back a run is ever traced. Longer than any streak anyone will hold
#: and short enough that the query stays a glance at an index.
MAX_LOOKBACK_DAYS = 90

def required_on(
    tasks: Tasks, kid_id: str, day: Date, *, school_day: bool
) -> list[TaskItem]:
    """The every-day tasks that day asked for. Empty means it asked nothing."""
    return [task for task in tasks_on(tasks, kid_id, day, school_day) if task.every == "day"]


def approved_by_day(
    connection: sqlite3.Connection, kid_id: str, since: Date
) -> dict[Date, set[str]]:
    """Which task ids were approved on each day, from `since` onward."""
    rows = connection.execute(
        """
        SELECT date, task_id FROM claims
        WHERE kid_id = ? AND status = 'approved' AND date >= ?
        """,
        (kid_id, since.isoformat()),
    )
    found: dict[Date, set[str]] = {}
    for row in rows:
        try:
            day = Date.fromisoformat(str(row["date"]))
        except ValueError:  # noqa: PERF203 - a bad row must not lose the streak
            continue
        found.setdefault(day, set()).add(str(row["task_id"]))
    return found


def current_streak(
    connection: sqlite3.Connection,
    tasks: Tasks,
    kid_id: str,
    today: Date,
    is_school_day: Callable[[Date], bool],
    *,
    lookback: int = MAX_LOOKBACK_DAYS,
) -> int:
    """The run of complete days ending today, counting back."""
    earliest = today - timedelta(days=lookback)
    approved = approved_by_day(connection, kid_id, earliest)

    streak = 0
    for offset in range(lookback + 1):
        day = today - timedelta(days=offset)
        required = required_on(tasks, kid_id, day, school_day=is_school_day(day))
        if not required:
            continue  # the day asked nothing of anyone
        done = approved.get(day, set())
        if all(task.id in done for task in required):
            streak += 1
            continue
        # Today is allowed to be unfinished: it is not over yet.
        if offset == 0:
            continue
        break
    return streak
