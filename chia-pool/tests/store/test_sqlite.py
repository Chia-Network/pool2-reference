from __future__ import annotations

import pathlib
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
import yaml
from api.store import (
    ClaimMetadata,
    GetFarmerResponse,
    GetLatestPayoutResponse,
    GetLatestSingletonResponse,
    GetLauncherIDsResponse,
    GetPartialsResponse,
    GetRewardClaimsResponse,
    PartialMetadata,
    Store,
)
from chia_rs import G1Element
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint32, uint64
from store.config import CONFIG_FILE_NAME
from store.sqlite import Store as SqliteStore

if TYPE_CHECKING:
    store_type: type[Store] = SqliteStore


@pytest.fixture
def config_fixture(tmp_path: pathlib.Path) -> Iterator[None]:
    config_path = pathlib.Path.cwd().joinpath(CONFIG_FILE_NAME)
    try:
        config_path.touch()
        with config_path.open(mode="w") as file:
            yaml.dump({"store_path": str(tmp_path.joinpath("store.sqlite"))}, file)
        yield
    finally:
        if config_path.exists():
            config_path.unlink()


def thirty_two_bytes(*, id_num: int) -> bytes32:
    return bytes32(bytes([id_num] * 32))


@pytest.mark.parametrize("store_type", [SqliteStore])
@pytest.mark.anyio
async def test_sqlite_store(config_fixture: None, store_type: type[Store]) -> None:
    farmer_1_launcher_id = thirty_two_bytes(id_num=1)
    farmer_2_launcher_id = thirty_two_bytes(id_num=2)
    farmer_1_payout_instructions = "cash money"
    farmer_2_payout_instructions = "for the love of the game"
    farmer_1_difficulty = uint64(100)
    farmer_2_difficulty = uint64(200)
    farmer_1_authentication_pubkey = G1Element.from_bytes(
        bytes.fromhex(
            "b2d620eff27a9c570264c9531c6ce72c2ddcff6c8445d2a0786f3161e5bb8c6d7c3040a07d865948303dd2cbc6537705"
        )
    )
    farmer_2_authentication_pubkey = G1Element.from_bytes(
        bytes.fromhex(
            "a00d36e34beda30c3cd6d5fba20daae798703c842afcd33dd57beba70ef52b203a2c212984f94b213123518378491b4a"
        )
    )
    async with store_type.create() as store:
        with pytest.raises(ValueError, match=f"Farmer not found for launcher ID {bytes32.zeros.hex()}"):
            await store.get_farmer(launcher_id=bytes32.zeros)
        await store.add_farmer(
            version=uint8(1),
            launcher_id=farmer_1_launcher_id,
            payout_instructions=farmer_1_payout_instructions,
            difficulty=farmer_1_difficulty,
            authentication_public_key=farmer_1_authentication_pubkey,
        )
        await store.add_farmer(
            version=uint8(1),
            launcher_id=farmer_2_launcher_id,
            payout_instructions=farmer_2_payout_instructions,
            difficulty=farmer_2_difficulty,
            authentication_public_key=farmer_2_authentication_pubkey,
        )
        for _ in range(2):
            assert await store.get_farmer(launcher_id=farmer_1_launcher_id) == GetFarmerResponse(
                version=uint8(1),
                payout_instructions=farmer_1_payout_instructions,
                difficulty=farmer_1_difficulty,
                authentication_public_key=farmer_1_authentication_pubkey,
            )
            farmer_1_difficulty = uint64(150)
            await store.update_difficulty(launcher_id=farmer_1_launcher_id, difficulty=farmer_1_difficulty)
        assert await store.get_launcher_ids() == GetLauncherIDsResponse(
            launcher_ids=[farmer_1_launcher_id, farmer_2_launcher_id]
        )
        assert await store.get_launcher_ids(count=uint64(1)) == GetLauncherIDsResponse(
            launcher_ids=[farmer_1_launcher_id]
        )
        assert await store.get_launcher_ids(count=uint64(1), start=uint64(1)) == GetLauncherIDsResponse(
            launcher_ids=[farmer_2_launcher_id]
        )
        with pytest.raises(ValueError, match="count must be specified if start is specified"):
            await store.get_launcher_ids(start=uint64(1))
        farmer_1_singleton_1_coin_id = thirty_two_bytes(id_num=5)
        farmer_1_singleton_1_created_height = uint32(1)
        await store.add_singleton(
            launcher_id=farmer_1_launcher_id,
            coin_id=farmer_1_singleton_1_coin_id,
            created_height=farmer_1_singleton_1_created_height,
            exiting_height=None,
        )
        assert await store.get_latest_singleton(launcher_id=farmer_1_launcher_id) == GetLatestSingletonResponse(
            coin_id=farmer_1_singleton_1_coin_id,
            created_height=farmer_1_singleton_1_created_height,
            exiting_height=None,
        )
        with pytest.raises(ValueError, match=f"Singleton not found for launcher ID {farmer_2_launcher_id.hex()}"):
            await store.get_latest_singleton(launcher_id=farmer_2_launcher_id)
        farmer_1_singleton_2_coin_id = thirty_two_bytes(id_num=6)
        farmer_1_singleton_2_created_height = uint32(2)
        await store.add_singleton(
            launcher_id=farmer_1_launcher_id,
            coin_id=farmer_1_singleton_2_coin_id,
            created_height=farmer_1_singleton_2_created_height,
            exiting_height=uint32(13),
        )
        assert await store.get_latest_singleton(launcher_id=farmer_1_launcher_id) == GetLatestSingletonResponse(
            coin_id=farmer_1_singleton_2_coin_id,
            created_height=farmer_1_singleton_2_created_height,
            exiting_height=uint32(13),
        )
        for i in range(3):
            await store.add_partial(
                launcher_id=farmer_1_launcher_id,
                timestamp=uint64(i),
                difficulty=uint64(i),
            )
        assert await store.get_partials(launcher_id=farmer_1_launcher_id, confirmed=True) == GetPartialsResponse(
            partials=[]
        )
        assert await store.get_partials(launcher_id=farmer_1_launcher_id, confirmed=False) == GetPartialsResponse(
            partials=[
                PartialMetadata(
                    timestamp=uint64(i),
                    difficulty=uint64(i),
                )
                for i in range(3)
            ]
        )
        assert await store.get_partials(
            launcher_id=farmer_1_launcher_id, confirmed=False, since=uint64(1)
        ) == GetPartialsResponse(
            partials=[
                PartialMetadata(
                    timestamp=uint64(i),
                    difficulty=uint64(i),
                )
                for i in range(1, 3)
            ]
        )
        assert await store.get_partials(
            launcher_id=farmer_1_launcher_id, confirmed=False, before=uint64(1)
        ) == GetPartialsResponse(
            partials=[
                PartialMetadata(
                    timestamp=uint64(i),
                    difficulty=uint64(i),
                )
                for i in range(1)
            ]
        )
        assert await store.get_partials(
            launcher_id=farmer_1_launcher_id, confirmed=False, count=uint64(2)
        ) == GetPartialsResponse(
            partials=[
                PartialMetadata(
                    timestamp=uint64(2),
                    difficulty=uint64(2),
                ),
                PartialMetadata(
                    timestamp=uint64(1),
                    difficulty=uint64(1),
                ),
            ]
        )
        await store.confirm_partials(launcher_id=farmer_1_launcher_id, until_timestamp=uint64(1))
        assert await store.get_partials(launcher_id=farmer_1_launcher_id, confirmed=True) == GetPartialsResponse(
            partials=[
                PartialMetadata(
                    timestamp=uint64(i),
                    difficulty=uint64(i),
                )
                for i in range(2)
            ]
        )
        assert await store.get_partials(
            launcher_id=farmer_1_launcher_id, confirmed=True, since=uint64(1)
        ) == GetPartialsResponse(
            partials=[
                PartialMetadata(
                    timestamp=uint64(i),
                    difficulty=uint64(i),
                )
                for i in range(1, 2)
            ]
        )
        assert await store.get_partials(
            launcher_id=farmer_1_launcher_id, confirmed=True, since=uint64(0), before=uint64(1)
        ) == GetPartialsResponse(
            partials=[
                PartialMetadata(
                    timestamp=uint64(i),
                    difficulty=uint64(i),
                )
                for i in range(1)
            ]
        )
        await store.delete_partial(launcher_id=farmer_1_launcher_id, timestamp=uint64(2))
        assert await store.get_partials(launcher_id=farmer_1_launcher_id, confirmed=False) == GetPartialsResponse(
            partials=[]
        )
        assert await store.get_partials(launcher_id=farmer_2_launcher_id, confirmed=True) == GetPartialsResponse(
            partials=[]
        )
        await store.add_payout(timestamp=uint64(2), payout_details=farmer_1_payout_instructions)
        assert await store.get_latest_payout() == GetLatestPayoutResponse(
            payout_details=farmer_1_payout_instructions,
            timestamp=uint64(2),
        )
        await store.add_reward_claim(timestamp=uint64(1), amount=uint64(100))
        assert await store.get_unpaid_reward_claims() == GetRewardClaimsResponse(
            claims=[ClaimMetadata(timestamp=uint64(1), amount=uint64(100))]
        )
        await store.set_claims_statuses(timestamps=[uint64(1)])
        assert await store.get_unpaid_reward_claims() == GetRewardClaimsResponse(claims=[])
