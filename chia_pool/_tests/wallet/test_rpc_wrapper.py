from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest
from chia._tests.environments.wallet import WalletStateTransition, WalletTestFramework  # noqa: PLC2701
from chia.types.coin_spend import make_spend
from chia.wallet.conditions import CreateCoin
from chia_rs import G2Element, Program, SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint64

from chia_pool.api.wallet_rpc import Payment, Wallet
from chia_pool.wallet.rpc_wrapper import WalletRPC

if TYPE_CHECKING:
    node: type[Wallet] = WalletRPC


@pytest.mark.parametrize(
    "wallet_environments",
    [{"num_environments": 1, "blocks_needed": [1]}],
    indirect=True,
)
@pytest.mark.anyio
async def test_rpc_wrapper(wallet_config: None, wallet_envs: WalletTestFramework, root_path: pathlib.Path) -> None:
    async with WalletRPC.create(root_path=root_path) as rpc_client:
        AMOUNT_SENT = uint64(100)
        FEE = uint64(50)
        response = await rpc_client.send_transaction(
            payments=[Payment(puzzle_hash=bytes32.zeros, amount=AMOUNT_SENT, memos=None)], fee=FEE
        )

        for tx_id in response["tx_ids"]:
            status = await rpc_client.get_transaction_status(tx_id=tx_id)
            assert not status["confirmed"]

        await wallet_envs.process_pending_states(
            [
                WalletStateTransition(
                    pre_block_balance_updates={
                        1: {
                            "unconfirmed_wallet_balance": -(AMOUNT_SENT + FEE),
                            "<=#spendable_balance": -(AMOUNT_SENT + FEE),
                            "<=#max_send_amount": -(AMOUNT_SENT + FEE),
                            ">=#pending_change": 0,
                            ">=#pending_coin_removal_count": 1,
                        }
                    },
                    post_block_balance_updates={
                        1: {
                            "confirmed_wallet_balance": -(AMOUNT_SENT + FEE),
                            ">=#spendable_balance": 0,
                            ">=#max_send_amount": 0,
                            "<=#pending_change": 0,
                            "<=#pending_coin_removal_count": 1,
                        }
                    },
                )
            ]
        )

        for tx_id in response["tx_ids"]:
            status = await rpc_client.get_transaction_status(tx_id=tx_id)
            assert status["confirmed"]

        await wallet_envs.full_node.farm_blocks_to_puzzlehash(
            count=1, farm_to=Program.to(1).get_tree_hash(), guarantee_transaction_blocks=True, timeout=100
        )
        await wallet_envs.full_node.farm_blocks_to_puzzlehash(count=1, guarantee_transaction_blocks=True, timeout=100)
        coins = await wallet_envs.full_node_rpc_client.get_coin_records_by_puzzle_hash(
            puzzle_hash=Program.to(1).get_tree_hash()
        )

        SECOND_AMOUNT_SENT = uint64(1000)
        SECOND_FEE = uint64(500)
        submission = await rpc_client.submit_transaction(
            spend_bundle=SpendBundle(
                [
                    make_spend(
                        next(iter(coins)).coin,
                        Program.to(1),
                        Program.to(
                            [CreateCoin(puzzle_hash=bytes32(bytes([1] * 32)), amount=SECOND_AMOUNT_SENT).to_program()]
                        ),
                    )
                ],
                G2Element(),
            ),
            fee=SECOND_FEE,
        )

        status = await rpc_client.get_transaction_status(tx_id=submission["tx_id"])
        assert not status["confirmed"]

        await wallet_envs.process_pending_states(
            [
                WalletStateTransition(
                    pre_block_balance_updates={
                        1: {
                            "unconfirmed_wallet_balance": -SECOND_FEE,
                            "<=#spendable_balance": -SECOND_FEE,
                            "<=#max_send_amount": -SECOND_FEE,
                            ">=#pending_change": 0,
                            ">=#pending_coin_removal_count": 1,
                        }
                    },
                    post_block_balance_updates={
                        1: {
                            "confirmed_wallet_balance": -SECOND_FEE,
                            ">=#spendable_balance": 0,
                            ">=#max_send_amount": 0,
                            "<=#pending_change": 0,
                            "<=#pending_coin_removal_count": 1,
                        }
                    },
                )
            ]
        )

        status = await rpc_client.get_transaction_status(tx_id=submission["tx_id"])
        assert status["confirmed"]
