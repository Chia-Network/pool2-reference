from __future__ import annotations

import datetime
import pathlib
from collections.abc import Iterator

import pytest
from chia._tests.conftest import (  # noqa: PLC2701
    blockchain_constants,  # noqa: F401
    consensus_mode,  # noqa: F401
    trusted_full_node,  # noqa: F401
    tx_config,  # noqa: F401
)
from chia._tests.environments.wallet import WalletTestFramework
from chia._tests.wallet.conftest import wallet_environments  # noqa: PLC2701, F401
from click.testing import CliRunner
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from tests.node.conftest import *  # noqa: F403
from tests.rpc.conftest import *  # noqa: F403
from tests.server.conftest import *  # noqa: F403
from tests.service.conftest import *  # noqa: F403
from tests.store.conftest import *  # noqa: F403
from tests.wallet.conftest import *  # noqa: F403


@pytest.fixture(autouse=True)
def _isolated_filesystem() -> Iterator[None]:
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield None


@pytest.fixture
async def wallet_envs(  # noqa: RUF029
    wallet_environments: WalletTestFramework,  # noqa: F811
) -> WalletTestFramework:
    return wallet_environments


@pytest.fixture
def root_path() -> pathlib.Path:
    return pathlib.Path.cwd()


@pytest.fixture
def generate_ssl_cert() -> tuple[pathlib.Path, pathlib.Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = pathlib.Path.cwd() / "test.crt"
    key_path = pathlib.Path.cwd() / "test.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
        )
    )
    return cert_path, key_path
