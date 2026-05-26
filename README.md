# Pool2 Reference

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Reference implementation of a Chia **pool server** for the **post–3.0 hard-fork** pooling model. The code lives in the `chia-pool` Python package and is meant as a starting point for pool operators and integrators—not as a turnkey production service.

| Topic                                                           | Where to look                                                       |
| --------------------------------------------------------------- | ------------------------------------------------------------------- |
| Farmer-facing HTTP API                                          | `chia-pool/farmer_rpc/v2.py` (routes registered as `/v2/...`)       |
| Background work (confirm partials, absorb rewards, pay farmers) | `chia-pool/service/service.py`, `chia-pool/server/pooling_tasks.py` |
| CLI entrypoint                                                  | `chia-pool/reference.py`                                            |
| Persistence                                                     | `chia-pool/store/sqlite.py` (default SQLite store)                  |

---

## Table of contents

- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the pool server](#running-the-pool-server)
- [HTTP API (v2)](#http-api-v2)
- [Background tasks](#background-tasks)
- [Customization](#customization)
- [License](#license)

---

## How it works

1. A farmer joins the pool with a **Plot NFT** configured for this pool's identity (`pool_claim_hash`, `relative_lock_height`, `pool_memoization`).
2. The farmer calls **`POST /v2/farmer`** to register their farmer with the pool.
3. The farmer calls **`GET /v2/auth`** with a signature from the key that controls exiting the pool, and receives a **JWT** (`authentication_token_v2`).
4. The farmer submits **partials** to **`POST /v2/partial`** with that token. Each partial is an aggregate-signed proof tied to the farmer's `RewardPuzzle` hash.
5. After `partial_confirmation_delay`, the pool confirms partials against the full node (signage point or end-of-subslot still valid), then credits difficulty-weighted points.
6. **`collect_pool_rewards`** builds spend bundles to forward pooled block rewards to the operator wallet.
7. **`submit_payments`** splits confirmed rewards among farmers by points (minus `fee_basis_points`) and sends wallet transactions to each farmer's payout instructions.

Rewards and membership are enforced on-chain via Plot NFT puzzles; the server coordinates validation, accounting, and payouts.

---

## Architecture

| Layer       | Module                                         | Responsibility                                                 |
| ----------- | ---------------------------------------------- | -------------------------------------------------------------- |
| HTTP        | `server/farmer_rpc.py`                         | Route registration, SSL, JSON/streamable request handling      |
| Handlers    | `farmer_rpc/v2.py`                             | Auth, farmer CRUD, partial validation, difficulty adjustment   |
| Core        | `service/service.py`                           | Confirm partials, track Plot NFTs, absorb rewards, pay farmers |
| Loops       | `server/pooling_tasks.py`                      | Periodic scheduling of service methods                         |
| RPC clients | `node/rpc_wrapper.py`, `wallet/rpc_wrapper.py` | Typed wrappers around Chia node/wallet RPC                     |
| Store       | `store/sqlite.py`                              | Farmers, partials, singletons, payouts, reward claims          |

Configs are split into several YAML files under a single **`--root-path`** (default `~/.chia-pool`), validated with Marshmallow schemas.

---

## Repository layout

```
pool2-reference/
├── chia-pool/
│   ├── reference.py          # Click CLI: config *, start
│   ├── farmer_rpc/
│   │   ├── v2.py             # V2 endpoint handlers + METADATA
│   │   └── authentication.py # JWT create/verify
│   ├── server/
│   │   ├── farmer_rpc.py     # aiohttp app
│   │   └── pooling_tasks.py  # Background loops
│   ├── service/service.py    # Pool business logic
│   ├── store/sqlite.py       # Default database
│   ├── api/                  # TypedDict configs + protocols
│   └── tests/
├── install.sh / Install.ps1  # Poetry + venv setup
├── activated.py              # Run commands inside the venv
├── pyproject.toml            # Package: chia-pool
└── conftest.py               # Pytest plugins (chia test fixtures)
```

---

## Requirements

- **Python** 3.10–3.13 (see `install.sh` / `Install.ps1`)
- **Poetry** (installed under `.penv/` by the install scripts)
- A synced Chia **full node** and **wallet** with RPC enabled (paths and certs configured in pool config)
- **OpenSSL** and **SQLite** versions checked by the installer
- For production HTTPS: certificate and key paths in `pool_server_config.yaml`

`chia-blockchain` is pulled as a **git dependency** (pinned revision in `pyproject.toml`). Use a node/wallet build compatible with that revision.

---

## Installation

### Linux / macOS

```bash
git clone https://github.com/Chia-Network/chia-pool.git pool2-reference
cd pool2-reference
./install.sh -d    # -d installs dev extras (pytest, ruff, mypy, pre-commit)
source ./activate  # or: source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
git clone https://github.com/Chia-Network/chia-pool.git pool2-reference
cd pool2-reference
.\Install.ps1 -d
.\venv\Scripts\Activate.ps1
```

### Run commands via `activated.py`

```bash
python activated.py -- pytest chia-pool/tests -n 2
python activated.py --penv poetry sync
```

---

## Configuration

Generate configs with the CLI (from the `chia-pool` directory, with the venv active):

```bash
cd chia-pool
python reference.py config --help
```

Each subcommand writes one file under `--root-path` (default `~/.chia-pool`):

| File                              | CLI command      | Purpose                                                             |
| --------------------------------- | ---------------- | ------------------------------------------------------------------- |
| `pool_store_config.yaml`          | `config store`   | SQLite database path                                                |
| `pool_node_client_config.yaml`    | `config node`    | Full node RPC host, port, SSL, `chia_root`                          |
| `pool_wallet_client_config.yaml`  | `config wallet`  | Wallet RPC (same shape as node client)                              |
| `pool_service_client_config.yaml` | `config service` | Pool identity, difficulty, fees, scan height, genesis challenge     |
| `pool_server_config.yaml`         | `config server`  | Logging, pool branding, web bind host/port, SSL, auth token timeout |

### Pool identity (`config service`)

These values define how Plot NFTs bind to your pool on-chain:

| Field                  | Meaning                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| `pool_claim_hash`      | Bech32m address / puzzle hash where absorbed rewards are sent        |
| `relative_lock_height` | Blocks before a farmer can leave the pool                            |
| `pool_memoization`     | CLVM hex passed to `CREATE_COIN` when paying the pool (default `80`) |

Node and wallet config commands accept standard Chia RPC options (`--hostname`, `--rpc-port`, `--chia-root`, daemon SSL paths, etc.). Point `--chia-root` at your real `CHIA_ROOT` (e.g. `~/.chia/mainnet`).

---

## Running the pool server

1. Install the package and create all five config files (see above).
2. Ensure Chia node and wallet are running and RPC ports match your configs.
3. Choose a secret **32-byte key** for signing JWTs (`--auth-sk`). Treat it like a server secret; farmers receive tokens derived from it.
4. Start the server:

```bash
cd chia-pool
python reference.py start \
  --auth-sk "<64-char hex secret key>" \
  --root-path ~/.chia-pool
```

This runs until interrupted. It concurrently:

- Serves **HTTPS** (or HTTP if SSL paths omitted) on `web_config.host` / `web_config.port`
- Runs background loops at `service_loop_intervals` seconds

Farmers must use the pool URL that matches your deployment and the Plot NFT pool configuration on-chain.

---

## HTTP API (v2)

Routes are registered under `/v2/<endpoint>` (see `farmer_rpc/v2.py` `METADATA`). Request/response types come from `chia.protocols.pool_protocol`.

| Method | Path            | Auth      | Description                                                          |
| ------ | --------------- | --------- | -------------------------------------------------------------------- |
| `GET`  | `/v2/pool_info` | No        | Pool name, logo, fees, min difficulty, lock height, protocol version |
| `GET`  | `/v2/auth`      | Signature | Issue JWT for a known farmer                                         |
| `GET`  | `/v2/farmer`    | JWT       | Farmer status, difficulty, current points                            |
| `POST` | `/v2/farmer`    | Signature | Register farmer                                                      |
| `PUT`  | `/v2/farmer`    | JWT       | Update payout instructions / suggested difficulty                    |
| `POST` | `/v2/partial`   | JWT       | Submit partial; returns `new_difficulty`                             |

**Authentication**

- Registration and `GET /v2/auth` use BLS signatures over messages that include `launcher_id` and `pool_claim_hash`, verified with the farmer’s authentication public key (child key derivation path `12381` for safety from tampering).
- Other endpoints expect `authentication_token_v2` (JWT, HS256) from `farmer_rpc/authentication.py`, with expiry driven by `authentication_token_timeout` in server config.

**Partial validation highlights**

- Aggregate signature over plot public key and authentication public key
- `pool_contract_puzzle_hash` must equal `RewardPuzzle(singleton_id=launcher_id).puzzle_hash()`
- Signage point or EOS must exist and not be reverted
- Proof quality checked with `POOL_SUB_SLOT_ITERS // 64` bound (same constant family as V1 pooling)

Errors return JSON `ErrorResponse` with `error_code` / `error_message` (`PoolErrorCode`).

> **Note:** If you register a `v1` handler set in `FarmerRPCServer.create_rpc`, those routes are also mounted at `/` for backward compatibility. The reference server only wires **`v2`** today.

---

## Background tasks

`PoolServer.create_pooling_tasks` schedules these `Service` methods on `service_loop_intervals`:

| Task       | Method                 | Purpose                                                    |
| ---------- | ---------------------- | ---------------------------------------------------------- |
| Partials   | `confirm_partials`     | Confirm or delete queued partials after delay              |
| Rewards    | `collect_pool_rewards` | Forward pool reward coins via Plot NFT spend bundles       |
| Payouts    | `submit_payments`      | Distribute absorbed rewards to farmers by points           |
| Singletons | `check_for_singletons` | Track Plot NFT coins, detect exits, prune inactive farmers |

Reward collection and singleton tracking include `TODO` markers for pagination, height persistence, and reorg handling—expect to harden these for production.

---

## Customization

| Area              | Extension point                                                                                 |
| ----------------- | ----------------------------------------------------------------------------------------------- |
| Store             | Implement `api.store.Store` (see `store/sqlite.py`)                                             |
| Service           | Subclass or replace `service.service.Service` methods                                           |
| HTTP              | Add `APIEndpointMetadata` entries and register new version keys in `reference.py` `start_async` |
| Difficulty        | Logic in `farmer_rpc/v2.py` `adjust_difficulty`                                                 |
| Payout addressing | `service.service.convert_payout_instructions` (currently hex → `bytes32`)                       |
| Auth              | Replace JWT helpers in `farmer_rpc/authentication.py`                                           |

On-chain Plot NFT rules and `pool_protocol` streamable types are defined in **chia-blockchain**; incompatible changes require a coordinated network/protocol update.

---

## License

Apache License 2.0. See [LICENSE](LICENSE).
