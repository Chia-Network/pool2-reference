from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest
from api.node_rpc import NodeRPC as NodeRPCStubs
from chia._tests.environments.wallet import WalletTestFramework
from chia.rpc.rpc_client import ResponseFailureError
from chia.types.coin_spend import make_spend
from chia_rs import G2Element, Program, SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint32
from node.rpc_wrapper import NodeRPC

if TYPE_CHECKING:
    node: type[NodeRPCStubs] = NodeRPC


@pytest.mark.parametrize(
    "wallet_environments",
    [{"num_environments": 1, "blocks_needed": [0]}],
    indirect=True,
)
@pytest.mark.anyio
@pytest.mark.standard_block_tools
async def test_rpc_wrapper(full_node_config: None, wallet_envs: WalletTestFramework, root_path: pathlib.Path) -> None:
    async with NodeRPC.create(root_path=root_path) as rpc_client:
        # create ourselves some coins
        NUM_BLOCKS = 3
        REWARDS_PER_BLOCK = 2
        ACS = Program.to(None)
        await wallet_envs.full_node.farm_blocks_to_puzzlehash(
            count=1, guarantee_transaction_blocks=True, timeout=100
        )  # pre-farm
        await wallet_envs.full_node.farm_blocks_to_puzzlehash(  # our rewards (paid out in next block)
            count=1, farm_to=ACS.get_tree_hash(), guarantee_transaction_blocks=True, timeout=100
        )
        await wallet_envs.full_node.farm_blocks_to_puzzlehash(count=1, guarantee_transaction_blocks=True, timeout=100)
        await wallet_envs.full_node.wait_for_self_synced()
        # check the constants
        constants = await rpc_client.get_constants()
        assert constants["constants"] == wallet_envs.full_node.full_node.constants
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
        await wallet_envs.full_node.farm_blocks_to_puzzlehash(count=1, guarantee_transaction_blocks=True, timeout=100)
        await wallet_envs.full_node.wait_for_self_synced()
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
        sp_hash = next(iter(wallet_envs.full_node.full_node.full_node_store.recent_signage_points.cache.keys()))
        assert (await rpc_client.get_recent_signage_point(signage_point_hash=sp_hash))["exists"]
        challenge_hash = next(iter(wallet_envs.full_node.full_node.full_node_store.recent_eos.cache.keys()))
        assert (await rpc_client.get_recent_end_of_subslot(challenge_hash=challenge_hash))["exists"]
        assert not (await rpc_client.get_recent_signage_point(signage_point_hash=bytes32.zeros))["exists"]
        assert not (await rpc_client.get_recent_end_of_subslot(challenge_hash=bytes32.zeros))["exists"]
        # test the spend fetching
        spends_response = await rpc_client.get_puzzle_and_solution(coin_id=spent_coin.name(), height=spent_height)
        assert spends_response["spend"].coin == spent_coin
        assert spends_response["spend"].puzzle_reveal.get_tree_hash() == ACS.get_tree_hash()
