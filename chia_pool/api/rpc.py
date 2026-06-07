from __future__ import annotations

from typing_extensions import TypedDict


class DaemonSSLConfig(TypedDict):
    private_crt: str
    private_key: str


class PrivateSSLConfig(TypedDict):
    crt: str
    key: str


class NetConfig(TypedDict):
    rpc_timeout: int
    daemon_ssl: DaemonSSLConfig
    private_ssl_ca: PrivateSSLConfig


class Config(TypedDict):
    self_hostname: str
    rpc_port: int
    root_path: str
    net_config: NetConfig
