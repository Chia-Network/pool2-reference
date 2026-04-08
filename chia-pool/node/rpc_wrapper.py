from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from api.node import (
    GetBlockchainStateResponse,
    GetCoinRecordByNameResponse,
    GetCoinRecordsByPuzzleHashesResponse,
    GetPuzzleAndSolutionResponse,
    GetRecentSignagePointOrEOSResponse,
)
from chia.full_node.full_node_rpc_client import FullNodeRpcClient
from chia.rpc.rpc_client import ResponseFailureError
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint16, uint32, uint64
from node.config import CONFIG_FILE_NAME, Config, load
from typing_extensions import Self


class NodeRPC:
    client: FullNodeRpcClient
    config: Config

    @classmethod
    @asynccontextmanager
    async def create(cls) -> AsyncIterator[Self]:
        self = cls()
        with Path.cwd().joinpath(CONFIG_FILE_NAME).open(mode="r") as file:
            config_data = yaml.safe_load(file)
        config: Config = load(config_data)
        self.config = config
        async with FullNodeRpcClient.create_as_context(
            self_hostname=self.config["self_hostname"],
            port=uint16(self.config["rpc_port"]),
            root_path=Path(self.config["root_path"]),
            net_config=self.config["net_config"],
        ) as client:
            self.client = client
            yield self

    async def get_blockchain_state(self) -> GetBlockchainStateResponse:
        dict_response = await self.client.get_blockchain_state()
        return GetBlockchainStateResponse(
            peak=uint32(dict_response["peak"].height), synced=dict_response["sync"]["synced"]
        )

    async def get_coin_records_by_puzzle_hashes(
        self, *, puzzle_hashes: list[bytes32], include_spent_coins: bool, start_height: uint32
    ) -> GetCoinRecordsByPuzzleHashesResponse:
        return GetCoinRecordsByPuzzleHashesResponse(
            coin_records=await self.client.get_coin_records_by_puzzle_hashes(
                puzzle_hashes=puzzle_hashes, include_spent_coins=include_spent_coins, start_height=start_height
            )
        )

    async def get_coin_record_by_name(self, *, coin_id: bytes32) -> GetCoinRecordByNameResponse:
        return GetCoinRecordByNameResponse(coin_record=await self.client.get_coin_record_by_name(coin_id=coin_id))

    async def get_recent_signage_point(self, *, signage_point_hash: bytes32) -> GetRecentSignagePointOrEOSResponse:
        try:
            dict_response = await self.client.get_recent_signage_point_or_eos(
                sp_hash=signage_point_hash, challenge_hash=None
            )
        except ResponseFailureError:
            return GetRecentSignagePointOrEOSResponse(
                signage_point=None, eos=None, time_received=uint64(0), exists=False, reverted=False
            )
        return GetRecentSignagePointOrEOSResponse(
            signage_point=dict_response["signage_point"],
            eos=None,
            time_received=uint64(dict_response["time_recieved"]),
            exists=True,
            reverted=dict_response["reverted"],
        )

    async def get_recent_end_of_subslot(self, *, challenge_hash: bytes32) -> GetRecentSignagePointOrEOSResponse:
        try:
            dict_response = await self.client.get_recent_signage_point_or_eos(
                sp_hash=None, challenge_hash=challenge_hash
            )
        except ResponseFailureError:
            return GetRecentSignagePointOrEOSResponse(
                signage_point=None, eos=None, time_received=uint64(0), exists=False, reverted=False
            )
        return GetRecentSignagePointOrEOSResponse(
            signage_point=None,
            eos=dict_response["end_of_sub_slot"],
            time_received=uint64(dict_response["time_recieved"]),
            exists=True,
            reverted=dict_response["reverted"],
        )

    async def get_puzzle_and_solution(self, *, coin_id: bytes32, height: uint32) -> GetPuzzleAndSolutionResponse:
        return GetPuzzleAndSolutionResponse(
            spend=await self.client.get_puzzle_and_solution(coin_id=coin_id, height=height)
        )
