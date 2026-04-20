from __future__ import annotations

import pathlib
import time
from dataclasses import replace

from api.node_rpc import NodeRPC
from api.service import CONFIG_FILE_NAME, Config
from api.store import PartialMetadata, Store
from api.wallet_rpc import Payment, Wallet
from chia.pools.plotnft_drivers import PlotNFT, PlotNFTPuzzle, PoolConfig, PoolReward, RewardPuzzle, UserConfig
from chia.types.blockchain_format.program import Program
from chia.util.bech32m import decode_puzzle_hash
from chia_rs import G2Element, SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint32, uint64
from config_loading import canonical_load_config
from service.config import ConfigSchema
from typing_extensions import Self


async def confirm_partial(
    *,
    partial: PartialMetadata,
    node_rpc: NodeRPC,
) -> bool:
    if partial.end_of_sub_slot:
        response = await node_rpc.get_recent_end_of_subslot(challenge_hash=partial.challenge_hash)
    else:
        response = await node_rpc.get_recent_signage_point(signage_point_hash=partial.challenge_hash)

    return not (response is None or response["reverted"] or not response["exists"])


def convert_payout_instructions(payout_instructions: str) -> bytes32:
    # TODO: hook for more of these?
    return decode_puzzle_hash(payout_instructions)


class Service:
    store: Store
    full_node: NodeRPC
    wallet: Wallet
    config: Config

    @property
    def current_time(self) -> uint64:
        return uint64(time.time())

    @classmethod
    def create(cls, *, store: Store, full_node: NodeRPC, wallet: Wallet, root_path: pathlib.Path) -> Self:
        self = cls()
        config = canonical_load_config(
            root_path=root_path, config_filename=CONFIG_FILE_NAME, schema_validation=ConfigSchema(), config_type=Config
        )
        self.config = config
        self.store = store
        self.full_node = full_node
        self.wallet = wallet
        return self

    async def confirm_partials(self) -> None:
        """
        The purpose of this task is to confirm partials that have been submitted by farmers after appropriate burial
        """
        launcher_id_response = await self.store.get_launcher_ids()  # TODO: pagination?
        target_timestamp = uint64(self.current_time - self.config["partial_confirmation_delay"])
        for launcher_id in launcher_id_response["launcher_ids"]:
            partials_response = await self.store.get_partials(
                launcher_id=launcher_id,
                confirmed=False,
                before=target_timestamp,
            )
            for partial in partials_response["partials"]:
                if not await confirm_partial(
                    partial=partial,
                    node_rpc=self.full_node,
                ):
                    await self.store.delete_partial(launcher_id=launcher_id, timestamp=partial.timestamp)

            await self.store.confirm_partials(launcher_id=launcher_id, until_timestamp=target_timestamp)

    async def check_for_singletons(self) -> None:
        """
        The purpose of this task is to follow farmer singletons to monitor for any exits initiated or completed.
        """
        # TODO: v1
        peak_height = (await self.full_node.get_blockchain_state())["peak"]
        launcher_id_response = await self.store.get_launcher_ids()  # TODO: pagination?
        for launcher_id in launcher_id_response["launcher_ids"]:
            farmer_response = await self.store.get_farmer(launcher_id=launcher_id)
            plotnft_puzzle = PlotNFTPuzzle(
                launcher_id=launcher_id,
                genesis_challenge=bytes32.from_hexstr(self.config["genesis_challenge"]),
                user_config=UserConfig(synthetic_pubkey=farmer_response["authentication_public_key"]),
                exiting=False,
                pool_config=PoolConfig(
                    pool_puzzle_hash=bytes32.from_hexstr(self.config["pool_identity"]["pool_claim_hash"]),
                    heightlock=uint32(self.config["pool_identity"]["relative_lock_height"]),
                    pool_memoization=Program.fromhex(self.config["pool_identity"]["pool_memoization"]),
                ),
            )
            plotnft_puzzle_exiting = replace(plotnft_puzzle, exiting=True)
            plotnfts_response = await self.full_node.get_coin_records_by_puzzle_hashes(
                puzzle_hashes=[plotnft_puzzle.puzzle_hash(nonce=0), plotnft_puzzle_exiting.puzzle_hash(nonce=0)],
                include_spent_coins=False,
                start_height=uint32(self.config["scan_start_height"]),  # TODO: persist height scanned
            )
            if len(plotnfts_response["coin_records"]) > 1:
                raise ValueError("Multiple plot NFTs found")
            if len(plotnfts_response["coin_records"]) == 0:
                raise ValueError("No plot NFT found")  # TODO: delete farmer?
            plotnft_coin = plotnfts_response["coin_records"][0]
            if plotnft_coin.confirmed_block_index > peak_height - self.config["confirmation_security_threshold"]:
                continue
            if plotnft_coin.coin.puzzle_hash == plotnft_puzzle_exiting.puzzle_hash(nonce=0):
                exiting_height = uint32(
                    plotnft_coin.confirmed_block_index + self.config["pool_identity"]["relative_lock_height"]
                )
            else:
                exiting_height = None
            # TODO: some re-org robustness might be nice
            # If somehow this gets added and then a reorg makes it happen at an earlier block height,
            # we're going to be in an awkward state
            await self.store.add_singleton(
                launcher_id=launcher_id,
                coin_id=plotnft_coin.coin.name(),
                created_height=plotnft_coin.confirmed_block_index,
                exiting_height=exiting_height,
            )

    async def collect_pool_rewards(self) -> None:
        """
        The purpose of this task is to forward to the pool any pool rewards that farmers have successfully farmed.
        """
        # TODO: v1
        peak_height = (await self.full_node.get_blockchain_state())["peak"]
        launcher_id_response = await self.store.get_launcher_ids()  # TODO: pagination?
        launcher_id_to_reward_hash: dict[bytes32, bytes32] = {}
        for launcher_id in launcher_id_response["launcher_ids"]:
            # TODO: cache
            launcher_id_to_reward_hash[launcher_id] = RewardPuzzle(singleton_id=launcher_id).puzzle_hash()
        response = await self.full_node.get_coin_records_by_puzzle_hashes(
            puzzle_hashes=list(launcher_id_to_reward_hash.values()),
            include_spent_coins=False,
            start_height=uint32(self.config["scan_start_height"]),  # TODO: persist height scanned
        )

        reward_hashes = set(cr.coin.puzzle_hash for cr in response["coin_records"])

        all_spends = []  # TODO: batching
        reward_amount = 0
        for launcher_id in launcher_id_response["launcher_ids"]:
            if launcher_id_to_reward_hash[launcher_id] not in reward_hashes:
                continue
            latest_singleton_response = await self.store.get_latest_singleton(launcher_id=launcher_id)
            plotnft_coin_record = (
                await self.full_node.get_coin_record_by_name(coin_id=latest_singleton_response["coin_id"])
            )["coin_record"]
            plotnft_parent_record = (
                await self.full_node.get_coin_record_by_name(coin_id=plotnft_coin_record.coin.parent_coin_info)
            )["coin_record"]
            last_spend = (
                await self.full_node.get_puzzle_and_solution(
                    coin_id=plotnft_parent_record.coin.name(), height=plotnft_parent_record.spent_block_index
                )
            )["spend"]
            plotnft = PlotNFT.get_next_from_coin_spend(
                coin_spend=last_spend,
                genesis_challenge=bytes32.from_hexstr(self.config["genesis_challenge"]),
            )
            all_rewards = [
                reward_record
                for reward_record in response["coin_records"]
                if reward_record.coin.puzzle_hash == launcher_id_to_reward_hash[launcher_id]
                and reward_record.coin.parent_coin_info[0:16] == bytes.fromhex(self.config["genesis_challenge"])[0:16]
                and reward_record.confirmed_block_index <= peak_height - self.config["confirmation_security_threshold"]
            ]
            if len(all_rewards) > 0:
                all_spends.extend(
                    plotnft.forward_pool_reward(
                        PoolReward(  # TODO: with underlying drivers, fix this to not require height
                            singleton_id=launcher_id,
                            coin=all_rewards[0].coin,
                            height=uint32.from_bytes(all_rewards[0].coin.parent_coin_info[28:]),
                        )
                    )
                )
                reward_amount += all_rewards[0].coin.amount

        # TODO: fee
        # TODO: persist and check tx_ids
        if len(all_spends) > 0:
            await self.wallet.submit_transaction(spend_bundle=SpendBundle(all_spends, G2Element()), fee=uint64(0))
            await self.store.add_reward_claim(  # TODO: make contingent on tx confirmation
                timestamp=self.current_time, amount=uint64(reward_amount)
            )

    async def submit_payments(self) -> None:
        """
        The purpose of this task is to payout farmers from a pool's wallet to credit them for the work proportional
        to the amount of total work done for the pool over the interval since the last payout.
        """
        timestamp = self.current_time
        user_difficulty_points: dict[bytes32, int] = {}
        user_payout_instructions: dict[bytes32, str] = {}
        last_payout = await self.store.get_latest_payout()
        for launcher_id in (await self.store.get_launcher_ids())["launcher_ids"]:
            since = 0 if last_payout is None else last_payout["timestamp"]
            unpaid_partials = (
                await self.store.get_partials(
                    launcher_id=launcher_id, since=uint64(since), before=timestamp, confirmed=True
                )
            )["partials"]
            if len(unpaid_partials) > 0:
                user_difficulty_points[launcher_id] = sum(partial.difficulty for partial in unpaid_partials)
                user_payout_instructions[launcher_id] = (await self.store.get_farmer(launcher_id=launcher_id))[
                    "payout_instructions"
                ]

        BASIS = 10000
        reward_claims = await self.store.get_unpaid_reward_claims()
        reward_total = int(
            sum(claim["amount"] for claim in reward_claims["claims"]) * (1 - self.config["fee_basis_points"] / BASIS)
        )
        total_points = sum(user_difficulty_points.values())

        raw = {user: reward_total * points / total_points for user, points in user_difficulty_points.items()}

        # Floor them
        payouts = {u: int(v) for u, v in raw.items()}
        distributed = sum(payouts.values())

        # Distribute remainder by largest fractional parts
        remainder = reward_total - distributed
        fractions = sorted(raw.items(), key=lambda item: item[1] - int(item[1]), reverse=True)
        for user, _ in fractions[:remainder]:
            payouts[user] += 1

        # TODO: fee
        # TODO: persist and check tx_ids
        # TODO: persist claims pending payouts
        for i in range(0, len(payouts), self.config["max_additions_per_transaction"]):
            payout_batch = {
                user: payouts[user]
                for user in list(payouts.keys())[
                    i : min(i + self.config["max_additions_per_transaction"], len(payouts))
                ]
            }
            if len(payout_batch) > 0:
                await self.wallet.send_transaction(
                    payments=[
                        Payment(
                            puzzle_hash=(puzzle_hash := convert_payout_instructions(user_payout_instructions[user])),
                            amount=uint64(amount),
                            memos=[puzzle_hash.hex()],
                        )
                        for user, amount in payout_batch.items()
                    ],
                    fee=uint64(0),
                )
                await self.store.add_payout(
                    timestamp=timestamp,
                    payout_details="",  # TODO: delete this?
                )
        await self.store.set_claims_statuses(timestamps=[claim["timestamp"] for claim in reward_claims["claims"]])
