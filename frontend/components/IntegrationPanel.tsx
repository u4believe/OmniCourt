"use client";

import { useState } from "react";
import { Check, Copy, Plug } from "lucide-react";

import { getContractAddress } from "@/lib/genlayer/client";
import { Button } from "./ui/button";

/**
 * The "other projects can call into this" panel.
 *
 * OmniCourt is a judgment layer, not an enforcement layer, so the thing an
 * integrating application actually needs is this one read call — which is
 * exactly what this panel shows, against the live address.
 */
export function IntegrationPanel() {
  const contractAddress = getContractAddress() || "0x…";
  const [copied, setCopied] = useState<string | null>(null);

  const snippets: { id: string; label: string; code: string }[] = [
    {
      id: "read",
      label: "Read a verdict (any app, any chain)",
      code: `import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

const chain = {
  ...studioDevnet,
  id: 61997,
  rpcUrls: { default: { http: ["https://studio-next.genlayer.com/api"] } },
};

const client = createClient({ chain });

const verdict = await client.readContract({
  address: "${contractAddress}",
  functionName: "get_verdict",
  args: [disputeId],
});

// => { status, recommended_action, allocation_bps, reasoning }
// Enforce it however your domain requires: release escrow, refund,
// revoke an agent's permission, flag reputation.`,
    },
    {
      id: "open",
      label: "Open a dispute from your own app",
      code: `await client.writeContract({
  address: "${contractAddress}",
  functionName: "open_dispute",
  args: [
    "agent_agent",             // or agent_person / person_person
    "agent:0xaaa1-payer",      // complainant, any reference
    "agent:0xbbb2-provider",   // respondent, any reference
    "Billed for a call that returned no payload.",
    "Refund and constrain billing authority",
  ],
  fees,
});`,
    },
    {
      id: "evidence",
      label: "Attach evidence from any network",
      code: `// Evidence is any public URL — validators re-fetch it themselves.
// That is what makes OmniCourt network-agnostic: no bridging, no
// reading foreign chain state.
//
// Prefer an endpoint an automated request can actually read. Most
// explorer HTML sits behind bot protection and comes back as a
// challenge page, which the contract flags as unreadable rather than
// letting it pass as evidence.
await client.writeContract({
  address: "${contractAddress}",
  functionName: "submit_evidence",
  args: [
    disputeId,
    "complainant",
    "https://eth.blockscout.com/api/v2/transactions/0x…",
  ],
  fees,
});`,
    },
  ];

  const copy = async (id: string, code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(id);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard unavailable — the code is on screen anyway */
    }
  };

  return (
    <div className="brand-card p-6 md:p-8 space-y-5">
      <div className="flex items-center gap-2">
        <Plug className="w-5 h-5 text-accent" />
        <h2 className="text-2xl font-bold">How another app integrates</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        OmniCourt is one permanently deployed registry at a fixed address —
        integrate against it the way you would a fixed API endpoint. It returns a
        verdict; your application enforces it in its own domain.
      </p>

      <div className="rounded-lg border border-white/10 p-3 flex items-center justify-between gap-3 flex-wrap">
        <div className="text-xs">
          <span className="text-muted-foreground">Contract: </span>
          <code className="break-all">{contractAddress}</code>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => copy("address", contractAddress)}
          className="gap-1 shrink-0"
        >
          {copied === "address" ? (
            <Check className="w-3 h-3" />
          ) : (
            <Copy className="w-3 h-3" />
          )}
          Copy
        </Button>
      </div>

      <div className="space-y-4">
        {snippets.map((snippet) => (
          <div key={snippet.id} className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">{snippet.label}</h3>
              <Button
                size="sm"
                variant="outline"
                onClick={() => copy(snippet.id, snippet.code)}
                className="gap-1"
              >
                {copied === snippet.id ? (
                  <Check className="w-3 h-3" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
                Copy
              </Button>
            </div>
            <pre className="rounded-lg border border-white/10 bg-black/30 p-3 overflow-x-auto text-xs leading-relaxed">
              <code>{snippet.code}</code>
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
