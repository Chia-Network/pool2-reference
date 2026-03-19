from __future__ import annotations

import pathlib
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
import yaml
from api.node import FullNode
from chia._tests.conftest import blockchain_constants, consensus_mode, one_node, self_hostname  # noqa: PLC2701, F401
from chia.rpc.rpc_client import ResponseFailureError
from chia.simulator.block_tools import BlockTools
from chia.simulator.start_simulator import SimulatorFullNodeService
from chia.types.coin_spend import make_spend
from chia.wallet.wallet_service import WalletService
from chia_rs import G2Element, Program, SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint32
from node.config import CONFIG_FILE_NAME
from node.rpc_wrapper import NodeRPC

if TYPE_CHECKING:
    node: type[FullNode] = NodeRPC


@pytest.fixture
def full_node_service(
    self_hostname: str,  # noqa: F811
    one_node: tuple[list[SimulatorFullNodeService], list[WalletService], BlockTools],  # noqa: F811
) -> Iterator[SimulatorFullNodeService]:
    one_node[0][0].service_config["selected_network"] = "simulator"
    assert one_node[0][0].rpc_server is not None
    config_path = pathlib.Path.cwd().joinpath(CONFIG_FILE_NAME)
    try:
        config_path.touch()
        with config_path.open(mode="w") as file:
            yaml.dump(
                {
                    "self_hostname": self_hostname,
                    "rpc_port": one_node[0][0].rpc_server.listen_port,
                    "root_path": str(one_node[0][0].root_path),
                    "net_config": {
                        "rpc_timeout": one_node[0][0].config["rpc_timeout"],
                        "daemon_ssl": one_node[0][0].config["daemon_ssl"],
                        "private_ssl_ca": one_node[0][0].config["private_ssl_ca"],
                    },
                },
                file,
            )
        yield one_node[0][0]
    finally:
        if config_path.exists():
            config_path.unlink()


@pytest.mark.anyio
async def test_rpc_wrapper(full_node_service: SimulatorFullNodeService) -> None:
    async with NodeRPC.create() as rpc_client:
        # create ourselves some coins
        NUM_BLOCKS = 3
        REWARDS_PER_BLOCK = 2
        ACS = Program.to(None)
        await full_node_service._api.farm_blocks_to_puzzlehash(count=1, guarantee_transaction_blocks=True)  # pre-farm
        await full_node_service._api.farm_blocks_to_puzzlehash(  # our rewards (paid out in next block)
            count=1, farm_to=ACS.get_tree_hash(), guarantee_transaction_blocks=True
        )
        await full_node_service._api.farm_blocks_to_puzzlehash(count=1, guarantee_transaction_blocks=True)
        await full_node_service._api.wait_for_self_synced()
        # check the blockchain state
        state = await rpc_client.get_blockchain_state()
        assert state["peak"] == NUM_BLOCKS
        assert state["synced"]
        # check our coin record getters
        puzhashes_response = await rpc_client.get_coin_records_by_puzzle_hashes(
            puzzle_hashes=[ACS.get_tree_hash()], include_spent_coins=False, start_height=uint32(NUM_BLOCKS + 1)
        )
        assert len(puzhashes_response["coin_records"]) == 0
        puzhashes_response = await rpc_client.get_coin_records_by_puzzle_hashes(
            puzzle_hashes=[ACS.get_tree_hash()], include_spent_coins=False, start_height=uint32(NUM_BLOCKS)
        )
        assert len(puzhashes_response["coin_records"]) == REWARDS_PER_BLOCK
        spent_coin = puzhashes_response["coin_records"][0].coin
        await rpc_client.get_coin_record_by_name(coin_id=spent_coin.name())
        with pytest.raises(ResponseFailureError, match=f"Coin record 0x{bytes32.zeros.hex()} not found"):
            await rpc_client.get_coin_record_by_name(coin_id=bytes32.zeros)
        # spend one of the coins
        await rpc_client.client.push_tx(
            spend_bundle=SpendBundle(
                [make_spend(spent_coin, ACS, Program.to(None))],
                aggregated_signature=G2Element(),
            )
        )
        await full_node_service._api.farm_blocks_to_puzzlehash(count=1, guarantee_transaction_blocks=True)
        await full_node_service._api.wait_for_self_synced()
        spent_height = (await rpc_client.get_blockchain_state())["peak"]
        # check include_spent_coins working
        puzhashes_response = await rpc_client.get_coin_records_by_puzzle_hashes(
            puzzle_hashes=[ACS.get_tree_hash()], include_spent_coins=False, start_height=uint32(0)
        )
        assert len(puzhashes_response["coin_records"]) == REWARDS_PER_BLOCK - 1
        puzhashes_response = await rpc_client.get_coin_records_by_puzzle_hashes(
            puzzle_hashes=[ACS.get_tree_hash()], include_spent_coins=True, start_height=uint32(0)
        )
        assert len(puzhashes_response["coin_records"]) == REWARDS_PER_BLOCK
        # test our block info endpoints
        sp_hash = next(iter(full_node_service._api.full_node.full_node_store.recent_signage_points.cache.keys()))
        assert (await rpc_client.get_recent_signage_point(signage_point_hash=sp_hash))["exists"]
        challenge_hash = next(iter(full_node_service._api.full_node.full_node_store.recent_eos.cache.keys()))
        assert (await rpc_client.get_recent_end_of_subslot(challenge_hash=challenge_hash))["exists"]
        assert not (await rpc_client.get_recent_signage_point(signage_point_hash=bytes32.zeros))["exists"]
        assert not (await rpc_client.get_recent_end_of_subslot(challenge_hash=bytes32.zeros))["exists"]
        # test the spend fetching
        spends_response = await rpc_client.get_puzzle_and_solution(coin_id=spent_coin.name(), height=spent_height)
        assert spends_response["spend"].coin == spent_coin
        assert spends_response["spend"].puzzle_reveal.get_tree_hash() == ACS.get_tree_hash()
