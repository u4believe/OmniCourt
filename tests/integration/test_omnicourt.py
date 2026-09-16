"""End-to-end OmniCourt tests against a GenLayer network.

Run with: gltest tests/integration/ -v -s

Each test drives one full cycle — open, submit evidence, resolve, read the
verdict back — against real consensus with mock validators, one per dispute
type. This is the shape an integrating application sees.
"""

import pytest
from gltest import get_contract_factory, get_default_account, get_validator_factory
from gltest.assertions import tx_execution_succeeded
from gltest.clients import get_gl_client
from gltest.fees import fee_profile_enabled, get_fee_profile_collector
from gltest.helpers import load_fixture
from gltest.types import MockedLLMResponse, MockedWebResponse

default_account = get_default_account()

FEE_ESTIMATE_OPTIONS = {
    "leaderTimeunitsAllocation": 100,
    "validatorTimeunitsAllocation": 200,
    "rotations": [1],
}

EQUIVALENCE_PRINCIPLE = (
    "Both answers recommend the same action category, and their "
    "allocation_bps values are within 1500 of each other (roughly the same "
    "split), even if the reasoning wording differs."
)

TRACKING_URL = "https://tracking.example.com/1Z999AA10123456784"
SELLER_RECEIPT_URL = "https://receipts.example.com/order-4471"
AGENT_REPORT_URL = "https://artifacts.example.com/research-report-v3"
AGENT_BRIEF_URL = "https://artifacts.example.com/task-brief"
AGENT_A_INVOICE_URL = "https://api.example.com/invoice/8812"
AGENT_B_LOG_URL = "https://api.example.com/logs/8812"


def transaction_fee_preset():
    estimate = get_gl_client().estimate_transaction_fees(FEE_ESTIMATE_OPTIONS)
    return {
        "distribution": estimate["distribution"],
        "feeValue": estimate["feeValue"],
    }


def fee_profile_wait_until():
    return "finalized" if fee_profile_enabled() else None


def make_adjudication_context(dispute_type, pages, verdict):
    """Build a validator set that sees `pages` and returns `verdict`.

    Every validator gets the same mocked evidence and verdict, so the
    comparative principle is satisfied and consensus is reached — the
    disagreement paths are covered by the direct-mode consensus tests.
    """
    mock_llm_response: MockedLLMResponse = {
        "nondet_exec_prompt": {
            f'disputes of type "{dispute_type}"': verdict,
        },
        "eq_principle_prompt_comparative": {EQUIVALENCE_PRINCIPLE: True},
        "eq_principle_prompt_non_comparative": {},
    }
    mock_web_response: MockedWebResponse = {
        "nondet_web_request": {
            url: {"method": "GET", "status": 200, "body": body}
            for url, body in pages.items()
        }
    }
    validators = get_validator_factory().batch_create_mock_validators(
        count=5,
        mock_llm_response=mock_llm_response,
        mock_web_response=mock_web_response,
    )
    return {"validators": [validator.to_dict() for validator in validators]}


def verdict_json(action, allocation_bps, reasoning):
    return (
        f'{{"recommended_action": "{action}", '
        f'"allocation_bps": {allocation_bps}, '
        f'"reasoning": "{reasoning}"}}'
    )


@pytest.mark.integration
def deploy_contract():
    factory = get_contract_factory("OmniCourt")
    contract = factory.deploy(
        fees=transaction_fee_preset(),
        wait_until=fee_profile_wait_until(),
    )

    # A freshly deployed registry is empty — this is the check that proves
    # the contract is live and holding real state.
    assert contract.dispute_count(args=[]).call() == 0
    assert contract.list_disputes(args=[]).call() == []
    return contract


def _open(contract, dispute_type, complainant, respondent, claim, remedy):
    result = contract.open_dispute(
        args=[dispute_type, complainant, respondent, claim, remedy]
    ).transact(fees=transaction_fee_preset())
    assert tx_execution_succeeded(result)


def _submit(contract, dispute_id, role, url):
    result = contract.submit_evidence(args=[dispute_id, role, url]).transact(
        fees=transaction_fee_preset()
    )
    assert tx_execution_succeeded(result)


def _resolve(contract, dispute_id, context):
    result = contract.resolve_dispute(args=[dispute_id]).transact(
        fees=transaction_fee_preset(),
        wait_interval=10000,
        wait_retries=20,
        transaction_context=context,
    )
    assert tx_execution_succeeded(result)


@pytest.mark.integration
def test_fee_profile_open_dispute():
    """Measure deploy + open_dispute fees for a developer fee profile.

    Run with: npm run test:fees (requires a running GenLayer Studio).
    """
    if not fee_profile_enabled():
        pytest.skip("fee profile generation requires --fee-profile")

    contract = load_fixture(deploy_contract)

    result = contract.open_dispute(
        args=[
            "person_person",
            "buyer:alice@example.com",
            "seller:bob@example.com",
            "Paid for a laptop that never arrived.",
            "Full refund",
        ]
    ).transact(fees=transaction_fee_preset(), wait_until="finalized")
    assert tx_execution_succeeded(result)

    profile = get_fee_profile_collector().build_profile(
        network="localnet", headroom=1.0
    )
    assert int(profile["deploy"]["executionBudgetPerRound"]) > 0
    assert int(profile["methods"]["open_dispute"]["executionBudgetPerRound"]) > 0


@pytest.mark.integration
def test_deploys_empty_registry():
    contract = load_fixture(deploy_contract)

    assert contract.dispute_count(args=[]).call() == 0
    assert contract.get_verdict(args=[0]).call() == {
        "status": "",
        "recommended_action": "",
        "allocation_bps": 0,
        "reasoning": "",
    }


@pytest.mark.integration
def test_person_person_non_delivery():
    """A plain chargeback: the buyer says it never came, tracking agrees."""
    contract = load_fixture(deploy_contract)

    _open(
        contract,
        "person_person",
        "buyer:alice@example.com",
        "seller:bob@example.com",
        "Paid 950 USDC for a laptop on 2026-09-01. It never arrived.",
        "Full refund of 950 USDC",
    )
    dispute_id = contract.dispute_count(args=[]).call() - 1

    _submit(contract, dispute_id, "complainant", TRACKING_URL)
    _submit(contract, dispute_id, "respondent", SELLER_RECEIPT_URL)

    dispute = contract.get_dispute(args=[dispute_id]).call()
    assert dispute["status"] == "open"
    assert dispute["complainant_evidence"] == [TRACKING_URL]
    assert dispute["respondent_evidence"] == [SELLER_RECEIPT_URL]

    context = make_adjudication_context(
        "person_person",
        {
            TRACKING_URL: (
                "Tracking 1Z999AA10123456784 — Label created 2026-09-01. "
                "No further scans. Status: Label Created."
            ),
            SELLER_RECEIPT_URL: (
                "Order 4471 — marked shipped 2026-09-01 by seller. "
                "No carrier acceptance scan on record."
            ),
        },
        verdict_json(
            "favor_complainant",
            10000,
            "The carrier never accepted the parcel, so non-delivery stands.",
        ),
    )
    _resolve(contract, dispute_id, context)

    verdict = contract.get_verdict(args=[dispute_id]).call()
    assert verdict["status"] == "resolved"
    assert verdict["recommended_action"] == "favor_complainant"
    assert verdict["allocation_bps"] == 10000
    assert verdict["reasoning"] != ""


@pytest.mark.integration
def test_agent_person_partial_performance():
    """A human says the agent's deliverable missed spec; it partly did."""
    contract = load_fixture(deploy_contract)

    _open(
        contract,
        "agent_person",
        "human:carol@example.com",
        "agent:0xfeedbeefresearchbot",
        "The research agent delivered a report with fabricated citations.",
        "Refund the 200 USDC fee",
    )
    dispute_id = contract.dispute_count(args=[]).call() - 1

    _submit(contract, dispute_id, "complainant", AGENT_REPORT_URL)
    _submit(contract, dispute_id, "respondent", AGENT_BRIEF_URL)

    context = make_adjudication_context(
        "agent_person",
        {
            AGENT_REPORT_URL: (
                "Research report v3 — 12 citations. Verification pass: 8 resolve "
                "to live DOIs, 4 resolve to nothing."
            ),
            AGENT_BRIEF_URL: (
                "Task brief: summarise recent literature. No explicit citation "
                "verification requirement was stated."
            ),
        },
        verdict_json(
            "split",
            6000,
            "Two thirds of the report is sound but a third of citations fail.",
        ),
    )
    _resolve(contract, dispute_id, context)

    verdict = contract.get_verdict(args=[dispute_id]).call()
    assert verdict["status"] == "resolved"
    assert verdict["recommended_action"] == "split"
    assert verdict["allocation_bps"] == 6000


@pytest.mark.integration
def test_agent_agent_mandate_breach():
    """Two agents disagree on whether a paid API task completed.

    This is the sharpest case for decentralized judgment: no single server
    should unilaterally decide whether another AI agent breached its mandate.
    """
    contract = load_fixture(deploy_contract)

    _open(
        contract,
        "agent_agent",
        "agent:0xaaa1payer",
        "agent:0xbbb2provider",
        "Respondent agent billed for an inference call it never completed.",
        "Revoke its spending authority",
    )
    dispute_id = contract.dispute_count(args=[]).call() - 1

    _submit(contract, dispute_id, "complainant", AGENT_A_INVOICE_URL)
    _submit(contract, dispute_id, "respondent", AGENT_B_LOG_URL)

    context = make_adjudication_context(
        "agent_agent",
        {
            AGENT_A_INVOICE_URL: (
                "Invoice 8812 — 1 inference call, 0.4 GEN, status BILLED."
            ),
            AGENT_B_LOG_URL: (
                "Request 8812 — upstream returned 502 Bad Gateway. "
                "No payload delivered to caller."
            ),
        },
        verdict_json(
            "constrain",
            0,
            "The provider billed for a call that returned no payload.",
        ),
    )
    _resolve(contract, dispute_id, context)

    verdict = contract.get_verdict(args=[dispute_id]).call()
    assert verdict["status"] == "resolved"
    assert verdict["recommended_action"] == "constrain"
    # A behavioural verdict carries no financial allocation.
    assert verdict["allocation_bps"] == 0


@pytest.mark.integration
def test_registry_serves_many_disputes():
    """One deployed contract, many disputes — the multi-tenant registry shape."""
    contract = load_fixture(deploy_contract)

    before = contract.dispute_count(args=[]).call()
    for dispute_type in ("agent_agent", "agent_person", "person_person"):
        _open(
            contract,
            dispute_type,
            "complainant-ref",
            "respondent-ref",
            f"A {dispute_type} claim.",
            "A remedy",
        )
    after = contract.dispute_count(args=[]).call()

    assert after - before == 3
    listed = contract.list_disputes(args=[]).call()
    assert len(listed) == after
    assert {entry["dispute_type"] for entry in listed[-3:]} == {
        "agent_agent",
        "agent_person",
        "person_person",
    }


@pytest.mark.integration
def test_invalid_dispute_type_is_rejected_on_chain():
    contract = load_fixture(deploy_contract)

    before = contract.dispute_count(args=[]).call()
    result = contract.open_dispute(
        args=["cat_dog", "c", "r", "a claim", "a remedy"]
    ).transact(fees=transaction_fee_preset())

    assert not tx_execution_succeeded(result)
    assert contract.dispute_count(args=[]).call() == before
