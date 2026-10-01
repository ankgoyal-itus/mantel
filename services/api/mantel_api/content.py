"""YAML content loading.

Every file is read and validated at startup, then again whenever anything in
content/ changes on disk. A bad file never crashes the API: the error is
logged with its path and the last good version keeps being served.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Generic, TypeVar

import yaml
from pydantic import BaseModel, ValidationError
from watchfiles import awatch

from .models import (
    ContentStatus,
    Family,
    Meals,
    MealsCatalog,
    Rewards,
    Schedule,
    Settings,
    Tasks,
)
from .paths import content_dir
from .school_events import SchoolEvents

logger = logging.getLogger("mantel_api.content")

ModelT = TypeVar("ModelT", bound=BaseModel)

_MAX_ERROR_CHARS = 200


def _summarize(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    if len(text) > _MAX_ERROR_CHARS:
        text = text[: _MAX_ERROR_CHARS - 1] + "…"
    return f"{type(exc).__name__}: {text}"


def _where(exc: Exception) -> str:
    """Line number of a YAML syntax error, when the parser knows one."""
    mark = getattr(exc, "problem_mark", None)
    if mark is None:
        return ""
    return f" (line {mark.line + 1}, column {mark.column + 1})"


class ContentFile(Generic[ModelT]):
    """One YAML file plus the last version of it that parsed cleanly."""

    def __init__(self, path: Path, model: type[ModelT]) -> None:
        self.path = path
        self.model = model
        self._last_good: ModelT | None = None
        self._error: str | None = None

    def load(self, context: dict[str, Any] | None = None) -> ModelT | None:
        """Re-read the file. On failure, log and keep the last good version."""
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
            parsed = self.model.model_validate(raw, context=context)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            self._error = _summarize(exc)
            logger.error("bad content file %s%s: %s", self.path, _where(exc), self._error)
            return self._last_good
        self._last_good = parsed
        self._error = None
        return parsed

    @property
    def current(self) -> ModelT | None:
        """The last version that parsed cleanly, without touching the disk."""
        return self._last_good

    @property
    def status(self) -> str:
        """"ok", or "error: ..." describing the most recent failed load."""
        return "ok" if self._error is None else f"error: {self._error}"


class Content:
    """The content/ directory as the API sees it."""

    def __init__(self, directory: Path | None = None) -> None:
        base = directory if directory is not None else content_dir()
        self.directory = base
        self.family: ContentFile[Family] = ContentFile(base / "family.yaml", Family)
        self.settings: ContentFile[Settings] = ContentFile(base / "settings.yaml", Settings)
        self.schedule: ContentFile[Schedule] = ContentFile(base / "schedule.yaml", Schedule)
        self.meals: ContentFile[Meals] = ContentFile(base / "meals.yaml", Meals)
        self.catalog: ContentFile[MealsCatalog] = ContentFile(
            base / "meals-catalog.yaml", MealsCatalog
        )
        self.tasks: ContentFile[Tasks] = ContentFile(base / "tasks.yaml", Tasks)
        self.rewards: ContentFile[Rewards] = ContentFile(base / "rewards.yaml", Rewards)
        self.school_events: ContentFile[SchoolEvents] = ContentFile(
            base / "school-events.yaml", SchoolEvents
        )

    def load_all(self) -> None:
        """Read every file.

        family.yaml goes first: it defines who may be referenced. The catalog
        comes before meals.yaml, which resolves dish ids against it.
        """
        family = self.family.load()
        kid_ids = {kid.id for kid in family.kids} if family else set()
        person_ids = kid_ids | ({parent.id for parent in family.parents} if family else set())
        roster: dict[str, Any] = {"kid_ids": kid_ids, "person_ids": person_ids}

        self.settings.load(roster)
        catalog = self.catalog.load()
        self.schedule.load(roster)
        self.tasks.load(roster)
        self.meals.load({"dish_names": catalog.names if catalog else {}})
        self.school_events.load()
        self.rewards.load()

    @property
    def status(self) -> ContentStatus:
        return ContentStatus(
            family=self.family.status,
            settings=self.settings.status,
            schedule=self.schedule.status,
            meals=self.meals.status,
            meals_catalog=self.catalog.status,
            tasks=self.tasks.status,
            school_events=self.school_events.status,
            rewards=self.rewards.status,
        )


#: Things under content/ that are not content. photos/ fills up from a phone,
#: and the ledger changes every time a child taps a task — neither is a reason
#: to re-read and re-validate every YAML file in the directory.
_NOT_CONTENT = ("photos", ".cache", ".backup")


def not_a_photo(_: Any, path: str) -> bool:
    """Whether a changed path under content/ is worth reloading for."""
    parts = Path(path).parts
    if any(part in _NOT_CONTENT for part in parts):
        return False
    return not Path(path).name.startswith("mantel.db")


async def watch(content: Content, stop_event: Any = None) -> None:
    """Reload everything whenever content/ changes. Runs for the app's lifetime."""
    async for changes in awatch(content.directory, stop_event=stop_event, watch_filter=not_a_photo):
        paths: Iterable[str] = sorted(path for _, path in changes)
        logger.info("content changed: %s", ", ".join(Path(p).name for p in paths))
        content.load_all()
