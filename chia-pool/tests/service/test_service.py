from __future__ import annotations

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from api.node_rpc import GetRecentSignagePointOrEOSResponse
from api.service import Service as ServiceAPI
from api.store import PartialMetadata
from chia._tests.conftest import (  # noqa: PLC2701
    blockchain_constants,  # noqa: F401
    consensus_mode,  # noqa: F401
    farmer_harvester_2_simulators_zero_bits_plot_filter,  # noqa: F401
    self_hostname,  # noqa: F401
    trusted_full_node,  # noqa: F401
    tx_config,  # noqa: F401
)
from chia._tests.environments.wallet import WalletStateTransition, WalletTestFramework  # noqa: PLC2701
from chia._tests.wallet.conftest import wallet_environments  # noqa: PLC2701, F401
from chia.pools.plotnft_drivers import RewardPuzzle
from chia.pools.pool_wallet_info import NewPoolWalletInitialTargetState, PoolSingletonState
from chia.types.blockchain_format.program import Program
from chia.wallet.plotnft_wallet.plotnft_wallet import PlotNFT2Wallet
from chia.wallet.wallet_request_types import CreateNewWallet, CreateNewWalletType, WalletCreationMode
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint32, uint64


def thirty_two_bytes(*, id_num: int) -> bytes32:
    return bytes32(bytes([id_num] * 32))


@pytest.mark.parametrize(
    "wallet_environments",
    [{"num_environments": 2, "blocks_needed": [1, 1]}],
    indirect=True,
)
@pytest.mark.anyio
@pytest.mark.standard_block_tools
async def test_service(reference_service: tuple[ServiceAPI, PropertyMock], wallet_envs: WalletTestFramework) -> None:
    service, current_time = reference_service

    # Make plotnfts
    env = wallet_envs.environments[1]
    for _ in range(2):
        await env.rpc_client.create_new_wallet(
            request=CreateNewWallet(
                wallet_type=CreateNewWalletType.POOL_WALLET,
                mode=WalletCreationMode.NEW,
                initial_target_state=NewPoolWalletInitialTargetState(
                    state=PoolSingletonState.FARMING_TO_POOL.name,
                    target_puzzle_hash=bytes32.from_hexstr(service.config["pool_identity"]["pool_claim_hash"]),
                    pool_url="don't matter",
                    relative_lock_height=uint32(service.config["pool_identity"]["relative_lock_height"]),
                    pool_memoization=Program.fromhex(service.config["pool_identity"]["pool_memoization"]),
                ),
                plotnft_version=uint8(2),
                push=True,
            ),
            tx_config=wallet_envs.tx_config,
        )
        await wallet_envs.full_node.wait_for_wallet_synced(wallet_node=env.node)
    await wallet_envs.process_pending_states(
        [
            WalletStateTransition(),
            WalletStateTransition(
                pre_block_balance_updates={1: {"set_remainder": True}},
                post_block_balance_updates={
                    1: {"set_remainder": True},
                    2: {"init": True, "set_remainder": True},
                    3: {"init": True, "set_remainder": True},
                },
            ),
        ]
    )

    farmer_1_wallet = env.wallet_state_manager.wallets[uint32(2)]
    farmer_2_wallet = env.wallet_state_manager.wallets[uint32(3)]
    assert isinstance(farmer_1_wallet, PlotNFT2Wallet)
    assert isinstance(farmer_2_wallet, PlotNFT2Wallet)
    farmer_1_launcher_id = farmer_1_wallet.plotnft_id
    farmer_2_launcher_id = farmer_2_wallet.plotnft_id
    async with env.wallet_state_manager.new_action_scope(wallet_envs.tx_config, push=True) as action_scope:
        farmer_1_user_puzhash = await action_scope.get_puzzle_hash(env.wallet_state_manager)
        farmer_2_user_puzhash = await action_scope.get_puzzle_hash(env.wallet_state_manager)
    farmer_1_difficulty = uint64(100)
    farmer_2_difficulty = uint64(200)
    farmer_1_authentication_pubkey = (await farmer_1_wallet.get_current_plotnft()).user_config.synthetic_pubkey
    farmer_2_authentication_pubkey = (await farmer_2_wallet.get_current_plotnft()).user_config.synthetic_pubkey
    farmer_1_rewards_hash = RewardPuzzle(singleton_id=farmer_1_launcher_id).puzzle_hash()
    farmer_2_rewards_hash = RewardPuzzle(singleton_id=farmer_2_launcher_id).puzzle_hash()

    await service.store.add_farmer(
        version=uint8(2),
        launcher_id=farmer_1_launcher_id,
        payout_instructions=farmer_1_user_puzhash.hex(),
        difficulty=farmer_1_difficulty,
        authentication_public_key=farmer_1_authentication_pubkey,
    )
    await service.store.add_farmer(
        version=uint8(2),
        launcher_id=farmer_2_launcher_id,
        payout_instructions=farmer_2_user_puzhash.hex(),
        difficulty=farmer_2_difficulty,
        authentication_public_key=farmer_2_authentication_pubkey,
    )

    # Test singeton scan
    await service.check_for_singletons()
    assert (await service.store.get_latest_singleton(launcher_id=farmer_1_launcher_id))["coin_id"] == (
        await farmer_1_wallet.get_current_plotnft()
    ).coin.name()
    assert (await service.store.get_latest_singleton(launcher_id=farmer_2_launcher_id))["coin_id"] == (
        await farmer_2_wallet.get_current_plotnft()
    ).coin.name()

    # Test partial confirmation
    await service.store.add_partial(
        launcher_id=farmer_1_launcher_id,
        partial=PartialMetadata(
            timestamp=service.current_time,
            difficulty=uint64(1),
            challenge_hash=bytes32.zeros,
            pos_hash=thirty_two_bytes(id_num=1),
            end_of_sub_slot=True,
            pool_contract_puzzle_hash=farmer_1_rewards_hash,
        ),
    )
    await service.store.add_partial(
        launcher_id=farmer_2_launcher_id,
        partial=PartialMetadata(
            timestamp=uint64(service.current_time + 1),
            difficulty=uint64(2),
            challenge_hash=bytes32.zeros,
            pos_hash=thirty_two_bytes(id_num=2),
            end_of_sub_slot=False,
            pool_contract_puzzle_hash=farmer_2_rewards_hash,
        ),
    )
    await service.store.add_partial(
        launcher_id=farmer_2_launcher_id,
        partial=PartialMetadata(
            timestamp=uint64(service.current_time + 2),
            difficulty=uint64(2),
            challenge_hash=bytes32.zeros,
            pos_hash=thirty_two_bytes(id_num=3),
            end_of_sub_slot=False,
            pool_contract_puzzle_hash=farmer_2_rewards_hash,
        ),
    )
    assert len((await service.store.get_partials(launcher_id=farmer_1_launcher_id, confirmed=True))["partials"]) == 0
    assert len((await service.store.get_partials(launcher_id=farmer_2_launcher_id, confirmed=True))["partials"]) == 0
    await service.confirm_partials()
    assert len((await service.store.get_partials(launcher_id=farmer_1_launcher_id, confirmed=True))["partials"]) == 0
    assert len((await service.store.get_partials(launcher_id=farmer_2_launcher_id, confirmed=True))["partials"]) == 0
    current_time.return_value += service.config["partial_confirmation_delay"] + 1
    with patch.object(
        service.full_node,
        "get_recent_end_of_subslot",
        new=AsyncMock(
            return_value=GetRecentSignagePointOrEOSResponse(
                eos=PropertyMock(), signage_point=None, time_received=service.current_time, exists=True, reverted=False
            )
        ),
    ):
        await service.confirm_partials()
    assert len((await service.store.get_partials(launcher_id=farmer_1_launcher_id, confirmed=True))["partials"]) == 1
    assert len((await service.store.get_partials(launcher_id=farmer_2_launcher_id, confirmed=True))["partials"]) == 0
    current_time.return_value += 1
    with patch.object(
        service.full_node,
        "get_recent_signage_point",
        new=AsyncMock(
            return_value=GetRecentSignagePointOrEOSResponse(
                eos=None, signage_point=PropertyMock(), time_received=service.current_time, exists=True, reverted=False
            )
        ),
    ):
        await service.confirm_partials()
    assert len((await service.store.get_partials(launcher_id=farmer_2_launcher_id, confirmed=True))["partials"]) == 1
    assert len((await service.store.get_partials(launcher_id=farmer_2_launcher_id, confirmed=False))["partials"]) == 1
    current_time.return_value += 1
    with patch.object(
        service.full_node,
        "get_recent_signage_point",
        new=AsyncMock(
            return_value=GetRecentSignagePointOrEOSResponse(
                eos=None, signage_point=PropertyMock(), time_received=service.current_time, exists=True, reverted=True
            )
        ),
    ):
        await service.confirm_partials()
    assert len((await service.store.get_partials(launcher_id=farmer_2_launcher_id, confirmed=True))["partials"]) == 1
    assert len((await service.store.get_partials(launcher_id=farmer_2_launcher_id, confirmed=False))["partials"]) == 0

    # Test pool reward claims
    farmer_1_reward_amount = await wallet_envs.full_node.farm_blocks_to_puzzlehash(
        count=1, farm_to=farmer_1_wallet.p2_singleton_puzzle_hash, guarantee_transaction_blocks=True, timeout=100
    )
    farmer_2_reward_amount = await wallet_envs.full_node.farm_blocks_to_puzzlehash(
        count=1, farm_to=farmer_2_wallet.p2_singleton_puzzle_hash, guarantee_transaction_blocks=True, timeout=100
    )
    await wallet_envs.process_pending_states(
        [
            WalletStateTransition(),
            WalletStateTransition(
                pre_block_balance_updates={
                    1: {"set_remainder": True},
                    2: {"set_remainder": True},
                    3: {"set_remainder": True},
                },
                post_block_balance_updates={
                    1: {"set_remainder": True},
                    2: {"set_remainder": True},
                    3: {"set_remainder": True},
                },
            ),
        ]
    )
    await service.collect_pool_rewards()
    total_pooling_reward_amount = int((farmer_1_reward_amount + farmer_2_reward_amount) * (7 / 8))
    await wallet_envs.process_pending_states(
        [
            WalletStateTransition(
                pre_block_balance_updates={
                    1: {
                        "unconfirmed_wallet_balance": total_pooling_reward_amount,
                        "pending_coin_removal_count": 2,
                    }
                },
                post_block_balance_updates={
                    1: {
                        "confirmed_wallet_balance": total_pooling_reward_amount,
                        "spendable_balance": total_pooling_reward_amount,
                        "max_send_amount": total_pooling_reward_amount,
                        "unspent_coin_count": 2,
                        "pending_coin_removal_count": -2,
                    }
                },
            ),
            WalletStateTransition(
                pre_block_balance_updates={
                    1: {"set_remainder": True},
                    2: {"set_remainder": True},
                    3: {"set_remainder": True},
                },
                post_block_balance_updates={
                    1: {"set_remainder": True},
                    2: {"set_remainder": True},
                    3: {"set_remainder": True},
                },
            ),
        ]
    )
    await service.collect_pool_rewards()  # another call to mark tx as confirmed
    await service.submit_payments()
    assert (await service.store.get_unpaid_reward_claims())["claims"] == []
    BASIS = 10_000
    reward_total_minus_fee = int(total_pooling_reward_amount * (1 - service.config["fee_basis_points"] / BASIS))
    await wallet_envs.process_pending_states(
        [
            WalletStateTransition(
                pre_block_balance_updates={
                    1: {
                        "unconfirmed_wallet_balance": -reward_total_minus_fee,
                        ">=#pending_coin_removal_count": 1,
                        "<=#spendable_balance": 0,
                        "<=#max_send_amount": 0,
                        ">=#pending_change": 0,
                    }
                },
                post_block_balance_updates={
                    1: {
                        "confirmed_wallet_balance": -reward_total_minus_fee,
                        ">=#spendable_balance": 0,
                        ">=#max_send_amount": 0,
                        "<=#unspent_coin_count": 0,
                        "<=#pending_coin_removal_count": -1,
                        "<=#pending_change": 0,
                    }
                },
            ),
            WalletStateTransition(
                pre_block_balance_updates={
                    1: {},
                    2: {},
                    3: {},
                },
                post_block_balance_updates={
                    1: {
                        "confirmed_wallet_balance": reward_total_minus_fee,
                        "unconfirmed_wallet_balance": reward_total_minus_fee,
                        "spendable_balance": reward_total_minus_fee,
                        "max_send_amount": reward_total_minus_fee,
                        "unspent_coin_count": 2,
                    },
                    2: {},
                    3: {},
                },
            ),
        ],
    )
    payment_amount_1 = int(reward_total_minus_fee * (2 / 3))
    payment_amount_2 = int(reward_total_minus_fee * (1 / 3))
    async with env.wallet_state_manager.new_action_scope(wallet_envs.tx_config, push=False) as action_scope:
        coin_set = await env.xch_wallet.select_coins(uint64(await env.xch_wallet.get_confirmed_balance()), action_scope)
        assert payment_amount_1 in {coin.amount for coin in coin_set}
        assert payment_amount_2 in {coin.amount for coin in coin_set}
