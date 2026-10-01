"""The bundled gazetteer: right where it matters, silent where it cannot be."""

from __future__ import annotations

import io

from PIL import Image

from mantel_api import places
from mantel_api.photos import process, taken_near

#: A town in the table, and the photos taken in it.
HOME = (37.5630, -122.3255)


def with_gps(lat: float, lon: float, size: tuple[int, int] = (200, 150)) -> bytes:
    """A JPEG carrying a GPS fix, the way a phone writes one."""

    def rational(value: float) -> tuple[float, float, float]:
        degrees = float(int(abs(value)))
        minutes = float(int((abs(value) - degrees) * 60))
        seconds = round((abs(value) - degrees - minutes / 60) * 3600, 2)
        return (degrees, minutes, seconds)

    image = Image.new("RGB", size, (60, 90, 120))
    exif = Image.Exif()
    # The GPS block is its own IFD; Pillow will only write one it has handed
    # out itself, which is why this is not a plain dict assignment.
    gps = exif.get_ifd(0x8825)
    gps[1] = "N" if lat >= 0 else "S"
    gps[2] = rational(lat)
    gps[3] = "E" if lon >= 0 else "W"
    gps[4] = rational(lon)
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


class TestTheTable:
    def test_it_is_bundled_and_not_empty(self) -> None:
        # No network, ever: the frame is the screen most likely to be running
        # while the house is offline.
        assert places.loaded() > 20000

    def test_it_is_sorted_by_latitude(self) -> None:
        # The lookup bisects on it; unsorted, it would silently return the
        # nearest city in whatever band it happened to look at.
        table, latitudes = places._table()
        assert latitudes == sorted(latitudes)
        assert len(table) == len(latitudes)


class TestNaming:
    def test_it_names_the_town_the_family_lives_in(self) -> None:
        assert places.name_for(*HOME) == "San Mateo"

    def test_it_stays_quiet_rather_than_naming_the_wrong_place(self) -> None:
        """The whole argument for the distance cap.

        The middle of the Pacific has a nearest city, and naming it would not
        be a vaguer answer than the right one — it would be a different one.
        """
        assert places.name_for(-30.0, -140.0) is None

    def test_a_photo_with_no_fix_says_nothing(self) -> None:
        assert places.name_for(None, None) is None
        assert places.name_for(37.0, None) is None

    def test_the_null_island_a_camera_writes_is_not_a_place(self) -> None:
        # 0,0 in the Atlantic is what a camera puts in EXIF when it has no fix.
        assert places.name_for(0.0, 0.0) is None

    def test_coordinates_off_the_earth_are_refused(self) -> None:
        assert places.name_for(120.0, 30.0) is None
        assert places.name_for(30.0, 400.0) is None

    def test_the_cap_is_a_real_boundary(self) -> None:
        near = places.nearest(*HOME)
        assert near is not None and near.name == "San Mateo"
        # Asking for a metre finds nothing, even standing on the town.
        assert places.nearest(37.60, -121.90, within_km=0.001) is None


class TestFromAPhoto:
    def test_gps_comes_out_of_exif_with_the_right_sign(self) -> None:
        lat, lon = taken_near(Image.open(io.BytesIO(with_gps(*HOME)))) or (0.0, 0.0)
        assert abs(lat - HOME[0]) < 0.01
        assert abs(lon - HOME[1]) < 0.01, "a western longitude must come out negative"

    def test_the_place_is_kept_and_the_coordinates_are_not(self) -> None:
        jpeg, _width, _height, _when, place = process(with_gps(*HOME))
        assert place == "San Mateo"
        # Re-encoding is what strips it: nothing is copied to the new file, so
        # what ships to the iPad is a town name and not a house.
        assert not dict(Image.open(io.BytesIO(jpeg)).getexif())

    def test_a_photo_without_a_fix_simply_has_no_place(self) -> None:
        plain = Image.new("RGB", (200, 150), (10, 10, 10))
        out = io.BytesIO()
        plain.save(out, format="JPEG")
        assert process(out.getvalue())[4] is None
