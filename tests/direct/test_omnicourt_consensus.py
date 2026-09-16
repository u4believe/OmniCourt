"""The validator side of adjudication.

`resolve_dispute` decides via `gl.eq_principle.prompt_comparative`, so every
validator re-fetches the evidence and re-judges it independently rather than
rubber-stamping the leader. These tests drive that validator path with
`direct_vm.run_validator()`.

Direct mode has no handler for the `EqComparative` comparison itself, so a
`_gl_call_hook` stands in for it. The hook also captures what the contract
passed to the comparison, which is what lets us assert that both answers and
the intended principle actually reach it.
"""

import json

CONTRACT = "contracts/omnicourt.py"
PROMPT_PERSON_PERSON = r'disputes of type "person_person"'

EXPECTED_PRINCIPLE = (
    "Both answers recommend the same action category, and their "
    "allocation_bps values are within 1500 of each other (roughly the same "
    "split), even if the reasoning wording differs."
)


def _install_comparison_hook(vm):
    """Stand in for the network's EqComparative step.

    Applies a literal reading of the contract's own principle — same action,
    allocations within 1500 — and records each comparison for inspection.
    """
    calls = []

    def hook(_vm, request):
        template = request.get("ExecPromptTemplate")
        if template is None:
            return None
        calls.append(template)

        leader = _parse_answer(template["leader_answer"])
        validator = _parse_answer(template["validator_answer"])
        if leader is None or validator is None:
            return {"ok": False}

        same_action = (
            leader["recommended_action"] == validator["recommended_action"]
        )
        close_allocation = (
            abs(int(leader["allocation_bps"]) - int(validator["allocation_bps"]))
            <= 1500
        )
        return {"ok": same_action and close_allocation}

    vm._gl_call_hook = hook
    return calls


def _parse_answer(raw):
    """Pull the verdict JSON out of a calldata-formatted answer."""
    if not isinstance(raw, str):
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except ValueError:
        return None


def _mock_verdict(vm, action, allocation_bps, reasoning="Because of the evidence."):
    vm.mock_llm(
        PROMPT_PERSON_PERSON,
        json.dumps(
            json.dumps(
                {
                    "recommended_action": action,
                    "allocation_bps": allocation_bps,
                    "reasoning": reasoning,
                }
            )
        ),
    )


def _resolved_dispute(contract, vm, action, allocation_bps):
    dispute_id = contract.open_dispute(
        "person_person", "buyer", "seller", "Item never arrived.", "Refund"
    )
    contract.submit_evidence(dispute_id, "complainant", "https://evidence.example.com/a")
    vm.mock_web(
        r".*evidence\.example\.com.*",
        {"status": 200, "body": "Tracking: label created, never scanned."},
    )
    _mock_verdict(vm, action, allocation_bps)
    contract.resolve_dispute(dispute_id)
    return dispute_id


def test_validator_agrees_on_the_same_evidence(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    comparisons = _install_comparison_hook(direct_vm)

    dispute_id = _resolved_dispute(contract, direct_vm, "favor_complainant", 10000)

    assert contract.get_verdict(dispute_id)["recommended_action"] == "favor_complainant"
    assert direct_vm.run_validator() is True
    assert len(comparisons) == 1
    assert comparisons[0]["principle"] == EXPECTED_PRINCIPLE


def test_validator_rejects_a_different_action(direct_vm, direct_deploy, direct_alice):
    """A validator that reads the evidence differently does not agree."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    comparisons = _install_comparison_hook(direct_vm)
    _resolved_dispute(contract, direct_vm, "favor_complainant", 10000)

    # The validator re-runs the adjudication against whatever it sees now.
    direct_vm.clear_mocks()
    direct_vm.mock_web(
        r".*evidence\.example\.com.*",
        {"status": 200, "body": "Tracking: delivered and signed for."},
    )
    _mock_verdict(direct_vm, "favor_respondent", 0)

    assert direct_vm.run_validator() is False
    leader, validator = comparisons[0]["leader_answer"], comparisons[0]["validator_answer"]
    assert "favor_complainant" in leader
    assert "favor_respondent" in validator


def test_validator_tolerates_a_near_identical_split(
    direct_vm, direct_deploy, direct_alice
):
    """The principle deliberately allows small allocation differences."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    _install_comparison_hook(direct_vm)
    _resolved_dispute(contract, direct_vm, "split", 5000)

    direct_vm.clear_mocks()
    direct_vm.mock_web(
        r".*evidence\.example\.com.*",
        {"status": 200, "body": "Tracking: label created, never scanned."},
    )
    _mock_verdict(direct_vm, "split", 6000, reasoning="Worded quite differently.")

    assert direct_vm.run_validator() is True


def test_validator_rejects_a_far_apart_split(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    _install_comparison_hook(direct_vm)
    _resolved_dispute(contract, direct_vm, "split", 5000)

    direct_vm.clear_mocks()
    direct_vm.mock_web(
        r".*evidence\.example\.com.*",
        {"status": 200, "body": "Tracking: label created, never scanned."},
    )
    _mock_verdict(direct_vm, "split", 9500)

    assert direct_vm.run_validator() is False


def test_validator_rejects_a_failed_leader(direct_vm, direct_deploy, direct_alice):
    """If the leader errored but this validator succeeded, it votes against."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    _install_comparison_hook(direct_vm)
    _resolved_dispute(contract, direct_vm, "favor_complainant", 10000)

    assert direct_vm.run_validator(leader_error=RuntimeError("leader crashed")) is False
