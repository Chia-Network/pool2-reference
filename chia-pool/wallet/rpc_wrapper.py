from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from api.rpc import Config
from api.wallet_rpc import (
    CONFIG_FILE_NAME,
    GetTransactionStatusResponse,
    Payment,
    SendTransactionResponse,
    SubmitTransactionResponse,
)
from chia.consensus.default_constants import DEFAULT_CONSTANTS
from chia.util.bech32m import encode_puzzle_hash
from chia.wallet.conditions import ConditionValidTimes
from chia.wallet.transaction_record import TransactionRecord
from chia.wallet.util.compute_memos import compute_memos
from chia.wallet.util.transaction_type import TransactionType
from chia.wallet.util.tx_config import TXConfig, TXConfigLoader
from chia.wallet.wallet_request_types import (
    Addition,
    CreateSignedTransaction,
    GetTransaction,
    PushTransactions,
)
from chia.wallet.wallet_rpc_client import WalletRpcClient
from chia.wallet.wallet_spend_bundle import WalletSpendBundle
from chia_rs import ConsensusConstants, SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint16, uint32, uint64
from config_loading import canonical_load_config
from typing_extensions import Self
from wallet.config import ConfigSchema


class WalletRPC:
    client: WalletRpcClient
    config: Config
    constants: ConsensusConstants

    @classmethod
    @asynccontextmanager
    async def create(cls, root_path: Path) -> AsyncIterator[Self]:
        self = cls()
        config = canonical_load_config(
            root_path=root_path, config_filename=CONFIG_FILE_NAME, schema_validation=ConfigSchema(), config_type=Config
        )
        self.config = config
        async with WalletRpcClient.create_as_context(
            self_hostname=self.config["self_hostname"],
            port=uint16(self.config["rpc_port"]),
            root_path=Path(self.config["root_path"]),
            net_config=self.config["net_config"],
        ) as client:
            self.client = client
            yield self

    @property
    def tx_config(self) -> TXConfig:
        return TXConfigLoader.from_json_dict(self.config["tx_config"]).autofill(constants=DEFAULT_CONSTANTS)

    async def send_transaction(self, *, payments: list[Payment], fee: uint64) -> SendTransactionResponse:
        response = await self.client.create_signed_transactions(
            CreateSignedTransaction(
                additions=[
                    Addition(amount=payment.amount, puzzle_hash=payment.puzzle_hash, memos=payment.memos)
                    for payment in payments
                ],
                fee=fee,
                push=True,
            ),
            tx_config=self.tx_config,
        )
        return SendTransactionResponse(tx_ids=[tx.name for tx in response.transactions])

    async def submit_transaction(self, *, spend_bundle: SpendBundle, fee: uint64) -> SubmitTransactionResponse:
        as_wallet_spend_bundle = WalletSpendBundle(
            coin_spends=spend_bundle.coin_spends,
            aggregated_signature=spend_bundle.aggregated_signature,
        )
        response = await self.client.push_transactions(
            request=PushTransactions(
                transactions=[
                    TransactionRecord(
                        to_puzzle_hash=bytes32.zeros,
                        confirmed_at_height=uint32(0),
                        created_at_time=uint64(0),
                        amount=uint64(sum([spend.coin.amount for spend in spend_bundle.coin_spends])),
                        fee_amount=fee,
                        sent_to=[],
                        name=spend_bundle.name(),
                        type=uint32(TransactionType.OUTGOING_TX.value),
                        memos=compute_memos(as_wallet_spend_bundle),
                        sent=uint32(0),
                        confirmed=False,
                        spend_bundle=as_wallet_spend_bundle,
                        additions=[coin for coin in spend_bundle.additions() if coin.amount != 1],
                        removals=[coin for coin in spend_bundle.removals() if coin.amount != 1],
                        wallet_id=uint32(1),
                        trade_id=None,
                        valid_times=ConditionValidTimes(),
                        to_address=encode_puzzle_hash(bytes32.zeros, "xch"),
                    )
                ],
                fee=fee,
            ),
            tx_config=self.tx_config,
        )
        return SubmitTransactionResponse(tx_id=response.transactions[0].name)

    async def get_transaction_status(self, *, tx_id: bytes32) -> GetTransactionStatusResponse:
        response = await self.client.get_transaction(GetTransaction(transaction_id=tx_id))
        return GetTransactionStatusResponse(confirmed=response.transaction.confirmed)
