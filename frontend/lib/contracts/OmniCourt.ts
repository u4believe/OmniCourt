import { createClient } from "genlayer-js";
import { GENLAYER_CHAIN } from "../genlayer/client";
import type { Dispute, DisputeType, Verdict } from "./types";

/**
 * Read access to a deployed OmniCourt registry.
 *
 * Writes go through Transaction Kit in the UI (so the user sees a fee quote
 * and signs in their wallet); this class covers the read side only.
 */
class OmniCourt {
  private contractAddress: `0x${string}`;
  private client: ReturnType<typeof createClient>;

  constructor(contractAddress: string, address?: string | null) {
    this.contractAddress = contractAddress as `0x${string}`;
    this.client = OmniCourt.makeClient(address);
  }

  private static makeClient(address?: string | null) {
    const config: Record<string, unknown> = { chain: GENLAYER_CHAIN };
    if (address) config.account = address as `0x${string}`;
    return createClient(config as never);
  }

  updateAccount(address: string): void {
    this.client = OmniCourt.makeClient(address);
  }

  async getDisputes(): Promise<Dispute[]> {
    const raw = await this.client.readContract({
      address: this.contractAddress,
      functionName: "list_disputes",
      args: [],
    });

    if (!Array.isArray(raw)) return [];
    // Newest first: a reviewer opening the app should see the dispute that
    // was just filed, not scroll to the bottom for it.
    return raw.map(toDispute).sort((a, b) => b.id - a.id);
  }

  async getDispute(id: number): Promise<Dispute | null> {
    const raw = await this.client.readContract({
      address: this.contractAddress,
      functionName: "get_dispute",
      args: [id],
    });
    const record = toRecord(raw);
    // An unknown id comes back as an empty mapping, not an error.
    if (!record || Object.keys(record).length === 0) return null;
    return toDispute(raw);
  }

  async getVerdict(id: number): Promise<Verdict> {
    const raw = await this.client.readContract({
      address: this.contractAddress,
      functionName: "get_verdict",
      args: [id],
    });
    const record = toRecord(raw) ?? {};
    return {
      status: asString(record.status) as Verdict["status"],
      recommended_action: asString(
        record.recommended_action,
      ) as Verdict["recommended_action"],
      allocation_bps: asNumber(record.allocation_bps),
      reasoning: asString(record.reasoning),
    };
  }

  async getDisputeCount(): Promise<number> {
    const count = await this.client.readContract({
      address: this.contractAddress,
      functionName: "dispute_count",
      args: [],
    });
    return asNumber(count);
  }
}

/**
 * GenLayer decodes contract dicts into `Map`s, so every read has to be
 * normalized before it reaches React.
 */
function toRecord(value: unknown): Record<string, unknown> | null {
  if (value instanceof Map) return Object.fromEntries(value.entries());
  if (value && typeof value === "object") return value as Record<string, unknown>;
  return null;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function asNumber(value: unknown): number {
  if (typeof value === "bigint") return Number(value);
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(asString);
}

function toDispute(raw: unknown): Dispute {
  const record = toRecord(raw) ?? {};
  return {
    id: asNumber(record.id),
    dispute_type: asString(record.dispute_type) as DisputeType,
    complainant_ref: asString(record.complainant_ref),
    respondent_ref: asString(record.respondent_ref),
    claim_description: asString(record.claim_description),
    requested_remedy: asString(record.requested_remedy),
    status: asString(record.status) as Dispute["status"],
    complainant_evidence: asStringList(record.complainant_evidence),
    respondent_evidence: asStringList(record.respondent_evidence),
    verdict_action: asString(record.verdict_action) as Dispute["verdict_action"],
    verdict_allocation_bps: asNumber(record.verdict_allocation_bps),
    verdict_reasoning: asString(record.verdict_reasoning),
  };
}

export default OmniCourt;
