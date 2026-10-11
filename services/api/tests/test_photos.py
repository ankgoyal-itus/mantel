"""Photos, read-only (0.3.0): Mantel reads Memories' folder and serves the same list and files
to its iPads; the old upload and delete routes answer 410 with Memories' address."""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mantel_api.photos import PhotoIndex, PhotoStore, write_sample_album


def jpeg(colour: str = "red") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 48), colour).save(out, format="JPEG")
    return out.getvalue()


@pytest.fixture
def folder(photos: PhotoStore) -> Path:
    """The `photos` fixture's folder, filled the way Memories fills it."""
    write_sample_album(photos.directory, [jpeg("red"), jpeg("blue")])
    return photos.directory


def _listing(directory: Path) -> dict[str, float]:
    return {str(p.relative_to(directory)): p.stat().st_mtime for p in directory.rglob("*")}


def test_lists_and_serves_what_memories_wrote(client: TestClient, folder: Path) -> None:
    listed = client.get("/api/photos").json()
    assert len(listed) == 2 and all(p["bytes"] > 0 for p in listed)
    first = listed[0]
    assert first["url"] == f"/api/photos/{first['id']}.jpg"
    image = client.get(first["url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert client.get("/api/photos/0000000000000000.jpg").status_code == 404


def test_picks_up_a_change_memories_makes(photos: PhotoStore, folder: Path) -> None:
    assert len(photos.photos()) == 2
    index = PhotoIndex.model_validate_json((folder / "index.json").read_text())
    index.photos.pop()
    (folder / "index.json").write_text(index.model_dump_json())
    stamp = (folder / "index.json").stat().st_mtime + 5
    os.utime(folder / "index.json", (stamp, stamp))
    assert len(photos.photos()) == 1


def test_a_wrecked_index_keeps_the_last_good_list_and_is_left_alone(
    photos: PhotoStore, folder: Path
) -> None:
    assert len(photos.photos()) == 2
    (folder / "index.json").write_text("{ not json")
    stamp = (folder / "index.json").stat().st_mtime + 5
    os.utime(folder / "index.json", (stamp, stamp))
    assert len(photos.photos()) == 2
    assert (folder / "index.json").read_text() == "{ not json"  # not renamed: not ours


def test_reading_never_writes(client: TestClient, folder: Path) -> None:
    before = _listing(folder)
    for photo in client.get("/api/photos").json():
        client.get(photo["url"])
    assert _listing(folder) == before


def test_no_folder_is_no_photos(tmp_path: Path) -> None:
    assert PhotoStore(tmp_path / "nothing").photos() == []


def test_uploads_and_deletes_moved_to_memories(
    client: TestClient, folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resp = client.post(
        "/api/photos",
        files=[("file", ("a.jpg", jpeg(), "image/jpeg"))],
        headers={"X-Mantel-Token": "anything"},
    )
    assert resp.status_code == 410
    assert resp.json()["moved_to"] == "http://albert.local:8002/api/photos"
    first = client.get("/api/photos").json()[0]["id"]
    gone = client.delete(f"/api/photos/{first}")
    assert gone.status_code == 410 and "Memories" in gone.json()["detail"]
    assert len(client.get("/api/photos").json()) == 2  # nothing deleted

    monkeypatch.setenv("MANTEL_MEMORIES_URL", "http://memories.test:9002/")
    moved = client.post("/api/photos", files=[("file", ("a.jpg", jpeg(), "image/jpeg"))])
    assert moved.json()["moved_to"] == "http://memories.test:9002/api/photos"


def test_photos_dir_setting(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from mantel_api.paths import photos_dir

    monkeypatch.setenv("MANTEL_PHOTOS_DIR", str(tmp_path / "shared"))
    assert photos_dir() == (tmp_path / "shared").resolve()
