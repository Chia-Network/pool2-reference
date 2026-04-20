from __future__ import annotations

import asyncio
import pathlib
from collections.abc import Callable
from typing import Literal

import api
import click
import yaml
from chia_rs.sized_bytes import bytes32
from farmer_rpc import v2
from node.rpc_wrapper import NodeRPC
from server.farmer_rpc import FarmerRPCServer
from server.pooling_tasks import PoolServer
from service.service import Service
from store.sqlite import Store
from wallet.rpc_wrapper import WalletRPC


@click.group()
def cli() -> None:
    pass


async def start_async(*, auth_sk: bytes32, root_path: pathlib.Path) -> None:
    async with (
        NodeRPC.create(root_path=root_path) as node_rpc,
        WalletRPC.create(root_path=root_path) as wallet_rpc,
        Store.create(root_path=root_path) as store,
    ):
        service = Service.create(store=store, full_node=node_rpc, wallet=wallet_rpc, root_path=root_path)
        async with (
            PoolServer.create_pooling_tasks(service=service, root_path=root_path),
            FarmerRPCServer.create_rpc(
                farmer_rpcs={"v2": v2.METADATA},
                handlers={"v2": v2.HANDLERS},
                service=service,
                token_sk=auth_sk,
                root_path=root_path,
            ),
        ):
            await asyncio.Event().wait()


@cli.command()
@click.option("--auth-sk", type=str, required=True, help="The 32-byte secret key to use for farmer authentication")
@click.option("--root-path", type=pathlib.Path, required=True, help="The root path for the config files")
def start(auth_sk: str, root_path: pathlib.Path) -> None:
    """Start the application."""
    asyncio.run(start_async(auth_sk=bytes32.from_hexstr(auth_sk), root_path=root_path))


@cli.group(short_help="Create config files")
def config() -> None:
    pass


def create_config(
    *,
    config_path: pathlib.Path,
    config_info: api.store.Config | api.rpc.Config | api.service.Config | api.server.Config,
) -> None:
    if not config_path.exists():
        config_path.touch()
    with config_path.open(mode="w", encoding="utf8") as file:
        yaml.dump(config_info, file)


root_path_option = click.option(
    "--root-path",
    type=click.Path(exists=True),
    required=True,
    help="The directory to create the config in",
    default="~/.chia-pool",
    show_default=True,
)


@config.command()
@root_path_option
@click.option("--store-path", type=click.Path(exists=False), required=True, help="The path to the store database file")
def store(*, root_path: str, store_path: str) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(api.store.CONFIG_FILE_NAME),
        config_info=api.store.Config(store_path=store_path),
    )


def chia_service_options(func: Callable[..., None]) -> Callable[..., None]:
    return click.option(
        "--hostname",
        type=str,
        required=True,
        help="The hostname where the full node is running",
        show_default=True,
        default="127.0.0.1",
    )(
        click.option("--rpc-port", type=int, required=True, help="The port to use for the full node RPC server")(
            click.option(
                "--chia-root", type=click.Path(exists=True), required=True, help="The path to the chia root directory"
            )(
                click.option(
                    "--rpc-timeout",
                    type=int,
                    required=True,
                    help="The RPC timeout in seconds",
                    show_default=True,
                    default=120,
                )(
                    click.option(
                        "--daemon-ssl-crt",
                        type=click.Path(),
                        required=True,
                        help="The path to the daemon SSL certificate",
                    )(
                        click.option(
                            "--daemon-ssl-key", type=click.Path(), required=True, help="The path to the daemon SSL key"
                        )(
                            click.option(
                                "--private-ssl-crt",
                                type=click.Path(),
                                required=True,
                                help="The path to the Full Node private SSL CA certificate",
                            )(
                                click.option(
                                    "--private-ssl-key",
                                    type=click.Path(),
                                    required=True,
                                    help="The path to the Full Node private SSL CA key",
                                )(func)
                            )
                        )
                    )
                )
            )
        )
    )


@config.command()
@root_path_option
@chia_service_options
def node(
    *,
    root_path: str,
    hostname: str,
    rpc_port: int,
    chia_root: str,
    rpc_timeout: int,
    daemon_ssl_crt: str,
    daemon_ssl_key: str,
    private_ssl_crt: str,
    private_ssl_key: str,
) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(api.node_rpc.CONFIG_FILE_NAME),
        config_info=api.rpc.Config(
            self_hostname=hostname,
            rpc_port=rpc_port,
            root_path=chia_root,
            net_config=api.rpc.NetConfig(
                rpc_timeout=rpc_timeout,
                daemon_ssl=api.rpc.DaemonSSLConfig(
                    private_crt=daemon_ssl_crt,
                    private_key=daemon_ssl_key,
                ),
                private_ssl_ca=api.rpc.PrivateSSLConfig(
                    crt=private_ssl_crt,
                    key=private_ssl_key,
                ),
            ),
        ),
    )


@config.command()
@root_path_option
@chia_service_options
def wallet(
    *,
    root_path: str,
    hostname: str,
    rpc_port: int,
    chia_root: str,
    rpc_timeout: int,
    daemon_ssl_crt: str,
    daemon_ssl_key: str,
    private_ssl_crt: str,
    private_ssl_key: str,
) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(api.wallet_rpc.CONFIG_FILE_NAME),
        config_info=api.rpc.Config(
            self_hostname=hostname,
            rpc_port=rpc_port,
            root_path=chia_root,
            net_config=api.rpc.NetConfig(
                rpc_timeout=rpc_timeout,
                daemon_ssl=api.rpc.DaemonSSLConfig(
                    private_crt=daemon_ssl_crt,
                    private_key=daemon_ssl_key,
                ),
                private_ssl_ca=api.rpc.PrivateSSLConfig(
                    crt=private_ssl_crt,
                    key=private_ssl_key,
                ),
            ),
        ),
    )


@config.command()
@root_path_option
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
    "--confirmation-security-threshold",
    type=int,
    required=True,
    help="The number of confirmations required for a block to be considered valid",
    show_default=True,
    default=2,
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
    help="The number of partials per --time-target interval a farmer should be submitting",
    show_default=True,
    default=0,
)
@click.option(
    "--time-target",
    type=int,
    required=True,
    help="The interval over which a farmer should submit --number-of-partials-target partials",
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
def service(
    *,
    root_path: str,
    relative_lock_height: int,
    pool_wallet_address: str,
    pool_memoization: str,
    min_difficulty: int,
    default_difficulty: int,
    partial_time_limit: int,
    partial_confirmation_delay: int,
    scan_start_height: int,
    confirmation_security_threshold: int,
    max_additions_per_transaction: int,
    number_of_partials_target: int,
    time_target: int,
    fee: int,
    genesis_challenge: str,
) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(api.service.CONFIG_FILE_NAME),
        config_info=api.service.Config(
            pool_identity=api.service.PoolIdentityConfig(
                relative_lock_height=relative_lock_height,
                pool_claim_hash=pool_wallet_address,
                pool_memoization=pool_memoization,
            ),
            min_difficulty=min_difficulty,
            default_difficulty=default_difficulty,
            partial_time_limit=partial_time_limit,
            partial_confirmation_delay=partial_confirmation_delay,
            scan_start_height=scan_start_height,
            confirmation_security_threshold=confirmation_security_threshold,
            max_additions_per_transaction=max_additions_per_transaction,
            number_of_partials_target=number_of_partials_target,
            time_target=time_target,
            fee_basis_points=fee,
            genesis_challenge=genesis_challenge,
        ),
    )


@config.command()
@root_path_option
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
    default=False,
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
    "--web-host",
    type=str,
    required=True,
    help="The host for the web server",
    show_default=True,
    default="127.0.0.1",
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
def server(
    *,
    root_path: str,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"],
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
    web_host: str,
    web_port: int,
    ssl_cert_path: str,
    ssl_key_path: str,
    service_loop_intervals: int,
    authentication_token_timeout: int,
) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(api.server.CONFIG_FILE_NAME),
        config_info=api.server.Config(
            logging=api.server.LoggingConfig(
                log_level=log_level,
                log_stdout=log_stdout,
                log_syslog=log_syslog,
                log_syslog_host=log_syslog_host,
                log_syslog_port=log_syslog_port,
                log_filename=log_filename,
                log_maxfilesrotation=log_maxfilesrotation,
                log_max_bytes_rotation=log_max_bytes_rotation,
                log_use_gzip=log_use_gzip,
            ),
            pool_info=api.server.PoolInfoConfig(
                name=pool_name,
                logo_url=pool_logo_url,
                description=pool_description,
                welcome_message=pool_welcome_message,
            ),
            web_config=api.server.WebConfig(
                host=web_host,
                port=web_port,
                ssl_cert_path=ssl_cert_path,
                ssl_key_path=ssl_key_path,
            ),
            service_loop_intervals=service_loop_intervals,
            authentication_token_timeout=authentication_token_timeout,
        ),
    )


if __name__ == "__main__":
    cli()
