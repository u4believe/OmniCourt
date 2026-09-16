"""How the adjudication block handles imperfect evidence sources.

Validators fetch every evidence URL independently, so the contract has to
cope with a link that is dead and with a page far too large to put in a
prompt. Both are asserted here by inspecting the prompt the model receives.
"""

import json

CONTRACT = "contracts/omnicourt.py"
PROMPT_PERSON_PERSON = r'disputes of type "person_person"'


def _capture_prompt(vm):
    """Register a catch-all LLM mock and record the prompt it is given."""
    seen = []
    original = vm._match_llm_mock

    def spy(prompt):
        seen.append(prompt)
        return original(prompt)

    vm._match_llm_mock = spy
    vm.mock_llm(
        PROMPT_PERSON_PERSON,
        json.dumps(
            json.dumps(
                {
                    "recommended_action": "escalate",
                    "allocation_bps": 0,
                    "reasoning": "Recorded for prompt inspection.",
                }
            )
        ),
    )
    return seen


def _open_with(contract, urls):
    dispute_id = contract.open_dispute(
        "person_person", "c", "r", "Goods never arrived.", "Refund"
    )
    for url in urls:
        contract.submit_evidence(dispute_id, "complainant", url)
    return dispute_id


def test_unfetchable_url_is_reported_not_fatal(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with(contract, ["https://dead.example.com/gone"])
    prompts = _capture_prompt(direct_vm)

    contract.resolve_dispute(dispute_id)

    assert contract.get_verdict(dispute_id)["status"] == "resolved"
    assert len(prompts) == 1
    assert "could not fetch this URL" in prompts[0]
    assert "https://dead.example.com/gone" in prompts[0]


def test_live_and_dead_urls_are_distinguished(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with(
        contract,
        ["https://live.example.com/tracking", "https://dead.example.com/gone"],
    )
    direct_vm.mock_web(
        r".*live\.example\.com.*",
        {"status": 200, "body": "Tracking: delivered 2026-09-03."},
    )
    prompts = _capture_prompt(direct_vm)

    contract.resolve_dispute(dispute_id)

    prompt = prompts[0]
    assert "Tracking: delivered 2026-09-03." in prompt
    assert "could not fetch this URL" in prompt


def test_oversized_page_is_truncated(direct_vm, direct_deploy, direct_alice):
    """One huge page must not be able to crowd out the rest of the evidence."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with(contract, ["https://huge.example.com/page"])
    direct_vm.mock_web(
        r".*huge\.example\.com.*",
        {"status": 200, "body": "A" * 10_000},
    )
    prompts = _capture_prompt(direct_vm)

    contract.resolve_dispute(dispute_id)

    prompt = prompts[0]
    assert "... (truncated)" in prompt
    # 4000 kept characters, and nothing near the original 10k.
    assert "A" * 4000 in prompt
    assert "A" * 4100 not in prompt


def test_prompt_carries_the_dispute_type_rubric(direct_vm, direct_deploy, direct_alice):
    """The type-specific rubric is what makes one registry serve three
    genuinely different relationship types."""
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    dispute_id = _open_with(contract, ["https://live.example.com/x"])
    direct_vm.mock_web(r".*live\.example\.com.*", {"status": 200, "body": "receipt"})
    prompts = _capture_prompt(direct_vm)

    contract.resolve_dispute(dispute_id)

    prompt = prompts[0]
    assert "Both parties are humans in an ordinary commercial exchange." in prompt
    assert "Goods never arrived." in prompt
    assert "Refund" in prompt
