"""Adjudication — one test per verdict shape, with web and LLM mocked.

These tests pin the contract's handling of the model's answer: the happy
paths, the coercion of a malformed answer, and the failure modes around a
dispute that cannot be judged.
"""

from tests.direct.conftest import mock_json_llm

CONTRACT = "contracts/omnicourt.py"

# Matched against the prompt, which names the dispute type on one line.
PROMPT_PERSON_PERSON = r'disputes of type "person_person"'
PROMPT_AGENT_PERSON = r'disputes of type "agent_person"'
PROMPT_AGENT_AGENT = r'disputes of type "agent_agent"'


def _open_with_evidence(
    contract,
    dispute_type,
    claim="The agreed outcome did not happen.",
    remedy="Make me whole",
    complainant_urls=("https://evidence.example.com/complainant",),
    respondent_urls=("https://evidence.example.com/respondent",),
):
    dispute_id = contract.open_dispute(
        dispute_type, "complainant-ref", "respondent-ref", claim, remedy
    )
    for url in complainant_urls:
        contract.submit_evidence(dispute_id, "complainant", url)
    for url in respondent_urls:
        contract.submit_evidence(dispute_id, "respondent", url)
    return dispute_id


def _mock_evidence_pages(vm, body="Status: delivered 2026-09-03, signed for by recipient."):
    vm.mock_web(
        r".*evidence\.example\.com.*",
        {"status": 200, "body": body},
    )


def test_person_person_favors_complainant(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(
        contract,
        "person_person",
        claim="Paid for a laptop, tracking shows it was never scanned as delivered.",
        remedy="Full refund of 950 USDC",
    )
    _mock_evidence_pages(direct_vm, "Tracking 1Z999: label created, never scanned.")
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "favor_complainant",
            "allocation_bps": 10000,
            "reasoning": "Tracking never shows delivery, so the buyer's claim stands.",
        },
    )

    contract.resolve_dispute(dispute_id)

    verdict = contract.get_verdict(dispute_id)
    assert verdict["status"] == "resolved"
    assert verdict["recommended_action"] == "favor_complainant"
    assert verdict["allocation_bps"] == 10000
    assert "never shows delivery" in verdict["reasoning"]


def test_person_person_favors_respondent(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "favor_respondent",
            "allocation_bps": 0,
            "reasoning": "Delivery is confirmed and signed for by the recipient.",
        },
    )

    contract.resolve_dispute(dispute_id)

    verdict = contract.get_verdict(dispute_id)
    assert verdict["recommended_action"] == "favor_respondent"
    assert verdict["allocation_bps"] == 0


def test_agent_person_splits_with_allocation(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(
        contract,
        "agent_person",
        claim="The research agent delivered a report with fabricated citations.",
        remedy="Refund the 200 USDC fee",
    )
    _mock_evidence_pages(
        direct_vm, "Report v3: 12 citations, 4 of which resolve to dead DOIs."
    )
    mock_json_llm(
        direct_vm,
        PROMPT_AGENT_PERSON,
        {
            "recommended_action": "split",
            "allocation_bps": 6000,
            "reasoning": "Most of the report is sound but a third of citations fail.",
        },
    )

    contract.resolve_dispute(dispute_id)

    verdict = contract.get_verdict(dispute_id)
    assert verdict["recommended_action"] == "split"
    assert verdict["allocation_bps"] == 6000


def test_agent_agent_returns_behavioural_action(direct_vm, direct_deploy, direct_alice):
    """An agent-to-agent breach can warrant constraining authority, not money."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(
        contract,
        "agent_agent",
        claim="Respondent agent charged for an API call it never completed.",
        remedy="Revoke its spending authority",
    )
    _mock_evidence_pages(direct_vm, "API log: 502 Bad Gateway, no payload returned.")
    mock_json_llm(
        direct_vm,
        PROMPT_AGENT_AGENT,
        {
            "recommended_action": "constrain",
            "allocation_bps": 0,
            "reasoning": "The agent billed for a call that returned no payload.",
        },
    )

    contract.resolve_dispute(dispute_id)

    verdict = contract.get_verdict(dispute_id)
    assert verdict["recommended_action"] == "constrain"
    assert verdict["allocation_bps"] == 0


def test_contradictory_evidence_escalates(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm, "Two records disagree on whether delivery occurred.")
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "escalate",
            "allocation_bps": 0,
            "reasoning": "The two records directly contradict each other.",
        },
    )

    contract.resolve_dispute(dispute_id)

    assert contract.get_verdict(dispute_id)["recommended_action"] == "escalate"


def test_unrecognised_action_is_coerced_to_escalate(
    direct_vm, direct_deploy, direct_alice
):
    """A model that invents an action must not be able to store it."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "imprison_the_seller",
            "allocation_bps": 10000,
            "reasoning": "Invented an action outside the allowed set.",
        },
    )

    contract.resolve_dispute(dispute_id)

    assert contract.get_verdict(dispute_id)["recommended_action"] == "escalate"


def test_out_of_range_allocation_is_clamped(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "favor_complainant",
            "allocation_bps": 99999,
            "reasoning": "Allocation well outside the basis-point range.",
        },
    )

    contract.resolve_dispute(dispute_id)

    assert contract.get_verdict(dispute_id)["allocation_bps"] == 10000


def test_negative_allocation_is_clamped_to_zero(direct_vm, direct_deploy, direct_alice):
    """u256 cannot hold a negative value, so this must be clamped, not stored."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "favor_respondent",
            "allocation_bps": -500,
            "reasoning": "Negative allocation supplied by the model.",
        },
    )

    contract.resolve_dispute(dispute_id)

    assert contract.get_verdict(dispute_id)["allocation_bps"] == 0


def test_non_numeric_allocation_falls_back_to_zero(
    direct_vm, direct_deploy, direct_alice
):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "warn",
            "allocation_bps": "not a number",
            "reasoning": "Behavioural action with an unparseable allocation.",
        },
    )

    contract.resolve_dispute(dispute_id)

    verdict = contract.get_verdict(dispute_id)
    assert verdict["recommended_action"] == "warn"
    assert verdict["allocation_bps"] == 0


def test_missing_reasoning_gets_a_placeholder(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {"recommended_action": "split", "allocation_bps": 5000},
    )

    contract.resolve_dispute(dispute_id)

    assert contract.get_verdict(dispute_id)["reasoning"] == (
        "No reasoning supplied by the adjudicating model."
    )


def test_one_sided_evidence_still_resolves(direct_vm, direct_deploy, direct_alice):
    """A silent respondent must not be able to stall adjudication."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(
        contract, "person_person", respondent_urls=()
    )
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "favor_complainant",
            "allocation_bps": 10000,
            "reasoning": "The respondent filed nothing to rebut the claim.",
        },
    )

    contract.resolve_dispute(dispute_id)

    assert contract.get_verdict(dispute_id)["status"] == "resolved"


def test_resolve_without_evidence_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = contract.open_dispute(
        "person_person", "c", "r", "Nothing to show for it.", "Refund"
    )

    with direct_vm.expect_revert("at least one evidence item is required"):
        contract.resolve_dispute(dispute_id)

    assert contract.get_dispute(dispute_id)["status"] == "open"


def test_resolving_twice_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "favor_respondent",
            "allocation_bps": 0,
            "reasoning": "Delivery confirmed.",
        },
    )

    contract.resolve_dispute(dispute_id)

    with direct_vm.expect_revert("Dispute is not open"):
        contract.resolve_dispute(dispute_id)


def test_resolving_unknown_dispute_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("Dispute does not exist"):
        contract.resolve_dispute(7)


def test_evidence_cannot_be_added_after_resolution(
    direct_vm, direct_deploy, direct_alice
):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": "split",
            "allocation_bps": 5000,
            "reasoning": "Both sides are partly right.",
        },
    )

    contract.resolve_dispute(dispute_id)

    with direct_vm.expect_revert("Dispute is not open"):
        contract.submit_evidence(dispute_id, "complainant", "https://example.com/late")


def test_resolution_preserves_the_evidence_trail(
    direct_vm, direct_deploy, direct_alice
):
    """The registry keeps the record a reviewer needs to audit the verdict."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(
        contract,
        "agent_agent",
        complainant_urls=(
            "https://evidence.example.com/invoice",
            "https://evidence.example.com/log",
        ),
        respondent_urls=("https://evidence.example.com/receipt",),
    )
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_AGENT_AGENT,
        {
            "recommended_action": "warn",
            "allocation_bps": 0,
            "reasoning": "A first, recoverable breach of the mandate.",
        },
    )

    contract.resolve_dispute(dispute_id)

    dispute = contract.get_dispute(dispute_id)
    assert dispute["status"] == "resolved"
    assert len(dispute["complainant_evidence"]) == 2
    assert len(dispute["respondent_evidence"]) == 1
    assert dispute["verdict_action"] == "warn"
    assert dispute["claim_description"] != ""


# ----------------------------------------------------------------------
# Reopening — an escalate verdict asks for more evidence, so it must not
# be a dead end. A decided verdict must not be re-rollable.
# ----------------------------------------------------------------------


def _resolve_as(direct_vm, contract, dispute_id, action, allocation_bps=0):
    _mock_evidence_pages(direct_vm)
    mock_json_llm(
        direct_vm,
        PROMPT_PERSON_PERSON,
        {
            "recommended_action": action,
            "allocation_bps": allocation_bps,
            "reasoning": f"Resolved as {action}.",
        },
    )
    contract.resolve_dispute(dispute_id)


def test_escalated_dispute_can_be_reopened(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _resolve_as(direct_vm, contract, dispute_id, "escalate")

    contract.reopen_dispute(dispute_id)

    dispute = contract.get_dispute(dispute_id)
    assert dispute["status"] == "open"
    # The undecided verdict is cleared, but the evidence trail survives.
    assert dispute["verdict_action"] == ""
    assert dispute["verdict_reasoning"] == ""
    assert len(dispute["complainant_evidence"]) == 1
    assert len(dispute["respondent_evidence"]) == 1


def test_reopened_dispute_accepts_more_evidence(direct_vm, direct_deploy, direct_alice):
    """The whole point: the complainant can answer what the verdict asked for."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _resolve_as(direct_vm, contract, dispute_id, "escalate")
    contract.reopen_dispute(dispute_id)

    contract.submit_evidence(
        dispute_id, "complainant", "https://evidence.example.com/receipt"
    )

    assert len(contract.get_dispute(dispute_id)["complainant_evidence"]) == 2


def test_reopened_dispute_can_reach_a_real_verdict(
    direct_vm, direct_deploy, direct_alice
):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _resolve_as(direct_vm, contract, dispute_id, "escalate")
    contract.reopen_dispute(dispute_id)
    contract.submit_evidence(
        dispute_id, "complainant", "https://evidence.example.com/receipt"
    )

    direct_vm.clear_mocks()
    _resolve_as(direct_vm, contract, dispute_id, "favor_complainant", 10000)

    verdict = contract.get_verdict(dispute_id)
    assert verdict["recommended_action"] == "favor_complainant"
    assert verdict["allocation_bps"] == 10000


def test_a_decided_verdict_cannot_be_re_rolled(direct_vm, direct_deploy, direct_alice):
    """Otherwise a losing party re-adjudicates until the answer changes."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")
    _resolve_as(direct_vm, contract, dispute_id, "favor_respondent")

    with direct_vm.expect_revert("Only an escalated dispute can be reopened"):
        contract.reopen_dispute(dispute_id)

    assert contract.get_verdict(dispute_id)["recommended_action"] == "favor_respondent"


def test_open_dispute_cannot_be_reopened(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")

    with direct_vm.expect_revert("Dispute is not resolved"):
        contract.reopen_dispute(dispute_id)


def test_reopening_unknown_dispute_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("Dispute does not exist"):
        contract.reopen_dispute(5)


def test_reopening_is_capped(direct_vm, direct_deploy, direct_alice):
    """A dispute cannot bounce between escalate and reopen forever."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")

    for _ in range(3):
        direct_vm.clear_mocks()
        _resolve_as(direct_vm, contract, dispute_id, "escalate")
        if contract.get_dispute(dispute_id)["resolution_rounds"] < 3:
            contract.reopen_dispute(dispute_id)

    assert contract.get_dispute(dispute_id)["resolution_rounds"] == 3
    with direct_vm.expect_revert("has been adjudicated 3 times"):
        contract.reopen_dispute(dispute_id)


def test_resolution_rounds_start_at_zero(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with_evidence(contract, "person_person")

    assert contract.get_dispute(dispute_id)["resolution_rounds"] == 0
