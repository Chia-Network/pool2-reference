from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Self

import aiosqlite
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
)
from chia_rs import G1Element
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint32, uint64
from store.config import CONFIG_FILE_NAME, Config, load


class Store:
    config: Config
    connection: aiosqlite.Connection
    _savepoint_name: int

    @classmethod
    @contextlib.asynccontextmanager
    async def create(cls) -> AsyncIterator[Self]:
        store = cls()
        with Path.home().joinpath(CONFIG_FILE_NAME).open(mode="r") as file:
            config_data = yaml.safe_load(file)
        config: Config = load(config_data)
        store.config = config
        store._savepoint_name = 0
        try:
            store.connection = await aiosqlite.connect(Path(config["store_path"]))
            await store.connection.execute("pragma journal_mode=wal")
            await store.connection.execute("pragma synchronous=2")
            await store.connection.execute(
                "CREATE TABLE IF NOT EXISTS farmers("
                "launcher_id blob PRIMARY KEY, "
                "version int, "
                "payout_instructions string, "
                "difficulty bigint, "
                "authentication_public_key blob)"
            )
            await store.connection.execute(
                "CREATE TABLE IF NOT EXISTS singletons"
                "(launcher_id blob PRIMARY KEY, coin_id blob, created_height int, exiting_height int)"
            )
            await store.connection.execute(
                "CREATE TABLE IF NOT EXISTS partials("
                "launcher_id blob, "
                "timestamp bigint PRIMARY KEY, "
                "difficulty bigint, "
                "confirmed boolean)"
            )
            await store.connection.execute(
                "CREATE TABLE IF NOT EXISTS claims(timestamp bigint PRIMARY KEY, amount bigint, confirmed boolean)"
            )
            await store.connection.execute(
                "CREATE TABLE IF NOT EXISTS payouts(timestamp bigint PRIMARY KEY, payout_details string)"
            )

            await store.connection.commit()
            yield store
        finally:
            await store.connection.close()

    def _next_savepoint(self) -> str:
        name = f"s{self._savepoint_name}"
        self._savepoint_name += 1
        return name

    @contextlib.asynccontextmanager
    async def get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        name = self._next_savepoint()
        await self.connection.execute(f"SAVEPOINT {name}")
        try:
            yield self.connection
        except:
            await self.connection.execute(f"ROLLBACK TO {name}")
            raise
        finally:
            # rollback to a savepoint doesn't cancel the transaction, it
            # just rolls back the state. We need to cancel it regardless
            await self.connection.execute(f"RELEASE {name}")

    async def add_farmer(
        self,
        *,
        version: uint8,
        launcher_id: bytes32,
        payout_instructions: str,
        difficulty: uint64,
        authentication_public_key: G1Element,
    ) -> None:
        async with self.get_connection() as conn:
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
        async with self.get_connection() as conn:
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

    async def update_difficulty(self, *, launcher_id: bytes32, difficulty: uint64) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "UPDATE farmers SET difficulty = ? WHERE launcher_id = ?",
                (difficulty, launcher_id),
            )

    async def get_launcher_ids(
        self, *, start: uint64 | None = None, count: uint64 | None = None
    ) -> GetLauncherIDsResponse:
        if start is not None and count is None:
            raise ValueError("count must be specified if start is specified")
        async with self.get_connection() as conn:
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
        async with self.get_connection() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO singletons "
                "(launcher_id, coin_id, created_height, exiting_height) VALUES (?, ?, ?, ?)",
                (launcher_id, coin_id, created_height, exiting_height),
            )

    async def get_latest_singleton(self, *, launcher_id: bytes32) -> GetLatestSingletonResponse:
        async with self.get_connection() as conn:
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

    async def add_partial(self, *, launcher_id: bytes32, timestamp: uint64, difficulty: uint64) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO partials "
                "(launcher_id, timestamp, difficulty, confirmed) VALUES (?, ?, ?, FALSE)",
                (launcher_id, timestamp, difficulty),
            )

    async def get_partials(
        self, *, launcher_id: bytes32, confirmed: bool, since: uint64 | None = None, before: uint64 | None = None
    ) -> GetPartialsResponse:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * from partials WHERE launcher_id = ?"  # noqa: S608
                + (" AND confirmed = TRUE" if confirmed else " AND confirmed = FALSE")
                + (" AND timestamp >= ?" if since is not None else "")
                + (" AND timestamp < ?" if before is not None else ""),
                tuple(
                    [launcher_id] + ([since] if since is not None else []) + ([before] if before is not None else [])
                ),
            )
            rows = await cursor.fetchall()
            if rows is None:
                return GetPartialsResponse(partials=[])
            return GetPartialsResponse(partials=[PartialMetadata(timestamp=row[1], difficulty=row[2]) for row in rows])

    async def confirm_partials(self, *, launcher_id: bytes32, until_timestamp: uint64) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "UPDATE partials SET confirmed = TRUE WHERE launcher_id = ? AND timestamp <= ?",
                (launcher_id, until_timestamp),
            )

    async def delete_partial(self, *, launcher_id: bytes32, timestamp: uint64) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "DELETE FROM partials WHERE launcher_id = ? AND timestamp = ?",
                (launcher_id, timestamp),
            )

    async def add_reward_claim(self, *, timestamp: uint64, amount: uint64) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO claims (timestamp, amount, confirmed) VALUES (?, ?, FALSE)",
                (timestamp, amount),
            )

    async def set_claims_statuses(self, *, timestamps: list[uint64]) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                f"UPDATE claims SET confirmed = TRUE WHERE timestamp IN ({','.join(['?'] * len(timestamps))})",  # noqa: S608
                tuple(timestamps),
            )

    async def get_unpaid_reward_claims(self) -> GetRewardClaimsResponse:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM claims WHERE confirmed = FALSE",
            )
            rows = await cursor.fetchall()
            return GetRewardClaimsResponse(claims=[ClaimMetadata(timestamp=row[0], amount=row[1]) for row in rows])

    async def add_payout(self, *, timestamp: uint64, payout_details: str) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "INSERT INTO payouts (timestamp, payout_details) VALUES (?, ?)",
                (timestamp, payout_details),
            )

    async def get_latest_payout(self) -> GetLatestPayoutResponse | None:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM payouts ORDER BY timestamp DESC LIMIT 1",
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return GetLatestPayoutResponse(timestamp=row[0], payout_details=row[1])
