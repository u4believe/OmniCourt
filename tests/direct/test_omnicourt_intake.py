"""Intake and evidence-submission logic — deterministic, no mocks needed."""

CONTRACT = "contracts/omnicourt.py"


def _open_person_person(contract):
    return contract.open_dispute(
        "person_person",
        "buyer:alice@example.com",
        "seller:bob@example.com",
        "Paid for a laptop on 2026-09-01, never arrived.",
        "Full refund of 950 USDC",
    )


def test_open_dispute_stores_registry_entry(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    dispute_id = _open_person_person(contract)

    assert dispute_id == 0
    assert contract.dispute_count() == 1

    dispute = contract.get_dispute(0)
    assert dispute["dispute_type"] == "person_person"
    assert dispute["complainant_ref"] == "buyer:alice@example.com"
    assert dispute["respondent_ref"] == "seller:bob@example.com"
    assert dispute["status"] == "open"
    assert dispute["complainant_evidence"] == []
    assert dispute["respondent_evidence"] == []
    assert dispute["verdict_action"] == ""
    assert dispute["verdict_allocation_bps"] == 0
    assert dispute["verdict_reasoning"] == ""


def test_dispute_ids_increment_across_types(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    first = _open_person_person(contract)
    second = contract.open_dispute(
        "agent_person", "agent:0xfeed", "human:carol", "Report was fabricated.", "Redo"
    )
    third = contract.open_dispute(
        "agent_agent", "agent:a", "agent:b", "Paid task never delivered.", "Refund"
    )

    assert [first, second, third] == [0, 1, 2]
    assert contract.dispute_count() == 3
    assert contract.get_dispute(1)["dispute_type"] == "agent_person"
    assert contract.get_dispute(2)["dispute_type"] == "agent_agent"


def test_all_three_dispute_types_are_accepted(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    for dispute_type in ("agent_agent", "agent_person", "person_person"):
        dispute_id = contract.open_dispute(
            dispute_type, "c", "r", "a claim", "a remedy"
        )
        assert contract.get_dispute(dispute_id)["dispute_type"] == dispute_type


def test_invalid_dispute_type_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("dispute_type must be"):
        contract.open_dispute("cat_dog", "c", "r", "a claim", "a remedy")

    assert contract.dispute_count() == 0


def test_empty_claim_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("claim_description must not be empty"):
        contract.open_dispute("person_person", "c", "r", "   ", "a remedy")


def test_submit_evidence_to_both_sides(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_person_person(contract)

    contract.submit_evidence(dispute_id, "complainant", "https://example.com/chat-log")
    contract.submit_evidence(dispute_id, "complainant", "https://example.com/receipt")
    contract.submit_evidence(dispute_id, "respondent", "https://example.com/tracking")

    dispute = contract.get_dispute(dispute_id)
    assert dispute["complainant_evidence"] == [
        "https://example.com/chat-log",
        "https://example.com/receipt",
    ]
    assert dispute["respondent_evidence"] == ["https://example.com/tracking"]


def test_evidence_url_is_trimmed(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_person_person(contract)

    contract.submit_evidence(dispute_id, "respondent", "  https://example.com/x  ")

    assert contract.get_dispute(dispute_id)["respondent_evidence"] == [
        "https://example.com/x"
    ]


def test_invalid_role_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_person_person(contract)

    with direct_vm.expect_revert("role must be"):
        contract.submit_evidence(dispute_id, "judge", "https://example.com/x")


def test_non_http_evidence_url_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_person_person(contract)

    with direct_vm.expect_revert("must be an http(s) URL"):
        contract.submit_evidence(dispute_id, "complainant", "ftp://example.com/x")


def test_empty_evidence_url_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_person_person(contract)

    with direct_vm.expect_revert("evidence_url must not be empty"):
        contract.submit_evidence(dispute_id, "complainant", "   ")


def test_evidence_cap_per_side(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_person_person(contract)

    for index in range(8):
        contract.submit_evidence(
            dispute_id, "complainant", f"https://example.com/{index}"
        )

    with direct_vm.expect_revert("at most 8 evidence items per side"):
        contract.submit_evidence(dispute_id, "complainant", "https://example.com/9")

    # The cap is per side, so the respondent is unaffected.
    contract.submit_evidence(dispute_id, "respondent", "https://example.com/defence")
    dispute = contract.get_dispute(dispute_id)
    assert len(dispute["complainant_evidence"]) == 8
    assert len(dispute["respondent_evidence"]) == 1


def test_evidence_on_unknown_dispute_is_rejected(
    direct_vm, direct_deploy, direct_alice
):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("Dispute does not exist"):
        contract.submit_evidence(99, "complainant", "https://example.com/x")


def test_evidence_submission_is_open_to_any_sender(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """Documented design choice: submission is not identity-bound.

    A party may have no GenLayer wallet at all, so any sender may file
    evidence under either role. This test pins that behaviour so a future
    change to it is a deliberate one.
    """
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_person_person(contract)

    direct_vm.sender = direct_bob
    contract.submit_evidence(dispute_id, "complainant", "https://example.com/relayed")

    assert contract.get_dispute(dispute_id)["complainant_evidence"] == [
        "https://example.com/relayed"
    ]


def test_unknown_dispute_reads_are_empty(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    assert contract.get_dispute(42) == {}
    assert contract.get_verdict(42) == {
        "status": "",
        "recommended_action": "",
        "allocation_bps": 0,
        "reasoning": "",
    }
    assert contract.dispute_count() == 0
    assert contract.list_disputes() == []


def test_list_disputes_returns_every_entry(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice

    _open_person_person(contract)
    contract.open_dispute("agent_agent", "a", "b", "claim", "remedy")

    listed = contract.list_disputes()
    assert [entry["id"] for entry in listed] == [0, 1]
    assert [entry["dispute_type"] for entry in listed] == [
        "person_person",
        "agent_agent",
    ]
