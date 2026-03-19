from __future__ import annotations

import pathlib
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
import yaml
from api.wallet import Payment, Wallet
from chia._tests.conftest import (
    blockchain_constants,  # noqa: PLC2701, F401
    consensus_mode,  # noqa: PLC2701, F401
    self_hostname,  # noqa: PLC2701, F401
    trusted_full_node,  # noqa: PLC2701, F401
    tx_config,  # noqa: PLC2701, F401
)
from chia._tests.environments.wallet import WalletStateTransition, WalletTestFramework  # noqa: PLC2701
from chia._tests.wallet.conftest import wallet_environments  # noqa: PLC2701, F401
from chia.types.coin_spend import make_spend
from chia.wallet.conditions import CreateCoin
from chia_rs import G2Element, Program, SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint64
from wallet.config import CONFIG_FILE_NAME
from wallet.rpc_wrapper import WalletRPC

if TYPE_CHECKING:
    node: type[Wallet] = WalletRPC


@pytest.fixture
def environments(
    self_hostname: str,  # noqa: F811
    wallet_environments: WalletTestFramework,  # noqa: F811
) -> Iterator[WalletTestFramework]:
    env = wallet_environments.environments[0]
    config_path = pathlib.Path.cwd().joinpath(CONFIG_FILE_NAME)
    try:
        config_path.touch()
        with config_path.open(mode="w") as file:
            yaml.dump(
                {
                    "self_hostname": self_hostname,
                    "rpc_port": env.rpc_server.listen_port,
                    "root_path": str(env.node.root_path),
                    "net_config": {
                        "rpc_timeout": env.service.config["rpc_timeout"],
                        "daemon_ssl": env.service.config["daemon_ssl"],
                        "private_ssl_ca": env.service.config["private_ssl_ca"],
                    },
                },
                file,
            )
        yield wallet_environments
    finally:
        if config_path.exists():
            config_path.unlink()


@pytest.mark.parametrize(
    "wallet_environments",
    [{"num_environments": 1, "blocks_needed": [1]}],
    indirect=True,
)
@pytest.mark.anyio
async def test_rpc_wrapper(environments: WalletTestFramework) -> None:
    async with WalletRPC.create() as rpc_client:
        AMOUNT_SENT = uint64(100)
        FEE = uint64(50)
        response = await rpc_client.send_transaction(
            payments=[Payment(puzzle_hash=bytes32.zeros, amount=AMOUNT_SENT, memos=None)], fee=FEE
        )

        for tx_id in response["tx_ids"]:
            status = await rpc_client.get_transaction_status(tx_id=tx_id)
            assert not status["confirmed"]

        await environments.process_pending_states(
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

        await environments.full_node.farm_blocks_to_puzzlehash(
            count=1, farm_to=Program.to(1).get_tree_hash(), guarantee_transaction_blocks=True
        )
        await environments.full_node.farm_blocks_to_puzzlehash(count=1, guarantee_transaction_blocks=True)
        coins = await environments.full_node_rpc_client.get_coin_records_by_puzzle_hash(
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

        await environments.process_pending_states(
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
