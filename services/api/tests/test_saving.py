"""What a kid is saving for: two picks, and the arithmetic behind the bars."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from mantel_api import ledger, saving
from mantel_api.db import Database


def rewards_in(client: TestClient) -> list[str]:
    return [reward["id"] for reward in client.get("/api/rewards").json()]


class TestMarking:
    def test_a_star_is_stored_and_comes_back_on_the_summary(
        self, client: TestClient
    ) -> None:
        wanted = rewards_in(client)[0]
        marked = client.put(f"/api/kids/mira/saving/{wanted}")
        assert marked.status_code == 200
        assert [one["reward_id"] for one in marked.json()["saving_for"]] == [wanted]

        # And on the next dashboard poll, which is where the bars are drawn.
        summary = client.get("/api/points/mira").json()
        assert [one["reward_id"] for one in summary["saving_for"]] == [wanted]

    def test_starring_it_again_takes_it_off(self, client: TestClient) -> None:
        wanted = rewards_in(client)[0]
        client.put(f"/api/kids/mira/saving/{wanted}")
        off = client.put(f"/api/kids/mira/saving/{wanted}")
        assert off.json()["saving_for"] == []

    def test_a_third_pick_pushes_the_oldest_off(self, client: TestClient) -> None:
        """A child who has changed their mind should not have to choose which
        of the two to give up: the one marked longest ago is the one they
        have gone off."""
        one, two, three = rewards_in(client)[:3]
        client.put(f"/api/kids/mira/saving/{one}")
        client.put(f"/api/kids/mira/saving/{two}")
        third = client.put(f"/api/kids/mira/saving/{three}")
        assert [pick["reward_id"] for pick in third.json()["saving_for"]] == [two, three]

    def test_two_is_the_cap(self, database: Database, client: TestClient) -> None:
        every = rewards_in(client)
        with database.write() as connection:
            kept = saving.set_ids(connection, "mira", every)
        assert len(kept) == saving.MAX_PICKS

    def test_a_double_tap_is_not_two_picks(self, database: Database) -> None:
        with database.write() as connection:
            kept = saving.set_ids(connection, "mira", ["ice_cream", "ice_cream"])
        assert kept == ["ice_cream"]

    def test_the_picks_are_one_childs_and_not_the_others(self, client: TestClient) -> None:
        one, two = rewards_in(client)[:2]
        client.put(f"/api/kids/mira/saving/{one}")
        client.put(f"/api/kids/kabir/saving/{two}")
        assert [p["reward_id"] for p in client.get("/api/points/mira").json()["saving_for"]] == [
            one
        ]
        assert [p["reward_id"] for p in client.get("/api/points/kabir").json()["saving_for"]] == [
            two
        ]


class TestTheBars:
    def test_a_pick_carries_what_the_bar_needs(self, client: TestClient) -> None:
        """Name, glyph and cost: the balance is already on the card."""
        wanted = rewards_in(client)[0]
        pick = client.put(f"/api/kids/mira/saving/{wanted}").json()["saving_for"][0]
        catalogue = next(r for r in client.get("/api/rewards").json() if r["id"] == wanted)
        assert pick == {
            "reward_id": catalogue["id"],
            "name": catalogue["name"],
            "glyph": catalogue["glyph"],
            "cost": catalogue["cost"],
        }

    def test_the_bar_moves_with_the_balance(
        self, client: TestClient, database: Database
    ) -> None:
        # The progress is balance over cost, computed on the card; what the
        # API owes it is a cost that does not move and a balance that does.
        wanted = rewards_in(client)[0]
        client.put(f"/api/kids/mira/saving/{wanted}")
        before = client.get("/api/points/mira").json()
        assert before["balance"] == 0

        with database.write() as connection:
            ledger.append(
                connection,
                kid_id="mira",
                delta=15,
                reason_kind="award",
                reason_ref="test",
                actor="parent",
                now=datetime.now(),
                note="tidying",
            )
        after = client.get("/api/points/mira").json()
        assert after["balance"] == 15
        assert after["saving_for"][0]["cost"] == before["saving_for"][0]["cost"]


class TestRefusals:
    def test_a_reward_nobody_offers_is_a_404(self, client: TestClient) -> None:
        assert client.put("/api/kids/mira/saving/a_pony").status_code == 404

    def test_a_child_who_does_not_live_here_is_a_404(self, client: TestClient) -> None:
        wanted = rewards_in(client)[0]
        assert client.put(f"/api/kids/nobody/saving/{wanted}").status_code == 404

    def test_a_reward_taken_out_of_the_file_stops_being_a_bar(
        self, client: TestClient, database: Database
    ) -> None:
        """Dropped rather than drawn as a blank bar with no name on it."""
        with database.write() as connection:
            saving.set_ids(connection, "mira", ["gone_from_the_file"])
        assert client.get("/api/points/mira").json()["saving_for"] == []

    def test_the_family_jar_saves_for_nothing(self, client: TestClient) -> None:
        # The jar is the house's, and the house does not have a wishlist.
        assert client.get("/api/points/family").json()["saving_for"] == []
