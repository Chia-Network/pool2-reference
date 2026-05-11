from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from api.store import (
    CONFIG_FILE_NAME,
    ClaimMetadata,
    Config,
    GetFarmerResponse,
    GetLatestPayoutResponse,
    GetLatestSingletonResponse,
    GetLauncherIDsResponse,
    GetPartialsResponse,
    GetRewardClaimsResponse,
    IsPendingRewardClaimResponse,
    PartialMetadata,
)
from chia.util.db_wrapper import DBWrapper2
from chia_rs import G1Element
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint32, uint64
from config_loading import canonical_load_config
from store.config import ConfigSchema
from typing_extensions import Self


class Store:
    config: Config
    db_wrapper: DBWrapper2

    @classmethod
    @contextlib.asynccontextmanager
    async def create(cls, root_path: Path) -> AsyncIterator[Self]:
        store = cls()
        config = canonical_load_config(
            root_path=root_path, config_filename=CONFIG_FILE_NAME, schema_validation=ConfigSchema(), config_type=Config
        )
        store.config = config
        async with DBWrapper2.managed(database=Path(config["store_path"])) as store.db_wrapper:
            async with store.db_wrapper.writer_maybe_transaction() as conn:
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS farmers("
                    "launcher_id blob PRIMARY KEY, "
                    "version int, "
                    "payout_instructions string, "
                    "difficulty bigint, "
                    "authentication_public_key blob)"
                )
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS singletons"
                    "(launcher_id blob PRIMARY KEY, coin_id blob, created_height int, exiting_height int)"
                )
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS partials("
                    "launcher_id blob, "
                    "timestamp bigint, "
                    "difficulty bigint, "
                    "challenge_hash blob, "
                    "pos_hash blob PRIMARY KEY, "
                    "end_of_subslot boolean, "
                    "pool_contract_puzzle_hash blob, "
                    "confirmed boolean)"
                )
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS claims("
                    "timestamp bigint PRIMARY KEY, "
                    "amount bigint, "
                    "tx_id blob, "
                    "tx_confirmed boolean, "
                    "paid boolean)"
                )
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS payouts(timestamp bigint PRIMARY KEY, payout_details string)"
                )

            yield store

    async def add_farmer(
        self,
        *,
        version: uint8,
        launcher_id: bytes32,
        payout_instructions: str,
        difficulty: uint64,
        authentication_public_key: G1Element,
    ) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO farmers "
                "(version, launcher_id, payout_instructions, difficulty, authentication_public_key) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    version,
                    launcher_id,
                    payout_instructions,
                    difficulty,
                    bytes(authentication_public_key),
                ),
            )

    async def get_farmer(self, *, launcher_id: bytes32) -> GetFarmerResponse:
        async with self.db_wrapper.reader() as conn:
            cursor = await conn.execute(
                "SELECT * FROM farmers WHERE launcher_id = ?",
                (launcher_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Farmer not found for launcher ID {launcher_id.hex()}")
            return GetFarmerResponse(
                version=uint8(row[1]),
                payout_instructions=row[2],
                difficulty=uint64(row[3]),
                authentication_public_key=G1Element.from_bytes(row[4]),
            )

    async def delete_farmer(self, *, launcher_id: bytes32) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "DELETE FROM farmers WHERE launcher_id = ?",
                (launcher_id,),
            )

    async def update_difficulty(self, *, launcher_id: bytes32, difficulty: uint64) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "UPDATE farmers SET difficulty = ? WHERE launcher_id = ?",
                (difficulty, launcher_id),
            )

    async def get_launcher_ids(
        self, *, start: uint64 | None = None, count: uint64 | None = None
    ) -> GetLauncherIDsResponse:
        if start is not None and count is None:
            raise ValueError("count must be specified if start is specified")
        async with self.db_wrapper.reader() as conn:
            supplied_args = []
            if count is not None:
                supplied_args.append(count)
            if start is not None:
                supplied_args.append(start)
            cursor = await conn.execute(
                "SELECT launcher_id FROM farmers ORDER BY launcher_id ASC"  # noqa: S608
                + (" LIMIT ?" if count is not None else "")
                + (" OFFSET ?" if start is not None else ""),
                tuple(supplied_args),
            )
            rows = await cursor.fetchall()
            return GetLauncherIDsResponse(launcher_ids=[bytes32(row[0]) for row in rows])

    async def add_singleton(
        self, *, launcher_id: bytes32, coin_id: bytes32, created_height: uint32, exiting_height: uint32 | None
    ) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO singletons "
                "(launcher_id, coin_id, created_height, exiting_height) VALUES (?, ?, ?, ?)",
                (launcher_id, coin_id, created_height, exiting_height),
            )

    async def delete_singleton(self, *, launcher_id: bytes32) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "DELETE FROM singletons WHERE launcher_id = ?",
                (launcher_id,),
            )

    async def get_latest_singleton(self, *, launcher_id: bytes32) -> GetLatestSingletonResponse:
        async with self.db_wrapper.reader() as conn:
            cursor = await conn.execute(
                "SELECT * FROM singletons WHERE launcher_id = ? ORDER BY created_height DESC LIMIT 1",
                (launcher_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Singleton not found for launcher ID {launcher_id.hex()}")
            return GetLatestSingletonResponse(
                coin_id=bytes32(row[1]),
                created_height=uint32(row[2]),
                exiting_height=uint32(row[3]) if row[3] is not None else None,
            )

    async def add_partial(self, *, launcher_id: bytes32, partial: PartialMetadata) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO partials "
                "(launcher_id, timestamp, difficulty, challenge_hash, pos_hash, "
                "end_of_subslot, pool_contract_puzzle_hash, confirmed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)",
                (
                    launcher_id,
                    partial.timestamp,
                    partial.difficulty,
                    partial.challenge_hash,
                    partial.pos_hash,
                    partial.end_of_sub_slot,
                    partial.pool_contract_puzzle_hash,
                ),
            )

    async def get_partials(
        self,
        *,
        launcher_id: bytes32,
        confirmed: bool,
        since: uint64 | None = None,
        before: uint64 | None = None,
        count: uint64 | None = None,
    ) -> GetPartialsResponse:
        if count is not None and (since is not None or before is not None):
            raise ValueError("Cannot specify both count and since/before")

        async with self.db_wrapper.reader() as conn:
            cursor = await conn.execute(
                "SELECT * from partials WHERE launcher_id = ?"  # noqa: S608
                + (" AND confirmed = TRUE" if confirmed else " AND confirmed = FALSE")
                + (" AND timestamp >= ?" if since is not None else "")
                + (" AND timestamp < ?" if before is not None else "")
                + " ORDER BY timestamp DESC"
                + (" LIMIT ?" if count is not None else ""),
                tuple(
                    [launcher_id]
                    + ([since] if since is not None else [])
                    + ([before] if before is not None else [])
                    + ([count] if count is not None else []),
                ),
            )
            rows = await cursor.fetchall()
            if rows is None:
                return GetPartialsResponse(partials=[])
            return GetPartialsResponse(
                partials=[
                    PartialMetadata(
                        timestamp=row[1],
                        difficulty=row[2],
                        challenge_hash=bytes32(row[3]),
                        pos_hash=bytes32(row[4]),
                        end_of_sub_slot=bool(row[5]),
                        pool_contract_puzzle_hash=bytes32(row[6]),
                    )
                    for row in rows
                ]
            )

    async def confirm_partials(self, *, launcher_id: bytes32, until_timestamp: uint64) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "UPDATE partials SET confirmed = TRUE WHERE launcher_id = ? AND timestamp < ?",
                (launcher_id, until_timestamp),
            )

    async def delete_partial(self, *, launcher_id: bytes32, timestamp: uint64) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "DELETE FROM partials WHERE launcher_id = ? AND timestamp = ?",
                (launcher_id, timestamp),
            )

    async def delete_all_partials(self, *, launcher_id: bytes32) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "DELETE FROM partials WHERE launcher_id = ?",
                (launcher_id,),
            )

    async def add_reward_claim(self, *, timestamp: uint64, amount: uint64, tx_id: bytes32) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO claims (timestamp, amount, tx_id, tx_confirmed, paid) "
                "VALUES (?, ?, ?, FALSE, FALSE)",
                (timestamp, amount, tx_id),
            )

    async def is_pending_reward_claim(self) -> IsPendingRewardClaimResponse:
        async with self.db_wrapper.reader() as conn:
            cursor = await conn.execute(
                "SELECT * FROM claims WHERE tx_confirmed = FALSE",
            )
            rows = await cursor.fetchall()
            if len(list(rows)) > 0:
                return IsPendingRewardClaimResponse(pending=True, tx_id=bytes32(next(iter(rows))[2]))
            return IsPendingRewardClaimResponse(pending=False, tx_id=None)

    async def confirm_claim_tx(self, tx_id: bytes32) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "UPDATE claims SET tx_confirmed = TRUE WHERE tx_id = ?",
                (tx_id,),
            )

    async def set_claims_statuses(self, *, timestamps: list[uint64]) -> None:
        if len(timestamps) == 0:
            return
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                f"UPDATE claims SET paid = TRUE WHERE timestamp IN ({','.join(['?'] * len(timestamps))})",  # noqa: S608
                tuple(timestamps),
            )

    async def get_unpaid_reward_claims(self) -> GetRewardClaimsResponse:
        async with self.db_wrapper.reader() as conn:
            cursor = await conn.execute(
                "SELECT * FROM claims WHERE paid = FALSE AND tx_confirmed = TRUE",
            )
            rows = await cursor.fetchall()
            return GetRewardClaimsResponse(
                claims=[ClaimMetadata(timestamp=row[0], amount=row[1], tx_id=bytes32(row[2])) for row in rows]
            )

    async def add_payout(self, *, timestamp: uint64, payout_details: str) -> None:
        async with self.db_wrapper.writer_maybe_transaction() as conn:
            await conn.execute(
                "INSERT INTO payouts (timestamp, payout_details) VALUES (?, ?)",
                (timestamp, payout_details),
            )

    async def get_latest_payout(self) -> GetLatestPayoutResponse | None:
        async with self.db_wrapper.reader() as conn:
            cursor = await conn.execute(
                "SELECT * FROM payouts ORDER BY timestamp DESC LIMIT 1",
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return GetLatestPayoutResponse(timestamp=row[0], payout_details=row[1])
