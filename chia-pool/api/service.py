from __future__ import annotations

import pathlib
from typing import Protocol, TypedDict

from api.node_rpc import NodeRPC
from api.store import Store
from api.wallet_rpc import Wallet
from chia_rs.sized_ints import uint64
from typing_extensions import Self

CONFIG_FILE_NAME = "pool_service_client_config.yaml"


class Service(Protocol):
    store: Store
    full_node: NodeRPC
    wallet: Wallet
    config: Config

    @property
    def current_time(self) -> uint64: ...
    @classmethod
    def create(cls, *, store: Store, full_node: NodeRPC, wallet: Wallet, root_path: pathlib.Path) -> Self: ...
    async def confirm_partials(self) -> None: ...
    async def check_for_singletons(self) -> None: ...
    async def collect_pool_rewards(self) -> None: ...
    async def submit_payments(self) -> None: ...


class PoolIdentityConfig(TypedDict):
    relative_lock_height: int
    pool_claim_hash: str
    pool_memoization: str


class Config(TypedDict):
    pool_identity: PoolIdentityConfig
    min_difficulty: int
    default_difficulty: int
    partial_time_limit: int
    partial_confirmation_delay: int
    partial_confirmation_batches: int
    scan_start_height: int
    confirmation_security_threshold: int
    max_additions_per_transaction: int
    number_of_partials_target: int
    time_target: int
    fee_basis_points: int
    genesis_challenge: str
    singleton_scan_batches: int
