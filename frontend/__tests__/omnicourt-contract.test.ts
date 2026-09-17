import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  readContract: vi.fn(),
  createClient: vi.fn(),
}));

vi.mock("genlayer-js", () => ({
  createClient: mocks.createClient.mockImplementation(() => ({
    readContract: mocks.readContract,
  })),
}));

import OmniCourt from "../lib/contracts/OmniCourt";

const ADDRESS = "0x2a98302C2252C05Bb05937C660138968e3ed9cdf";

/** The exact shape Studio Next returns for a resolved dispute. */
const RESOLVED_DISPUTE = {
  id: 0,
  dispute_type: "agent_agent",
  complainant_ref: "agent:0xaaa1-payer-bot",
  respondent_ref: "agent:0xbbb2-task-runner",
  claim_description: "Billed for a task it never completed.",
  requested_remedy: "Refund the task fee",
  status: "resolved",
  complainant_evidence: ["https://jsonplaceholder.typicode.com/todos/1"],
  respondent_evidence: ["https://jsonplaceholder.typicode.com/todos/4"],
  verdict_action: "favor_complainant",
  verdict_allocation_bps: 10000,
  verdict_reasoning: "The task record still shows completed=false.",
  resolution_rounds: 1,
};

describe("OmniCourt reads", () => {
  beforeEach(() => {
    mocks.readContract.mockReset();
    mocks.createClient.mockClear();
  });

  it("normalizes the plain-object shape the network returns", async () => {
    mocks.readContract.mockResolvedValue([RESOLVED_DISPUTE]);

    const [dispute] = await new OmniCourt(ADDRESS).getDisputes();

    expect(dispute.id).toBe(0);
    expect(dispute.dispute_type).toBe("agent_agent");
    expect(dispute.verdict_allocation_bps).toBe(10000);
    expect(dispute.complainant_evidence).toEqual([
      "https://jsonplaceholder.typicode.com/todos/1",
    ]);
  });

  it("normalizes Map-shaped decodings too", async () => {
    mocks.readContract.mockResolvedValue([new Map(Object.entries(RESOLVED_DISPUTE))]);

    const [dispute] = await new OmniCourt(ADDRESS).getDisputes();

    expect(dispute.verdict_action).toBe("favor_complainant");
    expect(dispute.respondent_evidence).toEqual([
      "https://jsonplaceholder.typicode.com/todos/4",
    ]);
  });

  it("carries the resolution round count through", async () => {
    mocks.readContract.mockResolvedValue([
      { ...RESOLVED_DISPUTE, resolution_rounds: 2n },
    ]);

    const [dispute] = await new OmniCourt(ADDRESS).getDisputes();

    expect(dispute.resolution_rounds).toBe(2);
  });

  it("coerces bigint allocations that would otherwise reach React", async () => {
    mocks.readContract.mockResolvedValue([
      { ...RESOLVED_DISPUTE, verdict_allocation_bps: 6000n, id: 2n },
    ]);

    const [dispute] = await new OmniCourt(ADDRESS).getDisputes();

    expect(dispute.verdict_allocation_bps).toBe(6000);
    expect(dispute.id).toBe(2);
  });

  it("lists the newest dispute first", async () => {
    mocks.readContract.mockResolvedValue([
      { ...RESOLVED_DISPUTE, id: 0 },
      { ...RESOLVED_DISPUTE, id: 1 },
      { ...RESOLVED_DISPUTE, id: 2 },
    ]);

    const disputes = await new OmniCourt(ADDRESS).getDisputes();

    expect(disputes.map((dispute) => dispute.id)).toEqual([2, 1, 0]);
  });

  it("returns null for an unknown dispute rather than an empty shell", async () => {
    mocks.readContract.mockResolvedValue({});

    expect(await new OmniCourt(ADDRESS).getDispute(99)).toBeNull();
  });

  it("reads back an empty verdict for an unresolved dispute", async () => {
    mocks.readContract.mockResolvedValue({
      status: "",
      recommended_action: "",
      allocation_bps: 0,
      reasoning: "",
    });

    expect(await new OmniCourt(ADDRESS).getVerdict(99)).toEqual({
      status: "",
      recommended_action: "",
      allocation_bps: 0,
      reasoning: "",
    });
  });
});
