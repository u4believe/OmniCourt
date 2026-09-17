# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
"""OmniCourt — a chain-agnostic dispute adjudication registry.

A single deployed registry that any application, on any chain or none at
all, can call into to have a disputed transaction adjudicated by
decentralized AI validators. Evidence is any public URL; validators
independently re-fetch it and re-judge, so no single arbiter decides the
outcome.

OmniCourt is a judgment layer, not an enforcement layer: it stores a
verdict, and the calling application enforces it in its own domain.
"""

import json
from dataclasses import dataclass

import genlayer as gl
from genlayer.storage import allow as allow_storage

# The three relationship types a dispute can take. Every dispute is one of
# these, which is what lets a single registry serve agent-to-agent,
# agent-to-person, and person-to-person conflicts.
TYPE_AGENT_AGENT = "agent_agent"
TYPE_AGENT_PERSON = "agent_person"
TYPE_PERSON_PERSON = "person_person"
VALID_TYPES = (TYPE_AGENT_AGENT, TYPE_AGENT_PERSON, TYPE_PERSON_PERSON)

ROLE_COMPLAINANT = "complainant"
ROLE_RESPONDENT = "respondent"

STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"

ACTION_ESCALATE = "escalate"
# A verdict merges the financial vocabulary (who gets the money) with the
# behavioural one (what happens to the agent's authority), so one schema
# covers all three dispute types.
VALID_ACTIONS = (
    "favor_complainant",
    "favor_respondent",
    "split",
    "warn",
    "constrain",
    "revoke",
    ACTION_ESCALATE,
)

MAX_EVIDENCE_PER_SIDE = 8
# Each fetched page is truncated before it reaches the prompt so that one
# huge page cannot crowd out the rest of the evidence or blow the context.
EVIDENCE_CHAR_LIMIT = 4000
ALLOCATION_MAX = 10000

# Many block explorers sit behind bot protection. The interstitial they serve
# often arrives as a normal 200 response, so fetching "succeeds" and a
# challenge page reaches the model dressed as evidence. Detecting these keeps
# an unreadable source from silently carrying evidentiary weight.
CHALLENGE_MARKERS = (
    "just a moment",
    "checking your browser",
    "enable javascript and cookies",
    "cf-browser-verification",
    "challenge-platform",
    "attention required!",
    "verify you are human",
    "ddos protection by",
    "please turn javascript on",
)

RUBRICS = {
    TYPE_AGENT_AGENT: (
        "Both parties are AI agents transacting under some mandate. "
        "Weigh: did the respondent agent's output/action match what was "
        "promised or specified? Is there evidence of API responses, "
        "transaction receipts, or logged output? Favor 'escalate' if "
        "mandate terms are too vague to judge."
    ),
    TYPE_AGENT_PERSON: (
        "The respondent is an AI agent, the complainant is a human (or "
        "vice versa). Weigh: did the agent perform the requested task to "
        "a reasonable standard? Consider delivered artifacts, logs, and "
        "any explicit instructions the agent was given."
    ),
    TYPE_PERSON_PERSON: (
        "Both parties are humans in an ordinary commercial exchange. "
        "Weigh: delivery confirmations, tracking data, timestamps, and "
        "any explicit claims in the evidence, as in a standard chargeback."
    ),
}

EQUIVALENCE_PRINCIPLE = (
    "Both answers recommend the same action category, and their "
    "allocation_bps values are within 1500 of each other (roughly the same "
    "split), even if the reasoning wording differs."
)


@allow_storage
@dataclass
class Dispute:
    dispute_type: str
    complainant_ref: str
    respondent_ref: str
    claim_description: str
    requested_remedy: str
    status: str
    complainant_evidence: gl.storage.DynArray[str]
    respondent_evidence: gl.storage.DynArray[str]
    verdict_action: str
    verdict_allocation_bps: gl.u256
    verdict_reasoning: str


def _clamp_allocation(raw: object) -> int:
    """Coerce a model-supplied allocation into 0..10000.

    The model is asked for an integer but may return a float or a numeric
    string; anything unparseable is treated as 0 rather than aborting an
    otherwise valid verdict.
    """
    try:
        value = int(float(raw))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, min(ALLOCATION_MAX, value))


def _truncate(text: str) -> str:
    if len(text) <= EVIDENCE_CHAR_LIMIT:
        return text
    return text[:EVIDENCE_CHAR_LIMIT] + "... (truncated)"


def _unreadable_reason(text: str) -> str:
    """Why this fetched page cannot serve as evidence, or "" if it can.

    Deliberately narrow: only an empty body or an explicit bot-protection
    interstitial. A short response is still real evidence — an API returning
    `{"completed": false}` is exactly the kind of source this is built for.
    """
    stripped = text.strip()
    if not stripped:
        return "the source returned no readable text"
    lowered = stripped.lower()
    for marker in CHALLENGE_MARKERS:
        if marker in lowered:
            return (
                "the source served a bot-protection challenge page instead of "
                "content, so its actual data could not be read"
            )
    return ""


class OmniCourt(gl.contract.Contract):
    next_dispute_id: gl.u256
    disputes: gl.storage.TreeMap[gl.u256, Dispute]

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Intake
    # ------------------------------------------------------------------

    @gl.public.write
    def open_dispute(
        self,
        dispute_type: str,
        complainant_ref: str,
        respondent_ref: str,
        claim_description: str,
        requested_remedy: str,
    ) -> gl.u256:
        if dispute_type not in VALID_TYPES:
            raise gl.vm.UserError(
                "dispute_type must be agent_agent, agent_person, or person_person"
            )
        if not claim_description.strip():
            raise gl.vm.UserError("claim_description must not be empty")

        dispute_id = self.next_dispute_id
        dispute = self.disputes.get_or_insert_default(dispute_id)
        dispute.dispute_type = dispute_type
        dispute.complainant_ref = complainant_ref
        dispute.respondent_ref = respondent_ref
        dispute.claim_description = claim_description
        dispute.requested_remedy = requested_remedy
        dispute.status = STATUS_OPEN
        dispute.verdict_action = ""
        dispute.verdict_allocation_bps = gl.u256(0)
        dispute.verdict_reasoning = ""

        self.next_dispute_id = dispute_id + gl.u256(1)
        return dispute_id

    @gl.public.write
    def submit_evidence(
        self, dispute_id: gl.u256, role: str, evidence_url: str
    ) -> None:
        """Attach a public evidence URL to one side of an open dispute.

        Submission is intentionally open: a party may have no GenLayer
        wallet at all (a Solana agent, someone who paid by bank transfer),
        so evidence is tagged by role rather than checked against a stored
        address. See the README for this documented limitation.
        """
        dispute = self._require_open(dispute_id)

        url = evidence_url.strip()
        if not url:
            raise gl.vm.UserError("evidence_url must not be empty")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise gl.vm.UserError("evidence_url must be an http(s) URL")

        if role == ROLE_COMPLAINANT:
            bucket = dispute.complainant_evidence
        elif role == ROLE_RESPONDENT:
            bucket = dispute.respondent_evidence
        else:
            raise gl.vm.UserError("role must be 'complainant' or 'respondent'")

        if len(bucket) >= MAX_EVIDENCE_PER_SIDE:
            raise gl.vm.UserError(
                f"at most {MAX_EVIDENCE_PER_SIDE} evidence items per side"
            )
        bucket.append(url)

    # ------------------------------------------------------------------
    # Adjudication
    # ------------------------------------------------------------------

    @gl.public.write
    def resolve_dispute(self, dispute_id: gl.u256) -> None:
        dispute = self._require_open(dispute_id)

        complainant_urls = list(dispute.complainant_evidence)
        respondent_urls = list(dispute.respondent_evidence)
        if not complainant_urls and not respondent_urls:
            raise gl.vm.UserError("at least one evidence item is required")

        # Copy to plain values before the non-deterministic block: the
        # closure runs once per validator and must not touch storage.
        dispute_type = dispute.dispute_type
        claim = dispute.claim_description
        remedy = dispute.requested_remedy
        rubric = RUBRICS[dispute_type]

        def adjudicate() -> str:
            complainant_evidence = _fetch_all(complainant_urls)
            respondent_evidence = _fetch_all(respondent_urls)

            prompt = f"""
You are an impartial adjudicator on a decentralized dispute-resolution
network. You judge disputes of type "{dispute_type}" between a complainant
and a respondent, regardless of which blockchain, payment rail, or platform
the underlying transaction happened on. Evidence has been independently
fetched from public sources for you.

DISPUTE TYPE GUIDANCE:
{rubric}

COMPLAINANT'S CLAIM:
{claim}

REQUESTED REMEDY:
{remedy}

COMPLAINANT'S EVIDENCE:
{json.dumps(complainant_evidence)}

RESPONDENT'S EVIDENCE:
{json.dumps(respondent_evidence)}

Each evidence item carries a "readable" flag. An item with "readable": false
could not actually be retrieved — it was unreachable, or the source served a
bot-protection page instead of its content. Such an item is NOT evidence: it
proves nothing for or against either party, and you must not treat it as
supporting the side that filed it. Say so plainly in your reasoning when a
party's case rests on a source that could not be read.

Weigh the evidence and decide:
1. recommended_action: one of "favor_complainant", "favor_respondent",
   "split", "warn", "constrain", "revoke", "escalate"
2. allocation_bps: integer 0-10000, how much of the disputed value/remedy
   should go to the complainant (10000 = fully to complainant, 0 = fully to
   respondent, 5000 = even split). Use 0 if recommended_action is a
   behavioral action (warn/constrain/revoke/escalate) with no financial
   component.
3. reasoning: one or two sentences.

If evidence is insufficient or contradictory, prefer "escalate". If neither
party has a readable source that speaks to the disputed facts, "escalate" is
the correct answer — do not infer a winner from an unread page.

Respond with ONLY this JSON, nothing else:
{{"recommended_action": "...", "allocation_bps": <int>, "reasoning": "..."}}
"""
            result = gl.nondet.exec_prompt(prompt, response_format="json")

            action = str(result.get("recommended_action", ""))
            if action not in VALID_ACTIONS:
                action = ACTION_ESCALATE
            allocation = _clamp_allocation(result.get("allocation_bps", 0))
            reasoning = str(result.get("reasoning", "")).strip()
            if not reasoning:
                reasoning = "No reasoning supplied by the adjudicating model."

            # Canonical JSON so independent validators produce comparable
            # strings rather than incidentally-different formatting.
            return json.dumps(
                {
                    "recommended_action": action,
                    "allocation_bps": allocation,
                    "reasoning": reasoning,
                },
                sort_keys=True,
            )

        raw = gl.eq_principle.prompt_comparative(adjudicate, EQUIVALENCE_PRINCIPLE)
        outcome = json.loads(raw)

        action = str(outcome.get("recommended_action", ACTION_ESCALATE))
        if action not in VALID_ACTIONS:
            action = ACTION_ESCALATE

        dispute.verdict_action = action
        dispute.verdict_allocation_bps = gl.u256(
            _clamp_allocation(outcome.get("allocation_bps", 0))
        )
        dispute.verdict_reasoning = str(outcome.get("reasoning", ""))
        dispute.status = STATUS_RESOLVED

    # ------------------------------------------------------------------
    # Reads — what an integrating application calls
    # ------------------------------------------------------------------

    @gl.public.view
    def get_verdict(self, dispute_id: gl.u256) -> dict:
        dispute = self.disputes.get(dispute_id, None)
        if dispute is None:
            return {
                "status": "",
                "recommended_action": "",
                "allocation_bps": 0,
                "reasoning": "",
            }
        return {
            "status": dispute.status,
            "recommended_action": dispute.verdict_action,
            "allocation_bps": dispute.verdict_allocation_bps,
            "reasoning": dispute.verdict_reasoning,
        }

    @gl.public.view
    def get_dispute(self, dispute_id: gl.u256) -> dict:
        dispute = self.disputes.get(dispute_id, None)
        if dispute is None:
            return {}
        return self._as_dict(dispute_id, dispute)

    @gl.public.view
    def list_disputes(self) -> list:
        return [
            self._as_dict(dispute_id, dispute)
            for dispute_id, dispute in self.disputes.items()
        ]

    @gl.public.view
    def dispute_count(self) -> gl.u256:
        return self.next_dispute_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_open(self, dispute_id: gl.u256) -> Dispute:
        dispute = self.disputes.get(dispute_id, None)
        if dispute is None:
            raise gl.vm.UserError("Dispute does not exist")
        if dispute.status != STATUS_OPEN:
            raise gl.vm.UserError("Dispute is not open")
        return dispute

    def _as_dict(self, dispute_id: gl.u256, dispute: Dispute) -> dict:
        return {
            "id": dispute_id,
            "dispute_type": dispute.dispute_type,
            "complainant_ref": dispute.complainant_ref,
            "respondent_ref": dispute.respondent_ref,
            "claim_description": dispute.claim_description,
            "requested_remedy": dispute.requested_remedy,
            "status": dispute.status,
            "complainant_evidence": list(dispute.complainant_evidence),
            "respondent_evidence": list(dispute.respondent_evidence),
            "verdict_action": dispute.verdict_action,
            "verdict_allocation_bps": dispute.verdict_allocation_bps,
            "verdict_reasoning": dispute.verdict_reasoning,
        }


def _fetch_all(urls: list) -> list:
    """Render each evidence URL, flagging any that could not actually be read.

    A single dead link must not sink the whole adjudication — the model is
    told explicitly which sources failed and weighs that itself. A source that
    returns a bot-protection page is reported as unreadable rather than passed
    through, so it cannot be mistaken for evidence that supports a party.
    """
    fetched = []
    for url in urls:
        try:
            rendered = gl.nondet.web.render(url, mode="text")
        except Exception:
            fetched.append(
                {
                    "url": url,
                    "readable": False,
                    "content": "(this URL could not be fetched)",
                }
            )
            continue

        reason = _unreadable_reason(rendered)
        if reason:
            fetched.append(
                {"url": url, "readable": False, "content": f"(unreadable: {reason})"}
            )
        else:
            fetched.append(
                {"url": url, "readable": True, "content": _truncate(rendered)}
            )
    return fetched
