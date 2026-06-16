from __future__ import annotations

import asyncio
import pathlib
from collections.abc import Callable
from typing import Literal

import click
import yaml
from chia_rs.sized_bytes import bytes32

import chia_pool.api
from chia_pool.farmer_rpc import v2
from chia_pool.node.rpc_wrapper import NodeRPC
from chia_pool.server.farmer_rpc import FarmerRPCServer
from chia_pool.server.pooling_tasks import PoolServer
from chia_pool.service.service import Service
from chia_pool.store.sqlite import Store
from chia_pool.wallet.rpc_wrapper import WalletRPC


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
                service=service,
                token_sk=auth_sk,
                root_path=root_path,
            ),
        ):
            await asyncio.Event().wait()


root_path_option = click.option(
    "--root-path",
    type=pathlib.Path,
    required=True,
    default="~/.chia-pool",
    show_default=True,
    help="The root path for the config files",
)


@cli.command()
@click.option("--auth-sk", type=str, required=True, help="The 32-byte secret key to use for farmer authentication")
@root_path_option
def start(auth_sk: str, root_path: pathlib.Path) -> None:
    """Start the application."""
    asyncio.run(start_async(auth_sk=bytes32.from_hexstr(auth_sk), root_path=root_path))


@cli.group(short_help="Create config files")
def config() -> None:
    pass


def create_config(
    *,
    config_path: pathlib.Path,
    config_info: chia_pool.api.store.Config
    | chia_pool.api.rpc.Config
    | chia_pool.api.service.Config
    | chia_pool.api.server.Config
    | chia_pool.api.wallet.Config,
) -> None:
    config_path = config_path.expanduser()
    if not config_path.exists():
        config_path.touch()
    with config_path.open(mode="w", encoding="utf8") as file:
        yaml.dump(config_info, file)


@config.command()
@root_path_option
@click.option("--store-path", type=click.Path(exists=False), required=True, help="The path to the store database file")
def store(*, root_path: str, store_path: str) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(chia_pool.api.store.CONFIG_FILE_NAME),
        config_info=chia_pool.api.store.Config(store_path=store_path),
    )


def chia_service_options(func: Callable[..., None]) -> Callable[..., None]:
    return click.option(
        "--hostname",
        type=str,
        required=True,
        help="The hostname where the service is running",
        show_default=True,
        default="localhost",
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
        config_path=pathlib.Path(root_path).joinpath(chia_pool.api.node_rpc.CONFIG_FILE_NAME),
        config_info=chia_pool.api.rpc.Config(
            self_hostname=hostname,
            rpc_port=rpc_port,
            root_path=chia_root,
            net_config=chia_pool.api.rpc.NetConfig(
                rpc_timeout=rpc_timeout,
                daemon_ssl=chia_pool.api.rpc.DaemonSSLConfig(
                    private_crt=daemon_ssl_crt,
                    private_key=daemon_ssl_key,
                ),
                private_ssl_ca=chia_pool.api.rpc.PrivateSSLConfig(
                    crt=private_ssl_crt,
                    key=private_ssl_key,
                ),
            ),
        ),
    )


@config.command()
@root_path_option
@chia_service_options
@click.option("--minimum-coin-amount", type=int, required=False, help="The minimum coin amount to use in transactions")
@click.option("--maximum-coin-amount", type=int, required=False, help="The maximum coin amount to use in transactions")
@click.option(
    "--excluded-coin-id", type=str, required=False, multiple=True, help="A coin ID to exclude from transactions"
)
@click.option(
    "--excluded-coin-amount", type=int, required=False, multiple=True, help="A coin amount to exclude from transactions"
)
@click.option(
    "--reuse-puzhash/--new-puzhashes", is_flag=True, default=True, help="Whether to reuse the puzhash for transactions"
)
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
    reuse_puzhash: bool,
    minimum_coin_amount: int | None = None,
    maximum_coin_amount: int | None = None,
    excluded_coin_id: tuple[str] | None = None,
    excluded_coin_amount: tuple[int] | None = None,
) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(chia_pool.api.wallet_rpc.CONFIG_FILE_NAME),
        config_info=chia_pool.api.rpc.Config(
            self_hostname=hostname,
            rpc_port=rpc_port,
            root_path=chia_root,
            net_config=chia_pool.api.rpc.NetConfig(
                rpc_timeout=rpc_timeout,
                daemon_ssl=chia_pool.api.rpc.DaemonSSLConfig(
                    private_crt=daemon_ssl_crt,
                    private_key=daemon_ssl_key,
                ),
                private_ssl_ca=chia_pool.api.rpc.PrivateSSLConfig(
                    crt=private_ssl_crt,
                    key=private_ssl_key,
                ),
            ),
            tx_config=chia_pool.api.wallet_rpc.TXConfig(
                reuse_puzhash=reuse_puzhash,
                **({"min_coin_amount": minimum_coin_amount} if minimum_coin_amount is not None else {}),
                **({"max_coin_amount": maximum_coin_amount} if maximum_coin_amount is not None else {}),
                **({"excluded_coin_ids": list(excluded_coin_id)} if excluded_coin_id is not None else {}),
                **({"excluded_coin_amounts": list(excluded_coin_amount)} if excluded_coin_amount is not None else {}),
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
    default=1,
)
@click.option(
    "--default-difficulty",
    type=int,
    required=True,
    help="The default difficulty for a farmer if a difficulty is not suggested",
    show_default=True,
    default=1,
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
    "--partial-confirmation-batches",
    type=int,
    required=True,
    help="How many partials to attempt confirming in a single batch while looping",
    show_default=True,
    default=100,
)
@click.option(
    "--singleton-scan-batches",
    type=int,
    required=True,
    help="How many singletons to poll for changes for at a time",
    show_default=True,
    default=10,
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
    default=20,
)
@click.option(
    "--time-target",
    type=int,
    required=True,
    help="The interval over which a farmer should submit --number-of-partials-target partials",
    show_default=True,
    default=3600,
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
    partial_confirmation_batches: int,
    singleton_scan_batches: int,
    scan_start_height: int,
    confirmation_security_threshold: int,
    max_additions_per_transaction: int,
    number_of_partials_target: int,
    time_target: int,
    fee: int,
    genesis_challenge: str,
) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(chia_pool.api.service.CONFIG_FILE_NAME),
        config_info=chia_pool.api.service.Config(
            pool_identity=chia_pool.api.service.PoolIdentityConfig(
                relative_lock_height=relative_lock_height,
                pool_claim_hash=pool_wallet_address,
                pool_memoization=pool_memoization,
            ),
            min_difficulty=min_difficulty,
            default_difficulty=default_difficulty,
            partial_time_limit=partial_time_limit,
            partial_confirmation_delay=partial_confirmation_delay,
            partial_confirmation_batches=partial_confirmation_batches,
            singleton_scan_batches=singleton_scan_batches,
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
    required=False,
    default=None,
    help="The path to the SSL certificate for the web server",
)
@click.option(
    "--ssl-key-path",
    type=click.Path(),
    required=False,
    default=None,
    help="The path to the SSL key for the web server",
)
@click.option(
    "--service-loop-intervals",
    type=int,
    required=True,
    help="The interval in seconds for the service loop",
    show_default=True,
    default=20,
)
@click.option(
    "--authentication-token-timeout",
    type=int,
    required=True,
    help="The timeout in minutes for authentication tokens",
    show_default=True,
    default=10,
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
    ssl_cert_path: str | None,
    ssl_key_path: str | None,
    service_loop_intervals: int,
    authentication_token_timeout: int,
) -> None:
    create_config(
        config_path=pathlib.Path(root_path).joinpath(chia_pool.api.server.CONFIG_FILE_NAME),
        config_info=chia_pool.api.server.Config(
            logging=chia_pool.api.server.LoggingConfig(
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
            pool_info=chia_pool.api.server.PoolInfoConfig(
                name=pool_name,
                logo_url=pool_logo_url,
                description=pool_description,
                welcome_message=pool_welcome_message,
            ),
            web_config=chia_pool.api.server.WebConfig(
                host=web_host,
                port=web_port,
                **(
                    {
                        "ssl_cert_path": ssl_cert_path,
                        "ssl_key_path": ssl_key_path,
                    }
                    if ssl_cert_path is not None and ssl_key_path is not None
                    else {}
                ),
            ),
            service_loop_intervals=service_loop_intervals,
            authentication_token_timeout=authentication_token_timeout,
        ),
    )


if __name__ == "__main__":
    cli()
