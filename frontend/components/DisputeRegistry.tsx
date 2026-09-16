"use client";

import { useMemo, useState } from "react";
import {
  AlertCircle,
  ExternalLink,
  FileSearch,
  Gavel,
  Loader2,
  Scale,
} from "lucide-react";
import {
  GenLayerTransactionPanel,
  type SubmitInput,
  type TrackedStatus,
} from "@genlayer/transaction-kit-react";

import { GENLAYER_NETWORK, getContractAddress } from "@/lib/genlayer/client";
import { useTransactionKit } from "@/lib/genlayer/kit";
import { useWallet } from "@/lib/genlayer/wallet";
import {
  useDisputes,
  useInvalidateDisputes,
  useOmniCourtContract,
} from "@/lib/hooks/useOmniCourt";
import {
  DISPUTE_TYPE_LABELS,
  type Dispute,
  type EvidenceRole,
} from "@/lib/contracts/types";
import { error, success } from "@/lib/utils/toast";
import { AllocationBar, VerdictBadge } from "./VerdictBadge";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

type EvidenceTarget = { disputeId: number; role: EvidenceRole };

export function DisputeRegistry() {
  const contract = useOmniCourtContract();
  const { data: disputes, isLoading, isError } = useDisputes();
  const { address } = useWallet();
  const kit = useTransactionKit(address);
  const invalidateDisputes = useInvalidateDisputes();
  const contractAddress = getContractAddress();

  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [evidenceTarget, setEvidenceTarget] = useState<EvidenceTarget | null>(null);
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [evidenceSubmitting, setEvidenceSubmitting] = useState(false);

  const resolveTx = useMemo<SubmitInput | null>(
    () =>
      resolvingId === null
        ? null
        : {
            kind: "write",
            address: contractAddress as `0x${string}`,
            method: "resolve_dispute",
            args: [resolvingId],
          },
    [contractAddress, resolvingId],
  );

  const evidenceTx = useMemo<SubmitInput | null>(
    () =>
      evidenceTarget && evidenceSubmitting
        ? {
            kind: "write",
            address: contractAddress as `0x${string}`,
            method: "submit_evidence",
            args: [evidenceTarget.disputeId, evidenceTarget.role, evidenceUrl.trim()],
          }
        : null,
    [contractAddress, evidenceTarget, evidenceSubmitting, evidenceUrl],
  );

  const requireWallet = (): boolean => {
    if (!address) {
      error("Connect your wallet first");
      return false;
    }
    if (!kit) {
      error("Transaction kit unavailable", {
        description: "Check your wallet connection and try again.",
      });
      return false;
    }
    if (!contractAddress) {
      error("Contract address not configured", {
        description: "Set NEXT_PUBLIC_CONTRACT_ADDRESS in frontend/.env.",
      });
      return false;
    }
    return true;
  };

  const closeEvidence = () => {
    setEvidenceTarget(null);
    setEvidenceUrl("");
    setEvidenceSubmitting(false);
  };

  const handleResolveDone = (status: TrackedStatus) => {
    if (status.successful !== false) {
      invalidateDisputes();
      success("Verdict recorded", {
        description: "Validators reached consensus on this dispute.",
      });
    } else {
      error("Adjudication did not succeed", {
        description: "The transaction completed without a successful outcome.",
      });
    }
    setResolvingId(null);
  };

  const handleEvidenceDone = (status: TrackedStatus) => {
    if (status.successful !== false) {
      invalidateDisputes();
      success("Evidence recorded");
    } else {
      error("Failed to record evidence");
    }
    closeEvidence();
  };

  if (isLoading) {
    return (
      <div className="brand-card p-8 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-accent" />
          <p className="text-sm text-muted-foreground">Loading the registry…</p>
        </div>
      </div>
    );
  }

  if (!contract) {
    return (
      <div className="brand-card p-12 text-center space-y-4">
        <AlertCircle className="w-16 h-16 mx-auto text-yellow-400 opacity-60" />
        <h3 className="text-xl font-bold">Setup required</h3>
        <p className="text-sm text-muted-foreground">
          Set{" "}
          <code className="bg-muted px-1 py-0.5 rounded text-xs">
            NEXT_PUBLIC_CONTRACT_ADDRESS
          </code>{" "}
          in <code className="bg-muted px-1 py-0.5 rounded text-xs">frontend/.env</code>.
        </p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="brand-card p-8 text-center">
        <p className="text-destructive">
          Could not read the registry. Please try again.
        </p>
      </div>
    );
  }

  if (!disputes || disputes.length === 0) {
    return (
      <div className="brand-card p-12 text-center space-y-3">
        <Scale className="w-16 h-16 mx-auto text-muted-foreground opacity-30" />
        <h3 className="text-xl font-bold">No disputes yet</h3>
        <p className="text-muted-foreground">
          File the first one — from any chain, or none at all.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        {disputes.map((dispute) => (
          <DisputeCard
            key={dispute.id}
            dispute={dispute}
            onAddEvidence={(role) => {
              if (!requireWallet()) return;
              setEvidenceTarget({ disputeId: dispute.id, role });
            }}
            onResolve={() => {
              if (!requireWallet()) return;
              setResolvingId(dispute.id);
            }}
          />
        ))}
      </div>

      <Dialog
        open={resolvingId !== null}
        onOpenChange={(open) => !open && setResolvingId(null)}
      >
        <DialogContent className="brand-card border-2 sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold">Send for adjudication</DialogTitle>
            <DialogDescription>
              Each validator independently re-fetches every evidence URL and reaches
              its own verdict. Review the fee quote and approve in your wallet.
            </DialogDescription>
          </DialogHeader>

          {kit && contractAddress && resolveTx && (
            <GenLayerTransactionPanel
              kit={kit}
              tx={resolveTx}
              network={GENLAYER_NETWORK.chainName}
              theme="dark"
              trackUntil="decided"
              onDone={handleResolveDone}
            />
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={evidenceTarget !== null} onOpenChange={(open) => !open && closeEvidence()}>
        <DialogContent className="brand-card border-2 sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold">Submit evidence</DialogTitle>
            <DialogDescription>
              Any public URL: a block explorer transaction, an API response, a
              tracking page, a hosted screenshot. Validators fetch it themselves.
            </DialogDescription>
          </DialogHeader>

          {!evidenceSubmitting ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="evidence-url">
                  Evidence URL ({evidenceTarget?.role})
                </Label>
                <Input
                  id="evidence-url"
                  value={evidenceUrl}
                  onChange={(e) => setEvidenceUrl(e.target.value)}
                  placeholder="https://etherscan.io/tx/0x…"
                />
              </div>
              <Button
                className="w-full"
                disabled={!evidenceUrl.trim().startsWith("http")}
                onClick={() => setEvidenceSubmitting(true)}
              >
                Review
              </Button>
            </div>
          ) : (
            kit &&
            contractAddress &&
            evidenceTx && (
              <GenLayerTransactionPanel
                kit={kit}
                tx={evidenceTx}
                network={GENLAYER_NETWORK.chainName}
                theme="dark"
                trackUntil="decided"
                onDone={handleEvidenceDone}
              />
            )
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function DisputeCard({
  dispute,
  onAddEvidence,
  onResolve,
}: {
  dispute: Dispute;
  onAddEvidence: (role: EvidenceRole) => void;
  onResolve: () => void;
}) {
  const isResolved = dispute.status === "resolved";
  const hasEvidence =
    dispute.complainant_evidence.length + dispute.respondent_evidence.length > 0;

  return (
    <div className="brand-card p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="secondary">#{dispute.id}</Badge>
            <Badge variant="outline">
              {DISPUTE_TYPE_LABELS[dispute.dispute_type] ?? dispute.dispute_type}
            </Badge>
            <Badge
              variant="outline"
              className={
                isResolved
                  ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-300 border-amber-500/30"
              }
            >
              {dispute.status}
            </Badge>
            {isResolved && <VerdictBadge action={dispute.verdict_action} />}
          </div>
          <p className="text-sm font-medium">{dispute.claim_description}</p>
          {dispute.requested_remedy && (
            <p className="text-xs text-muted-foreground">
              Requested remedy: {dispute.requested_remedy}
            </p>
          )}
        </div>

        {!isResolved && (
          <Button size="sm" onClick={onResolve} disabled={!hasEvidence} className="gap-2">
            <Gavel className="w-4 h-4" />
            Adjudicate
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <EvidenceColumn
          title="Complainant"
          partyRef={dispute.complainant_ref}
          urls={dispute.complainant_evidence}
          canAdd={!isResolved}
          onAdd={() => onAddEvidence("complainant")}
        />
        <EvidenceColumn
          title="Respondent"
          partyRef={dispute.respondent_ref}
          urls={dispute.respondent_evidence}
          canAdd={!isResolved}
          onAdd={() => onAddEvidence("respondent")}
        />
      </div>

      {isResolved && (
        <div className="rounded-lg border border-white/10 p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Scale className="w-4 h-4 text-accent" />
            Verdict
          </div>
          <p className="text-sm text-muted-foreground">{dispute.verdict_reasoning}</p>
          <AllocationBar
            action={dispute.verdict_action}
            allocationBps={dispute.verdict_allocation_bps}
          />
        </div>
      )}

      {!isResolved && !hasEvidence && (
        <p className="text-xs text-muted-foreground">
          Add at least one evidence URL before sending this for adjudication.
        </p>
      )}
    </div>
  );
}

function EvidenceColumn({
  title,
  partyRef,
  urls,
  canAdd,
  onAdd,
}: {
  title: string;
  partyRef: string;
  urls: string[];
  canAdd: boolean;
  onAdd: () => void;
}) {
  return (
    <div className="rounded-lg border border-white/10 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {title}
          </div>
          <div className="text-xs break-all">{partyRef || "—"}</div>
        </div>
        {canAdd && (
          <Button size="sm" variant="outline" onClick={onAdd} className="shrink-0">
            + Evidence
          </Button>
        )}
      </div>

      {urls.length === 0 ? (
        <p className="text-xs text-muted-foreground flex items-center gap-1">
          <FileSearch className="w-3 h-3" />
          No evidence filed
        </p>
      ) : (
        <ul className="space-y-1">
          {urls.map((url) => (
            <li key={url}>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-accent hover:underline break-all inline-flex items-start gap-1"
              >
                <ExternalLink className="w-3 h-3 mt-0.5 shrink-0" />
                {url}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
