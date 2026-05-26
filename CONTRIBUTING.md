# Contributing to Pool2 Reference

Thank you for helping improve the Chia pool reference implementation. This guide covers how to set up a development environment, follow project conventions, and submit changes that pass CI.

For an overview of what the project does, see [README.md](README.md).

---

## Table of contents

- [Before you start](#before-you-start)
- [Development setup](#development-setup)
- [Project conventions](#project-conventions)
- [Running tests](#running-tests)
- [Pre-commit and formatting](#pre-commit-and-formatting)
- [Dependency changes](#dependency-changes)
- [Pull requests](#pull-requests)
- [Where to contribute](#where-to-contribute)

---

## Before you start

- **Search existing issues and PRs** on [GitHub](https://github.com/Chia-Network/chia-pool) to avoid duplicate work.
- **Open an issue** for large or ambiguous changes (new endpoints, payout schemes, storage backends) so maintainers can align on approach before you invest heavily.
- **Keep scope focused.** Small, reviewable PRs are easier to merge than sweeping refactors mixed with feature work.
- **Protocol changes** that affect farmers or on-chain behavior need coordination with [chia-blockchain](https://github.com/Chia-Network/chia-blockchain) and the pooling specification; discuss those in an issue first.

Be respectful and constructive in issues and reviews. For general Chia community support, see [Discord](https://discord.gg/chia).

---

## Development setup

### Prerequisites

- Git
- Python **3.10–3.13**
- On Windows: [Python Launcher](https://docs.python.org/3/using/windows.html#installation-steps) (`py`), Visual C++ Redistributable 2019+, and Git

### Install

**Linux / macOS**

```bash
git clone https://github.com/Chia-Network/chia-pool.git
cd chia-pool
./install.sh -d
source ./activate
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/Chia-Network/chia-pool.git
cd chia-pool
.\Install.ps1 -d
.\venv\Scripts\Activate.ps1
```

The `-d` flag installs development dependencies (pytest, ruff, mypy, pre-commit, etc.).

### Pre-commit

Install hooks once per clone:

```bash
pre-commit install
```

Hooks run automatically on `git commit`. You can also run everything manually:

```bash
pre-commit run --all-files
```

On Windows or when the venv is not active, use the project wrapper:

```bash
python activated.py -- pre-commit run --all-files
```

---

## Project conventions

### Python style

| Rule               | Detail                                                                                                                                                   |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Line length        | **120** characters (`ruff.toml`)                                                                                                                         |
| Future annotations | Every `.py` file must start with `from __future__ import annotations`                                                                                    |
| Imports            | **No relative imports** — use top-level names (`api`, `service`, `farmer_rpc`, …) as in existing modules under `chia-pool/`                              |
| Formatting         | **Ruff format** (enforced in pre-commit)                                                                                                                 |
| Linting            | **Ruff** with a broad rule set; some categories are intentionally ignored (docstrings, many `TRY`/`BLE` rules) — match surrounding code when fixing lint |
| Types              | **mypy** in strict mode (`mypy.ini`) — new code should type-check cleanly                                                                                |

### Package layout

Application code lives under **`chia-pool/`**. When running or testing locally, commands are usually issued from that directory or with `chia-pool` on the module path (see `pytest.ini` `testpaths`).

- **`api/`** — TypedDict configs and protocols (`Store`, `NodeRPC`, `Wallet`, …)
- **`farmer_rpc/`** — HTTP handler implementations (e.g. `v2.py`)
- **`server/`** — aiohttp wiring and background task scheduling
- **`service/`** — Core pool logic (partials, rewards, payouts)
- **`store/`** — Persistence (default: SQLite)
- **`tests/`** — Pytest suites; reuses Chia’s `chia._tests` fixtures via root `conftest.py`

### `__init__.py` files

Pre-commit runs `build-init-files.py` to ensure every package directory under `chia-pool/` has an `__init__.py`. Do not remove these; add new package folders and let the hook create the file, or run:

```bash
python activated.py python build-init-files.py -v --root . --tree chia-pool
```

### Async code

The server is **asyncio**-based. Prefer `async`/`await` for I/O; avoid blocking calls in async paths (Ruff flags some of these under `ASYNC*` rules).

---

## Running tests

From the repository root with the venv active:

```bash
pytest chia-pool/tests
```

Parallel runs (as in CI):

```bash
pytest chia-pool/tests -n 2
```

### Writing tests

- Place tests under `chia-pool/tests/` mirroring the module under test (`tests/rpc/`, `tests/service/`, …).
- Use existing **fixtures** in `tests/*/conftest.py` and `chia-pool/tests/conftest.py` (`root_path`, `reference_service`, `server_config`, wallet environments, etc.).
- Prefer **`pytest.mark.anyio`** for async tests where the suite already does.
- Do not add tests that only assert trivial constants unless they guard real regression behavior.

---

## Pre-commit and formatting

Hooks defined in [`.pre-commit-config.yaml`](.pre-commit-config.yaml):

| Hook            | Purpose                                                                               |
| --------------- | ------------------------------------------------------------------------------------- |
| `init_py_files` | Regenerate missing `__init__.py` under `chia-pool/`                                   |
| `ruff format`   | Format Python                                                                         |
| `ruff`          | Lint and auto-fix where possible                                                      |
| `poetry`        | `poetry check --strict` and refresh lock when `pyproject.toml` / `poetry.lock` change |
| `prettier`      | Format YAML, TOML, Markdown, JSON                                                     |
| `shfmt`         | Format shell scripts                                                                  |
| Standard hooks  | YAML syntax, LF line endings, EOF fixer, trailing whitespace, AST check               |
| `mypy`          | Type-check the tree                                                                   |

Fix failures before pushing; CI runs the same hooks on Ubuntu, macOS, and Windows across Python 3.10–3.13.

---

## Dependency changes

Dependencies are managed with **Poetry** (`pyproject.toml`, `poetry.lock`).

1. Edit `pyproject.toml` (version pins, git rev for `chia-blockchain`, optional `dev` extras).
2. Regenerate the lockfile:

   ```bash
   python activated.py --poetry poetry lock
   ```

3. Pre-commit’s `poetry` hook runs `poetry-check.py` (`poetry check --strict` and `poetry lock`) on lockfile changes — commit **both** `pyproject.toml` and `poetry.lock`.
4. Re-run tests after bumping **chia-blockchain**; pooling APIs and test fixtures often shift between revisions.

---

## Pull requests

### Branch and commits

1. Fork the repo and create a branch from `main`.
2. Make focused commits with clear messages (imperative summary, optional body for “why”). Examples from history: `Fix test from upgrade`, `Use query for GET requests`, `Repin chia-blockchain`.
3. **Sign your commits** with GPG. CI runs [check-commit-signing](.github/workflows/check-commit-signing.yml) on PRs; unsigned commits will fail.
4. Keep your branch up to date with `main` to avoid the `merge_conflict` label (see [conflict-check](.github/workflows/conflict-check.yml)).

### PR checklist

Before requesting review:

- [ ] `pre-commit run --all-files` passes
- [ ] `pytest chia-pool/tests` passes
- [ ] New behavior has tests where practical
- [ ] README or config docs updated if user-facing behavior changed
- [ ] `pyproject.toml` / `poetry.lock` updated together if dependencies changed

### Review expectations

Maintainers may ask for:

- Smaller follow-up PRs instead of one large diff
- Tests covering edge cases (reorgs, late partials, difficulty bounds)
- Notes on operational impact for pool operators

### License

By contributing, you agree that your contributions are licensed under the same terms as the project: **Apache License 2.0** ([LICENSE](LICENSE)).

---

## Where to contribute

| Area                 | Good first issues / needs                                         |
| -------------------- | ----------------------------------------------------------------- |
| `farmer_rpc/v2.py`   | Endpoint behavior, validation, clearer errors                     |
| `service/service.py` | Reward collection, payouts, singleton following (`TODO`s in file) |
| `store/sqlite.py`    | Schema, pagination, performance                                   |
| `tests/`             | Coverage for RPC and service paths                                |
| Docs                 | README, examples, operator runbooks                               |
| Tooling              | CI, install scripts, pre-commit                                   |

Avoid drive-by changes to ignored Ruff categories project-wide unless discussed first — large lint-only PRs are hard to review and often conflict with active work.

---

## Questions

- **Pooling concepts:** [Chia Pooling FAQ](https://github.com/Chia-Network/chia-blockchain/wiki/Pooling-FAQ)
- **V1 reference pool:** [pool-reference](https://github.com/Chia-Network/pool-reference)
- **Bugs and features:** [GitHub Issues](https://github.com/Chia-Network/chia-pool/issues)

Thank you for contributing.
