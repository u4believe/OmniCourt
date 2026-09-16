# OmniCourt

**A chain-agnostic dispute adjudication registry on GenLayer.**

One permanently deployed Intelligent Contract that any application — on any
blockchain, or none at all — can call into to have a disputed transaction
adjudicated by decentralized AI validators, whether the dispute is between two
AI agents, an agent and a human, or two humans.

- **Network:** GenLayer Studio Next (chain `61997`)
- **Contract:** `0xa4B43D14C18bc6397B771DDb89D63e1c1d02c786`
- **Contract source:** [`contracts/omnicourt.py`](contracts/omnicourt.py)

---

## Why this is genuinely network-agnostic

GenLayer validators never read state from the chain the dispute happened on.
They fetch **public evidence** — a block explorer page, an API response, a
delivery-tracking page, a hosted screenshot — directly from the web via
`gl.nondet.web.render()`, independently, per validator.

That is the actual mechanism: evidence is verified by *re-fetching a public
URL*, not by bridging or reading foreign chain state. The disputed transaction
can be a Solana swap, a PayPal receipt, an Ethereum escrow, or a plain email.
If there is a public evidence trail, OmniCourt can adjudicate it.

## Why decentralized judgment matters here

Every question OmniCourt answers — did the agent's output match its mandate?
did the buyer actually receive the item? did the second agent deliver the result
it billed for? — is a *subjective, evidence-weighing* judgment, not a
deterministic computation.

A single centralized arbiter (a platform's support team, one LLM call from one
server) is both a single point of failure and a single point of bias. Optimistic
Democracy across independent validators is what makes the verdict *contestable
and non-unilateral* — which is the only reason a "court" is credible at all.

`resolve_dispute` uses `gl.eq_principle.prompt_comparative`, so every validator
re-fetches the evidence and reaches its own verdict; consensus is over the
*substance* of the judgment, not over a leader's claim.

## The three dispute types

One registry, three genuinely different relationship types, each with its own
adjudication rubric:

| Type | Who | What the rubric weighs |
|------|-----|------------------------|
| `agent_agent` | Two AI agents under a mandate | Did the respondent's output/action match what was promised? |
| `agent_person` | An AI agent and a human | Did the agent perform the task to a reasonable standard? |
| `person_person` | Two humans in a commercial exchange | Delivery confirmations, tracking, timestamps — a standard chargeback |

## The verdict schema

One schema covers all three, merging the financial vocabulary (who gets the
money) with the behavioural one (what happens to the agent's authority):

```json
{
  "recommended_action": "favor_complainant | favor_respondent | split | warn | constrain | revoke | escalate",
  "allocation_bps": 0,
  "reasoning": "..."
}
```

`allocation_bps` (0-10000) expresses *how much* to favour the complainant when
the dispute has a financial dimension (10000 = fully, 5000 = even split). It is
0 and ignored for purely behavioural actions.

Malformed model output cannot corrupt the registry: an action outside the
allowed set is coerced to `escalate`, and an allocation that is out of range,
negative, or unparseable is clamped into 0-10000.

---

## Verify a full cycle yourself

A reviewer can reproduce one complete dispute against the live deployment
without a wallet for the read steps.

### Reads (no wallet needed)

```shell
npm ci
node scripts/omnicourt.mjs count       # how many disputes the registry holds
node scripts/omnicourt.mjs list        # every dispute with its verdict
node scripts/omnicourt.mjs dispute 0   # full record incl. the evidence trail
node scripts/omnicourt.mjs verdict 0   # what an integrating app reads back
```

Dispute `0` is a real `agent_agent` case already adjudicated on Studio Next.
The complainant cited a public task record showing `completed: false`; the
respondent cited a record for a *different* task. The validators caught the
substitution:

> *"The complainant's evidence directly references task 1 and shows
> `"completed": false`, which contradicts the respondent's claim that task 1 was
> done. The respondent's evidence refers to a different task (id 4), so it does
> not rebut the allegation about task 1."*
> — `favor_complainant`, `allocation_bps: 10000`

Dispute `1` (`person_person`) resolved to `escalate`, because neither side's
evidence actually spoke to delivery — the insufficient-evidence path working as
designed.

### Writes (needs a funded key)

`DEPLOY_KEY_FILE` points at a file holding a hex private key. `genlayer account
unlock` needs an OS keychain, which WSL and bare containers do not have, so
decrypt the keystore to a `0600` file instead:

```shell
python3 scripts/extract_key.py ~/.genlayer/keystores/<name>.json <password> /tmp/omnicourt.key
export DEPLOY_KEY_FILE=/tmp/omnicourt.key

node scripts/omnicourt.mjs open person_person \
  "buyer:alice@example.com" "seller:bob@example.com" \
  "Paid for a laptop on 2026-09-01. It never arrived." "Full refund"

node scripts/omnicourt.mjs evidence <id> complainant "https://<public-evidence-url>"
node scripts/omnicourt.mjs evidence <id> respondent  "https://<public-evidence-url>"
node scripts/omnicourt.mjs resolve <id>
node scripts/omnicourt.mjs verdict <id>
```

### Frontend

```shell
cp frontend/.env.example frontend/.env   # then set the contract address
cd frontend && npm run dev               # http://localhost:3000
```

The UI shows, per dispute: status, both evidence lists, the verdict action, the
allocation split, and the validators' reasoning. Writes go through Transaction
Kit, so you see a fee quote before signing.

---

## How another app integrates

OmniCourt is a **judgment layer, not an enforcement layer**. It returns a
verdict; your application enforces it in its own domain.

```ts
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

const chain = {
  ...studioDevnet,
  id: 61997,
  rpcUrls: { default: { http: ["https://studio-next.genlayer.com/api"] } },
};

const verdict = await createClient({ chain }).readContract({
  address: "0xa4B43D14C18bc6397B771DDb89D63e1c1d02c786",
  functionName: "get_verdict",
  args: [disputeId],
});
// => { status, recommended_action, allocation_bps, reasoning }
```

Then act on it however your domain requires: release escrow, refund, revoke an
agent's permission, flag reputation.

### Contract API

| Method | Kind | Purpose |
|--------|------|---------|
| `open_dispute(type, complainant_ref, respondent_ref, claim, remedy)` | write | Files a dispute, returns its id |
| `submit_evidence(dispute_id, role, evidence_url)` | write | Attaches a public URL to one side |
| `resolve_dispute(dispute_id)` | write | Runs adjudication across validators |
| `get_verdict(dispute_id)` | view | What an integrating app reads back |
| `get_dispute(dispute_id)` | view | Full record incl. the evidence trail |
| `list_disputes()` | view | Every dispute in the registry |
| `dispute_count()` | view | Number of disputes filed |

---

## Development

```shell
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

genvm-lint check contracts/omnicourt.py     # static analysis
python3 -m pytest tests/direct/ -v          # 69 fast in-memory tests
gltest tests/integration/ -v -s             # full consensus tests (needs Studio)
```

> **Note:** run pytest as `python3 -m pytest`, not bare `pytest`. This repo has an
> `__init__.py` at its root, which makes pytest's rootdir walk skip the project
> directory, so `from tests.direct.conftest import ...` fails under bare `pytest`.

> If `python3 -m venv` fails with a missing `ensurepip`, install
> `python3.12-venv`, or use [uv](https://github.com/astral-sh/uv):
> `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt`.

### Test coverage

| Suite | What it covers |
|-------|----------------|
| `tests/direct/test_omnicourt_intake.py` | Dispute creation, validation, evidence rules, the per-side cap |
| `tests/direct/test_omnicourt_resolve.py` | One test per verdict action, plus coercion and clamping of malformed model output |
| `tests/direct/test_omnicourt_evidence_fetch.py` | Dead links, oversized pages, and the rubric reaching the prompt |
| `tests/direct/test_omnicourt_consensus.py` | The validator side: agreement, disagreement, and a failed leader |
| `tests/integration/test_omnicourt.py` | All three dispute types end-to-end against real consensus |

### Deploying your own instance

The published GenLayer CLI (0.39.2) has **no Studio Next preset** — it only
knows Studio (chain 61999), so `genlayer deploy` signs for the wrong chain and
the RPC rejects it with `InvalidChainId`. Use the included script instead:

```shell
DEPLOY_KEY_FILE=/path/to/key node deploy/deployStudioNext.mjs
```

It builds the Studio Next chain from `genlayer-js` directly, quotes the active
fee policy (Consensus v0.6 requires a non-zero fee value or the deploy reverts
with `FeeValueMustBeNonZero`), checks the deployer's balance first, and refuses
to report success on an `UNDETERMINED` receipt.

---

## Deliberately out of scope

Named explicitly, because each is a judgment call rather than a gap.

- **Enforcement.** OmniCourt returns a verdict; it does not move funds or revoke
  permissions on any chain. Enforcement is chain-specific and belongs to the
  calling application.
- **Identity-bound evidence submission.** `submit_evidence` does **not** check
  `gl.message.sender_address` against a stored party address, because a party may
  have no GenLayer wallet at all (a Solana agent, someone who paid by bank
  transfer). Evidence is tagged by role only. This is a real limitation, pinned
  by a test so that changing it is a deliberate act. *V2 path:* signed off-chain
  proofs or ERC-8004 agent identity.
- **Payable filing bonds.** Studio Next does not roll back a value transfer if
  execution reverts afterward, so a payable method that raises after
  `gl.message.value` has arrived strands the caller's funds permanently. Every
  method here is non-payable. Protocol transaction fees are handled by
  Transaction Kit's fee quoting, so no contract-level economics are needed for a
  working system.
- **Appeals.** A bonded appeal flow is a natural next step, not part of a
  coherent minimum.

## Architecture

```
Any app, on any chain (escrow, agent framework, marketplace, wallet)
      |
      | 1. open_dispute(type, complainant_ref, respondent_ref, claim, remedy)
      v
OmniCourt - one deployed GenLayer contract, a persistent dispute registry
      |
      | 2. submit_evidence(dispute_id, role, url)   <- either party, or a relayer
      |    evidence = ANY public URL
      v
resolve_dispute(dispute_id)
      |
      | 3. each validator independently:
      |      - gl.nondet.web.render() every evidence URL
      |      - gl.nondet.exec_prompt() a type-specific rubric prompt
      |      - consensus via gl.eq_principle.prompt_comparative
      v
Verdict on-chain: { recommended_action, allocation_bps, reasoning }
      |
      | 4. get_verdict(dispute_id)  <- any app reads this back
      v
The calling app enforces the outcome in its own domain
```

## License

MIT - see [LICENSE](LICENSE).
