from __future__ import annotations

import asyncio
import pathlib

import click
import yaml
from chia_rs.sized_bytes import bytes32
from node.config import CONFIG_FILE_NAME as NODE_CONFIG_FILE
from node.rpc_wrapper import NodeRPC
from server.config import CONFIG_FILE_NAME as SERVER_CONFIG_FILE
from server.farmer_rpc import FarmerRPCServer
from server.pooling_tasks import PoolServer
from service.config import CONFIG_FILE_NAME as SERVICE_CONFIG_FILE
from service.service import Service
from store.config import CONFIG_FILE_NAME as STORE_CONFIG_FILE
from store.sqlite import Store
from wallet.config import CONFIG_FILE_NAME as WALLET_CONFIG_FILE
from wallet.rpc_wrapper import WalletRPC


@click.group()
def cli() -> None:
    pass


async def start_async(auth_sk: bytes32) -> None:
    async with NodeRPC.create() as node_rpc, WalletRPC.create() as wallet_rpc, Store.create() as store:
        service = Service.create(store=store, full_node=node_rpc, wallet=wallet_rpc)
        async with (
            PoolServer.create_pool_tasks(service=service),
            FarmerRPCServer.create_rpc(farmer_rpcs={}, handlers={}, service=service, token_sk=auth_sk),
        ):
            await asyncio.Event().wait()


@cli.command()
@click.option("--auth-sk", type=str, required=True, help="The 32-byte secret key to use for farmer authentication")
def start(auth_sk: str) -> None:
    """Start the application."""
    asyncio.run(start_async(bytes32.from_hexstr(auth_sk)))


@cli.command()
@click.option("--store-path", type=click.Path(exists=False), required=True, help="The path to the store database file")
@click.option(
    "--hostname",
    type=str,
    required=True,
    help="The hostname to use for the service",
    show_default=True,
    default="127.0.0.1",
)
@click.option("--full-node-rpc-port", type=int, required=True, help="The port to use for the full node RPC server")
@click.option("--wallet-rpc-port", type=int, required=True, help="The port to use for the wallet RPC server")
@click.option("--chia-root", type=click.Path(exists=True), required=True, help="The path to the chia root directory")
@click.option(
    "--rpc-timeout", type=int, required=True, help="The RPC timeout in seconds", show_default=True, default=120
)
@click.option("--daemon-ssl-crt", type=click.Path(), required=True, help="The path to the daemon SSL certificate")
@click.option("--daemon-ssl-key", type=click.Path(), required=True, help="The path to the daemon SSL key")
@click.option(
    "--full-node-private-ssl-crt",
    type=click.Path(),
    required=True,
    help="The path to the Full Node private SSL CA certificate",
)
@click.option(
    "--full-node-private-ssl-key",
    type=click.Path(),
    required=True,
    help="The path to the Full Node private SSL CA key",
)
@click.option(
    "--wallet-private-ssl-crt",
    type=click.Path(),
    required=True,
    help="The path to the Wallet private SSL CA certificate",
)
@click.option(
    "--wallet-private-ssl-key",
    type=click.Path(),
    required=True,
    help="The path to the Wallet private SSL CA key",
)
@click.option(
    "--relative-lock-height",
    type=int,
    required=True,
    help="The amount of blocks it takes for a farmer to leave the pool (POOL IDENTITY)",
    show_default=True,
    default=20,
)
@click.option(
    "--pool-wallet-address",
    type=str,
    required=True,
    help="The place where farmer rewards will be sent (POOL IDENTITY)",
)
@click.option(
    "--pool-memoization",
    type=str,
    required=True,
    help="The (clvm hex of) remaining arguments to CREATE_COIN when payments are made to a pool (POOL IDENTITY)",
    show_default=True,
    default="80",
)
@click.option(
    "--min-difficulty",
    type=int,
    required=True,
    help="The minimum difficulty for a farmer to be included in the pool",
    show_default=True,
    default=0,
)
@click.option(
    "--default-difficulty",
    type=int,
    required=True,
    help="The default difficulty for a farmer if a difficulty is not suggested",
    show_default=True,
    default=0,
)
@click.option(
    "--partial-time-limit",
    type=int,
    required=True,
    help="The time limit for partial submissions in seconds",
    show_default=True,
    default=120,
)
@click.option(
    "--partial-confirmation-delay",
    type=int,
    required=True,
    help="The delay in seconds before a partial submission is confirmed",
    show_default=True,
    default=600,
)
@click.option(
    "--scan-start-height",
    type=int,
    required=True,
    help="The height at which to start scanning for blocks",
    show_default=True,
    default=8455205,
)
@click.option(
    "--collect-pool-rewards-interval",
    type=int,
    required=True,
    help="The interval in seconds between collecting pool rewards",
    show_default=True,
    default=600,
)
@click.option(
    "--confirmation-security-threshold",
    type=int,
    required=True,
    help="The number of confirmations required for a block to be considered valid",
    show_default=True,
    default=2,
)
@click.option(
    "--payment-interval",
    type=int,
    required=True,
    help="The interval in seconds between distributing farmer payouts",
    show_default=True,
    default=3600 * 12,
)
@click.option(
    "--max-additions-per-transaction",
    type=int,
    required=True,
    help="The maximum number of additions per transaction",
    show_default=True,
    default=500,
)
@click.option(
    "--number-of-partials-target",
    type=int,
    required=True,
    help="Don't actually know what this is",
    show_default=True,
    default=0,
)
@click.option(
    "--time-target",
    type=int,
    required=True,
    help="Nor this",
    show_default=True,
    default=0,
)
@click.option(
    "--fee",
    type=int,
    required=True,
    help="The fee, in basis points, that the pool takes from the farmer's reward",
    show_default=True,
    default=0,
)
@click.option(
    "--genesis-challenge",
    type=str,
    required=True,
    help="The genesis challenge of the network this pool is running on",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    required=True,
    help="The logging level",
    show_default=True,
    default="DEBUG",
)
@click.option(
    "--log-stdout/--no-log-stdout",
    required=True,
    help="Whether to log to stdout",
    show_default=True,
    default=True,
)
@click.option(
    "--log-syslog/--no-log-syslog",
    required=True,
    help="Whether to log to syslog",
    show_default=True,
    default=True,
)
@click.option(
    "--log-syslog-host",
    type=str,
    required=True,
    help="The syslog host",
    show_default=True,
    default="",
)
@click.option(
    "--log-syslog-port",
    type=int,
    required=True,
    help="The syslog port",
    show_default=True,
    default=514,
)
@click.option(
    "--log-filename",
    type=str,
    required=True,
    help="The log filename",
    show_default=True,
    default="",
)
@click.option(
    "--log-maxfilesrotation",
    type=int,
    required=True,
    help="The maximum number of log files to keep during rotation",
    show_default=True,
    default=7,
)
@click.option(
    "--log-max-bytes-rotation",
    type=int,
    required=True,
    help="The maximum number of bytes per log file before rotation",
    show_default=True,
    default=52428800,
)
@click.option(
    "--log-use-gzip/--no-log-use-gzip",
    required=True,
    help="Whether to gzip rotated log files",
    show_default=True,
    default=True,
)
@click.option(
    "--pool-name",
    type=str,
    required=True,
    help="The name of the pool",
    show_default=True,
    default="",
)
@click.option(
    "--pool-logo-url",
    type=str,
    required=True,
    help="The URL of the pool logo",
    show_default=True,
    default="",
)
@click.option(
    "--pool-description",
    type=str,
    required=True,
    help="The description of the pool",
    show_default=True,
    default="",
)
@click.option(
    "--pool-welcome-message",
    type=str,
    required=True,
    help="The welcome message for the pool",
    show_default=True,
    default="",
)
@click.option(
    "--pool-minimum-difficulty",
    type=int,
    required=True,
    help="The minimum difficulty shown in pool info",
    show_default=True,
    default=0,
)
@click.option(
    "--web-host",
    type=str,
    required=True,
    help="The host for the web server",
    show_default=True,
    default="localhost",
)
@click.option(
    "--web-port",
    type=int,
    required=True,
    help="The port for the web server",
    show_default=True,
    default=8080,
)
@click.option(
    "--ssl-cert-path",
    type=click.Path(),
    required=True,
    help="The path to the SSL certificate for the web server",
)
@click.option(
    "--ssl-key-path",
    type=click.Path(),
    required=True,
    help="The path to the SSL key for the web server",
)
@click.option(
    "--service-loop-intervals",
    type=int,
    required=True,
    help="The interval in seconds for the service loop",
    show_default=True,
    default=1,
)
@click.option(
    "--authentication-token-timeout",
    type=int,
    required=True,
    help="The timeout in seconds for authentication tokens",
    show_default=True,
    default=0,
)
def generate_config(
    *,
    store_path: str,
    hostname: str,
    full_node_rpc_port: int,
    wallet_rpc_port: int,
    chia_root: str,
    rpc_timeout: int,
    daemon_ssl_crt: str,
    daemon_ssl_key: str,
    full_node_private_ssl_crt: str,
    full_node_private_ssl_key: str,
    wallet_private_ssl_crt: str,
    wallet_private_ssl_key: str,
    relative_lock_height: int,
    pool_wallet_address: str,
    pool_memoization: str,
    min_difficulty: int,
    default_difficulty: int,
    partial_time_limit: int,
    partial_confirmation_delay: int,
    scan_start_height: int,
    collect_pool_rewards_interval: int,
    confirmation_security_threshold: int,
    payment_interval: int,
    max_additions_per_transaction: int,
    number_of_partials_target: int,
    time_target: int,
    fee: int,
    genesis_challenge: str,
    log_level: str,
    log_stdout: bool,
    log_syslog: bool,
    log_syslog_host: str,
    log_syslog_port: int,
    log_filename: str,
    log_maxfilesrotation: int,
    log_max_bytes_rotation: int,
    log_use_gzip: bool,
    pool_name: str,
    pool_logo_url: str,
    pool_description: str,
    pool_welcome_message: str,
    pool_minimum_difficulty: int,
    web_host: str,
    web_port: int,
    ssl_cert_path: str,
    ssl_key_path: str,
    service_loop_intervals: int,
    authentication_token_timeout: int,
) -> None:
    """Generate all configuration files."""
    server_config_path = pathlib.Path.home().joinpath(SERVER_CONFIG_FILE)
    service_config_path = pathlib.Path.home().joinpath(SERVICE_CONFIG_FILE)
    node_config_path = pathlib.Path.home().joinpath(NODE_CONFIG_FILE)
    wallet_config_path = pathlib.Path.home().joinpath(WALLET_CONFIG_FILE)
    store_config_path = pathlib.Path.home().joinpath(STORE_CONFIG_FILE)
    if not store_config_path.exists():
        store_config_path.touch()
    if not service_config_path.exists():
        service_config_path.touch()
    if not node_config_path.exists():
        node_config_path.touch()
    if not wallet_config_path.exists():
        wallet_config_path.touch()
    if not server_config_path.exists():
        server_config_path.touch()
    with store_config_path.open(mode="w") as file:
        yaml.dump({"store_path": store_path}, file)
    with node_config_path.open(mode="w") as file:
        yaml.dump(
            {
                "self_hostname": hostname,
                "rpc_port": full_node_rpc_port,
                "root_path": chia_root,
                "net_config": {
                    "rpc_timeout": rpc_timeout,
                    "daemon_ssl": {
                        "private_crt": daemon_ssl_crt,
                        "private_key": daemon_ssl_key,
                    },
                    "private_ssl_ca": {
                        "crt": full_node_private_ssl_crt,
                        "key": full_node_private_ssl_key,
                    },
                },
            },
            file,
        )
    with wallet_config_path.open(mode="w") as file:
        yaml.dump(
            {
                "self_hostname": hostname,
                "rpc_port": wallet_rpc_port,
                "root_path": chia_root,
                "net_config": {
                    "rpc_timeout": rpc_timeout,
                    "daemon_ssl": {
                        "private_crt": daemon_ssl_crt,
                        "private_key": daemon_ssl_key,
                    },
                    "private_ssl_ca": {
                        "crt": wallet_private_ssl_crt,
                        "key": wallet_private_ssl_key,
                    },
                },
            },
            file,
        )
    with service_config_path.open(mode="w") as file:
        yaml.dump(
            {
                "pool_identity": {
                    "relative_lock_height": relative_lock_height,
                    "pool_claim_hash": pool_wallet_address,
                    "pool_memoization": pool_memoization,
                },
                "min_difficulty": min_difficulty,
                "default_difficulty": default_difficulty,
                "partial_time_limit": partial_time_limit,
                "partial_confirmation_delay": partial_confirmation_delay,
                "scan_start_height": scan_start_height,
                "collect_pool_rewards_interval": collect_pool_rewards_interval,
                "confirmation_security_threshold": confirmation_security_threshold,
                "payment_interval": payment_interval,
                "max_additions_per_transaction": max_additions_per_transaction,
                "number_of_partials_target": number_of_partials_target,
                "time_target": time_target,
                "fee_basis_points": fee,
                "genesis_challenge": genesis_challenge,
            },
            file,
        )
    with server_config_path.open(mode="w") as file:
        yaml.dump(
            {
                "logging": {
                    "log_level": log_level,
                    "log_stdout": log_stdout,
                    "log_syslog": log_syslog,
                    "log_syslog_host": log_syslog_host,
                    "log_syslog_port": log_syslog_port,
                    "log_filename": log_filename,
                    "log_maxfilesrotation": log_maxfilesrotation,
                    "log_max_bytes_rotation": log_max_bytes_rotation,
                    "log_use_gzip": log_use_gzip,
                },
                "pool_info": {
                    "name": pool_name,
                    "logo_url": pool_logo_url,
                    "description": pool_description,
                    "welcome_message": pool_welcome_message,
                    "minimum_difficulty": pool_minimum_difficulty,
                },
                "web_config": {
                    "host": web_host,
                    "port": web_port,
                    "ssl_cert_path": ssl_cert_path,
                    "ssl_key_path": ssl_key_path,
                },
                "service_loop_intervals": service_loop_intervals,
                "authentication_token_timeout": authentication_token_timeout,
            },
            file,
        )


if __name__ == "__main__":
    cli()
