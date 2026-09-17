/**
 * TypeScript types for the OmniCourt dispute registry contract.
 */

export type DisputeType = "agent_agent" | "agent_person" | "person_person";

export type VerdictAction =
  | "favor_complainant"
  | "favor_respondent"
  | "split"
  | "warn"
  | "constrain"
  | "revoke"
  | "escalate"
  | "";

export type DisputeStatus = "open" | "resolved" | "";

export type EvidenceRole = "complainant" | "respondent";

export interface Dispute {
  id: number;
  dispute_type: DisputeType;
  complainant_ref: string;
  respondent_ref: string;
  claim_description: string;
  requested_remedy: string;
  status: DisputeStatus;
  complainant_evidence: string[];
  respondent_evidence: string[];
  verdict_action: VerdictAction;
  verdict_allocation_bps: number;
  verdict_reasoning: string;
  resolution_rounds: number;
}

/** Matches MAX_RESOLUTION_ROUNDS in contracts/omnicourt.py. */
export const MAX_RESOLUTION_ROUNDS = 3;

export interface Verdict {
  status: DisputeStatus;
  recommended_action: VerdictAction;
  allocation_bps: number;
  reasoning: string;
}

/** Human-readable labels for each relationship type the registry serves. */
export const DISPUTE_TYPE_LABELS: Record<DisputeType, string> = {
  agent_agent: "Agent ↔ Agent",
  agent_person: "Agent ↔ Person",
  person_person: "Person ↔ Person",
};

export const DISPUTE_TYPE_DESCRIPTIONS: Record<DisputeType, string> = {
  agent_agent:
    "Two AI agents transacting under a mandate. Did the respondent's output match what was promised?",
  agent_person:
    "An AI agent and a human. Did the agent perform the requested task to a reasonable standard?",
  person_person:
    "Two people in an ordinary commercial exchange, judged as a standard chargeback.",
};

export const VERDICT_ACTION_LABELS: Record<Exclude<VerdictAction, "">, string> = {
  favor_complainant: "Favor complainant",
  favor_respondent: "Favor respondent",
  split: "Split",
  warn: "Warn",
  constrain: "Constrain",
  revoke: "Revoke",
  escalate: "Escalate",
};

/**
 * Behavioural actions carry no financial allocation, so the UI hides the
 * basis-point split for them rather than showing a meaningless 0%.
 */
export const BEHAVIOURAL_ACTIONS: ReadonlySet<string> = new Set([
  "warn",
  "constrain",
  "revoke",
  "escalate",
]);

export function isFinancialAction(action: VerdictAction): boolean {
  return action !== "" && !BEHAVIOURAL_ACTIONS.has(action);
}
