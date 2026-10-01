"""The photo pipeline: what goes in, what comes out, and what is refused."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mantel_api.app import create_app
from mantel_api.calendars import CalendarService
from mantel_api.content import Content
from mantel_api.photos import LONG_EDGE, PhotoError, PhotoStore, process
from mantel_api.weather import WeatherService

TOKEN = "test-token"


def landscape(width: int = 1200, height: int = 800, colour: str = "red") -> Image.Image:
    """A plain image, wider than it is tall, so orientation is visible."""
    image = Image.new("RGB", (width, height), colour)
    # A darker top-left corner, so a rotation is detectable from the pixels.
    for x in range(width // 4):
        for y in range(height // 4):
            image.putpixel((x, y), (0, 0, 0))
    return image


def as_jpeg(image: Image.Image, orientation: int | None = None) -> bytes:
    out = io.BytesIO()
    if orientation is None:
        image.save(out, format="JPEG")
    else:
        exif = Image.Exif()
        exif[274] = orientation  # Orientation
        exif[36867] = "2024:06:14 10:23:45"  # DateTimeOriginal
        image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def as_heic(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="HEIF")
    return out.getvalue()


@pytest.fixture
def store(tmp_path: Path) -> PhotoStore:
    return PhotoStore(tmp_path / "photos")


@pytest.fixture
def client(
    content: Content,
    weather: WeatherService,
    calendars: CalendarService,
    store: PhotoStore,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setenv("MANTEL_UPLOAD_TOKEN", TOKEN)
    yield TestClient(create_app(content, weather, calendars, store))


def upload(
    client: TestClient, data: bytes, name: str = "photo.jpg", token: str = TOKEN
) -> httpx.Response:
    # TestClient's methods come back untyped through the httpx shim.
    return cast(
        httpx.Response,
        client.post(
            "/api/photos",
            files=[("file", (name, data, "image/jpeg"))],
            headers={"X-Mantel-Token": token},
        ),
    )


class TestPipeline:
    def test_resizes_to_the_long_edge(self) -> None:
        jpeg, width, height, _, _ = process(as_jpeg(landscape(4032, 3024)))
        assert max(width, height) == LONG_EDGE
        assert (width, height) == (2048, 1536)
        assert Image.open(io.BytesIO(jpeg)).size == (2048, 1536)

    def test_leaves_a_small_photo_alone(self) -> None:
        _, width, height = process(as_jpeg(landscape(800, 600)))[:3]
        assert (width, height) == (800, 600)

    def test_applies_exif_orientation(self) -> None:
        # Orientation 6 means "rotate 90° clockwise to view": a 1200x800 photo
        # is stored landscape but meant to be seen as 800x1200.
        upright, width, height, _, _ = process(as_jpeg(landscape(1200, 800), orientation=6))
        assert (width, height) == (800, 1200), "orientation 6 should come out portrait"
        assert Image.open(io.BytesIO(upright)).size == (800, 1200)

    def test_keeps_the_taken_date_and_drops_the_rest(self) -> None:
        jpeg, _, _, when, _ = process(as_jpeg(landscape(), orientation=1))
        assert when is not None and when.isoformat() == "2024-06-14"
        # Nothing else survives the re-encode.
        assert not dict(Image.open(io.BytesIO(jpeg)).getexif())

    def test_converts_heic(self) -> None:
        jpeg, width, height, _, _ = process(as_heic(landscape(1000, 750)))
        assert (width, height) == (1000, 750)
        assert Image.open(io.BytesIO(jpeg)).format == "JPEG"

    def test_a_file_that_is_not_an_image_is_refused(self) -> None:
        with pytest.raises(PhotoError):
            process(b"this is not a photo")


class TestStore:
    def test_de_dups_on_the_original(self, store: PhotoStore) -> None:
        data = as_jpeg(landscape())
        first, added = store.add(data, "one.jpg")
        assert added

        again, added_again = store.add(data, "a-different-name.jpg")
        assert again == first
        assert not added_again
        assert len(store.photos()) == 1

    def test_failed_files_are_moved_aside_and_never_listed(self, store: PhotoStore) -> None:
        store.add(as_jpeg(landscape()), "good.jpg")
        with pytest.raises(PhotoError):
            store.add(b"not an image at all", "broken.jpg")

        assert len(store.photos()) == 1
        assert [p.name for p in store.failed.iterdir()] != []
        assert list(store.cache.glob("*.jpg")) != []
        # The broken original is out of originals/, so a rerun cannot trip on it.
        assert len(list(store.originals.iterdir())) == 1

    def test_newest_first(self, store: PhotoStore) -> None:
        store.add(as_jpeg(landscape(colour="red"), orientation=1), "june.jpg")  # 2024-06-14
        store.add(as_jpeg(landscape(colour="blue")), "undated.jpg")  # today
        assert store.photos()[0].taken_at is None, "an undated upload is the newest thing we have"

    def test_survives_a_wrecked_index(self, store: PhotoStore, tmp_path: Path) -> None:
        store.add(as_jpeg(landscape()), "one.jpg")
        store.index_file.write_text("{ this is not json", encoding="utf-8")

        reopened = PhotoStore(store.directory)
        assert reopened.photos() == []
        assert list(store.directory.glob("index.bad-*.json")), "the bad index is kept for a human"

    def test_picks_up_an_index_written_by_the_cli(self, store: PhotoStore) -> None:
        # The import CLI is a separate process writing the same index.json. The
        # running service holds its catalogue in memory, so it has to notice.
        store.add(as_jpeg(landscape(colour="red")), "first.jpg")

        offline = PhotoStore(store.directory)
        offline.add(as_jpeg(landscape(colour="blue")), "imported.jpg")

        assert len(store.photos()) == 2, "a CLI import should not need a restart"

    def test_does_not_lose_a_photo_another_process_added(self, store: PhotoStore) -> None:
        store.add(as_jpeg(landscape(colour="red")), "first.jpg")
        PhotoStore(store.directory).add(as_jpeg(landscape(colour="blue")), "second.jpg")

        store.add(as_jpeg(landscape(colour="green")), "third.jpg")
        assert len(store.photos()) == 3

    def test_delete_removes_the_files(self, store: PhotoStore) -> None:
        photo_id, _ = store.add(as_jpeg(landscape()), "one.jpg")
        assert store.delete(photo_id)
        assert store.photos() == []
        assert not store.delete(photo_id)

    def test_import_folder(self, store: PhotoStore, tmp_path: Path) -> None:
        folder = tmp_path / "export"
        (folder / "nested").mkdir(parents=True)
        (folder / "a.jpg").write_bytes(as_jpeg(landscape(colour="red")))
        (folder / "nested" / "b.heic").write_bytes(as_heic(landscape(colour="blue")))
        (folder / "a-copy.jpg").write_bytes(as_jpeg(landscape(colour="red")))
        (folder / "notes.txt").write_text("not a photo", encoding="utf-8")
        (folder / "broken.jpg").write_bytes(b"nope")

        added, skipped, failed = store.import_folder(folder)
        assert (added, skipped, failed) == (2, 1, 1)
        assert len(store.photos()) == 2


class TestEndpoints:
    def test_upload_lists_and_serves(self, client: TestClient) -> None:
        response = upload(client, as_jpeg(landscape(3000, 2000)))
        assert response.status_code == 200
        body = response.json()
        assert len(body["added"]) == 1 and body["skipped"] == []

        listed = client.get("/api/photos").json()
        assert len(listed) == 1
        photo = listed[0]
        assert photo["url"] == f"/api/photos/{photo['id']}.jpg"
        assert (photo["w"], photo["h"]) == (2048, 1365)

        served = client.get(photo["url"])
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/jpeg"
        assert "immutable" in served.headers["cache-control"]

    def test_upload_reports_a_repeat_as_skipped(self, client: TestClient) -> None:
        data = as_jpeg(landscape())
        first = upload(client, data).json()
        second = upload(client, data).json()
        assert second["added"] == [] and second["skipped"] == first["added"]

    def test_many_files_in_one_request(self, client: TestClient) -> None:
        files = [
            ("file", (f"{colour}.jpg", as_jpeg(landscape(colour=colour)), "image/jpeg"))
            for colour in ("red", "green", "blue")
        ]
        body = client.post("/api/photos", files=files, headers={"X-Mantel-Token": TOKEN}).json()
        assert len(body["added"]) == 3

    def test_a_broken_file_does_not_fail_the_batch(self, client: TestClient) -> None:
        files = [
            ("file", ("good.jpg", as_jpeg(landscape()), "image/jpeg")),
            ("file", ("bad.jpg", b"nope", "image/jpeg")),
        ]
        response = client.post("/api/photos", files=files, headers={"X-Mantel-Token": TOKEN})
        assert response.status_code == 200
        assert len(response.json()["added"]) == 1
        assert len(client.get("/api/photos").json()) == 1

    def test_a_bad_token_is_rejected(self, client: TestClient) -> None:
        assert upload(client, as_jpeg(landscape()), token="wrong").status_code == 401
        # Nothing was stored on the way to being refused.
        assert client.get("/api/photos").json() == []

    def test_a_missing_token_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/photos", files=[("file", ("a.jpg", as_jpeg(landscape()), "image/jpeg"))]
        )
        assert response.status_code == 401

    def test_uploads_are_off_when_no_token_is_configured(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An empty token must not mean "everything matches".
        monkeypatch.setenv("MANTEL_UPLOAD_TOKEN", "")
        assert upload(client, as_jpeg(landscape()), token="").status_code == 503
        assert upload(client, as_jpeg(landscape()), token="anything").status_code == 503

    def test_reading_needs_no_token(self, client: TestClient) -> None:
        upload(client, as_jpeg(landscape()))
        assert client.get("/api/photos").status_code == 200

    def test_delete_needs_the_token(self, client: TestClient) -> None:
        photo_id = upload(client, as_jpeg(landscape())).json()["added"][0]
        assert client.delete(f"/api/photos/{photo_id}").status_code == 401

        ok = client.delete(f"/api/photos/{photo_id}", headers={"X-Mantel-Token": TOKEN})
        assert ok.status_code == 200
        assert client.get("/api/photos").json() == []

    def test_an_unknown_photo_is_a_404(self, client: TestClient) -> None:
        assert client.get("/api/photos/deadbeefdeadbeef.jpg").status_code == 404
