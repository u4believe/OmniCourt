# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

```bash
# Linting
genvm-lint check contracts/omnicourt.py        # Lint the contract

# Testing — use `python3 -m pytest`, not bare `pytest` (see note below)
python3 -m pytest tests/direct/ -v             # Direct mode tests (fast, no Studio)
gltest tests/integration/ -v -s                # Integration tests (requires Studio)

# Deployment — the CLI has no Studio Next preset, so use the script
DEPLOY_KEY_FILE=/path/to/key node deploy/deployStudioNext.mjs

# Driving the deployed registry
node scripts/omnicourt.mjs list                # Reads need no wallet
node scripts/omnicourt.mjs verdict 0

# Frontend
cd frontend && npm run dev                     # Start frontend dev server
```

## Project-specific gotchas

These cost real time to rediscover:

- **Run pytest as `python3 -m pytest`.** The repo root has an `__init__.py`,
  which makes pytest's rootdir walk skip the project directory, so
  `from tests.direct.conftest import ...` fails under bare `pytest`.
- **The contract's `Depends` runner hash must exist in the installed GenVM
  release.** `contracts/omnicourt.py` pins
  `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`. A hash
  that is not in the release tree fails every direct test with
  `FileNotFoundError: runner ... not under ~/.cache/gltest-direct/...`.
- **Two SDK generations ship side by side.** The pinned runner maps to the
  `import genlayer as gl` / `gl.contract.Contract` / `gl.storage.TreeMap` API.
  The other runner in `legacy-runners/` maps to the newer
  `from genlayer import *` / `gl.Contract` API. Mixing them produces confusing
  `name 'gl' is not defined` or `No module named 'genlayer.storage'` errors.
- **`DynArray()` cannot be constructed by user code** — it raises `TypeError`.
  Create the containing record with `TreeMap.get_or_insert_default(key)` and
  assign fields, then `append()` into the already-allocated `DynArray`.
- **The GenLayer CLI (0.39.2) has no Studio Next preset.** It only knows Studio
  (chain 61999), so `genlayer deploy --rpc <studio-next>` signs for the wrong
  chain and fails with `InvalidChainId`. Use `deploy/deployStudioNext.mjs`.
- **Consensus v0.6 deploys and writes need a non-zero fee value**, or they
  revert with `FeeValueMustBeNonZero`. Quote it with
  `client.estimateTransactionFees(...)` rather than hardcoding.
- **Studio Next's faucet needs a hex-encoded amount.**
  `sim_fundAccount` with a decimal integer returns a tx hash but credits
  nothing; `["0x<addr>", "0x56BC75E2D63100000"]` works.
- **Studio Next drops sockets intermittently.** Retry RPC calls rather than
  treating the first `UND_ERR_SOCKET` / SSL error as a real failure.

## Architecture

```
contracts/omnicourt.py   # The OmniCourt dispute registry
tests/
  direct/                # Fast in-memory tests with web/LLM mocks
  integration/           # Full tests against GenLayer Studio
frontend/                # Next.js app (TypeScript, TanStack Query, Radix UI)
deploy/                  # Studio Next deployment script
scripts/omnicourt.mjs    # CLI for driving the deployed registry
```

**Frontend stack**: Next.js 15, React 19, TypeScript, Tailwind CSS, TanStack Query, Wagmi/Viem, MetaMask wallet integration.

## Development Workflow

1. Write/modify contract in `contracts/`
2. Lint: `genvm-lint check contracts/omnicourt.py`
3. Test direct: `python3 -m pytest tests/direct/ -v`
4. Deploy: `DEPLOY_KEY_FILE=/path/to/key node deploy/deployStudioNext.mjs`
5. Test integration: `gltest tests/integration/ -v -s`
6. Run frontend: `cd frontend && npm run dev`

## Contract Development

Contracts are Python files in `/contracts/` using the GenLayer SDK. Match the
API generation of the pinned runner (see gotchas above) — this project uses the
`import genlayer as gl` style:

```python
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl


class MyContract(gl.contract.Contract):
    data: gl.storage.TreeMap[gl.Address, str]

    def __init__(self):
        pass

    @gl.public.view
    def get_data(self, addr: gl.Address) -> str:
        return self.data.get(addr, "")

    @gl.public.write
    def set_data(self, value: str) -> None:
        self.data[gl.message.sender_address] = value
```

**Decorators**:
- `@gl.public.view` — Read-only methods
- `@gl.public.write` — State-modifying methods
- `@gl.public.write.payable` — Methods accepting value

**Storage types**: `gl.storage.TreeMap`, `gl.storage.DynArray`, `gl.storage.Array`,
`gl.u256`, `gl.i256`, and `@allow_storage` (from `genlayer.storage import allow`)
for dataclasses stored inside collections.

## Writing Direct Mode Tests

Direct mode runs contracts in-memory without Studio. Key APIs:

```python
def test_example(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/my_contract.py")

    # Set sender
    direct_vm.sender = direct_alice

    # Mock web requests (regex on URL)
    direct_vm.mock_web(r".*example\.com.*", {"status": 200, "body": "response"})

    # Mock LLM responses (regex on prompt)
    direct_vm.mock_llm(r".*analyze.*", '{"result": "positive"}')

    # Call contract methods directly
    contract.some_write_method("arg1")
    result = contract.some_view_method()

    # Assert expected failures
    with direct_vm.expect_revert("Error message"):
        contract.invalid_method()

    # Reset mocks between different scenarios
    direct_vm.clear_mocks()
```

Available fixtures: `direct_vm`, `direct_deploy`, `direct_alice`, `direct_bob`, `direct_charlie`, `direct_owner`, `direct_accounts`

## Linting

The GenVM linter catches contract issues before deployment:
- Forbidden imports (`os`, `sys`, `subprocess`, etc.)
- Non-deterministic calls outside equivalence principle blocks
- Invalid storage types (must use `TreeMap`/`DynArray`, not `dict`/`list`)
- Missing decorators and return type annotations
- Bare Python exceptions (must use `gl.vm.UserError` or `Exception`)

## Frontend Patterns

- Contract interactions: `frontend/lib/contracts/OmniCourt.ts`
- React hooks: `frontend/lib/hooks/useOmniCourt.ts`
- Wallet context: `frontend/lib/genlayer/WalletProvider.tsx`
- GenLayer client: `frontend/lib/genlayer/client.ts`

## AI Agent Skills

Install the GenLayer development skills for enhanced agent-assisted workflows:

```bash
# In Claude Code:
/plugin marketplace add genlayerlabs/skills
/plugin install genlayer-dev@genlayerlabs
```

Skills available: `genvm-lint` (linting), `direct-tests` (direct mode testing), `integration-tests` (integration testing).

---

## GenLayer Technical Reference

> **Can't solve an issue?** Always check the complete SDK API reference:
> **https://sdk.genlayer.com/main/_static/ai/api.txt**
>
> Contains: all classes, methods, parameters, return types, changelogs, breaking changes.

### Documentation URLs

| Resource | URL |
|----------|-----|
| **SDK API (Complete)** | https://sdk.genlayer.com/main/_static/ai/api.txt |
| Full Documentation | https://docs.genlayer.com/full-documentation.txt |
| Main Docs | https://docs.genlayer.com/ |
| GenLayerJS SDK | https://docs.genlayer.com/api-references/genlayer-js |

### What is GenLayer?

GenLayer is an AI-native blockchain where smart contracts can natively access the internet and make decisions using AI (LLMs). Contracts are Python-based and executed in the GenVM.

### Web Access (`gl.nondet.web`)

```python
gl.nondet.web.get(url: str, *, headers: dict = {}) -> Response
gl.nondet.web.post(url: str, *, body: str | bytes | None = None, headers: dict = {}) -> Response
gl.nondet.web.render(url: str, *, mode: Literal['text', 'html']) -> str
gl.nondet.web.render(url: str, *, mode: Literal['screenshot']) -> Image
```

### LLM Access (`gl.nondet`)

```python
gl.nondet.exec_prompt(prompt: str, *, images: Sequence[bytes | Image] | None = None) -> str
gl.nondet.exec_prompt(prompt: str, *, response_format: Literal['json'], image: bytes | Image | None = None) -> dict
```

### Equivalence Principle

Validation for non-deterministic outputs. Two approaches:

**Custom leader/validator functions** (recommended for most cases):
```python
result = gl.vm.run_nondet(leader_fn, validator_fn)
result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)  # no type matching
```

**Convenience functions** (for common patterns):
| Type | Use Case | Function |
|------|----------|----------|
| Strict | Exact outputs | `gl.eq_principle.strict_eq()` |
| Comparative | Similar outputs | `gl.eq_principle.prompt_comparative()` |
| Non-Comparative | Subjective assessments | `gl.eq_principle.prompt_non_comparative()` |

### Key Documentation Links

- [Introduction to Intelligent Contracts](https://docs.genlayer.com/developers/intelligent-contracts/introduction)
- [Storage](https://docs.genlayer.com/developers/intelligent-contracts/storage)
- [Deploying Contracts](https://docs.genlayer.com/developers/intelligent-contracts/deploying)
- [Crafting Prompts](https://docs.genlayer.com/developers/intelligent-contracts/crafting-prompts)
- [Contract Examples](https://docs.genlayer.com/developers/intelligent-contracts/examples/storage)
- [Testing Contracts](https://docs.genlayer.com/developers/decentralized-applications/testing)
