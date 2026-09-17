"use client";

import { useEffect, useMemo, useState } from "react";
import { Gavel, ArrowLeft } from "lucide-react";
import {
  GenLayerTransactionPanel,
  type SubmitInput,
  type TrackedStatus,
} from "@genlayer/transaction-kit-react";

import { GENLAYER_NETWORK, getContractAddress } from "@/lib/genlayer/client";
import { useTransactionKit } from "@/lib/genlayer/kit";
import { useWallet } from "@/lib/genlayer/wallet";
import { useInvalidateDisputes } from "@/lib/hooks/useOmniCourt";
import {
  DISPUTE_TYPE_DESCRIPTIONS,
  DISPUTE_TYPE_LABELS,
  type DisputeType,
} from "@/lib/contracts/types";
import { afterRender } from "@/lib/utils/afterRender";
import { error, success } from "@/lib/utils/toast";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

const DISPUTE_TYPES: DisputeType[] = [
  "person_person",
  "agent_person",
  "agent_agent",
];

export function OpenDisputeModal() {
  const { isConnected, address, isLoading } = useWallet();
  const kit = useTransactionKit(address);
  const invalidateDisputes = useInvalidateDisputes();
  const contractAddress = getContractAddress();

  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState<"form" | "review">("form");
  const [disputeType, setDisputeType] = useState<DisputeType>("person_person");
  const [complainantRef, setComplainantRef] = useState("");
  const [respondentRef, setRespondentRef] = useState("");
  const [claim, setClaim] = useState("");
  const [remedy, setRemedy] = useState("");
  const [errors, setErrors] = useState({ claim: "", complainantRef: "" });

  // Stable tx identity: the transaction flow re-estimates (and resets) when
  // this object's reference changes, so it must not be rebuilt on unrelated
  // re-renders while the panel is mounted.
  const openDisputeTx = useMemo<SubmitInput>(
    () => ({
      kind: "write",
      address: contractAddress as `0x${string}`,
      method: "open_dispute",
      args: [disputeType, complainantRef, respondentRef, claim, remedy],
    }),
    [contractAddress, disputeType, complainantRef, respondentRef, claim, remedy],
  );

  useEffect(() => {
    if (!isConnected && isOpen && step === "form") setIsOpen(false);
  }, [isConnected, isOpen, step]);

  const resetForm = () => {
    setStep("form");
    setDisputeType("person_person");
    setComplainantRef("");
    setRespondentRef("");
    setClaim("");
    setRemedy("");
    setErrors({ claim: "", complainantRef: "" });
  };

  const validate = (): boolean => {
    const next = {
      claim: claim.trim() ? "" : "Describe what went wrong",
      complainantRef: complainantRef.trim()
        ? ""
        : "Identify the complainant (any reference works)",
    };
    setErrors(next);
    return !next.claim && !next.complainantRef;
  };

  const handleReview = () => {
    if (!contractAddress) {
      error("Contract address not configured", {
        description: "Set NEXT_PUBLIC_CONTRACT_ADDRESS in frontend/.env.",
      });
      return;
    }
    if (!kit) {
      error("Transaction kit unavailable", {
        description: "Check your wallet connection and try again.",
      });
      return;
    }
    if (validate()) setStep("review");
  };

  const handleDone = (status: TrackedStatus) => {
    afterRender(() => {
      if (status.successful !== false) {
        invalidateDisputes();
        success("Dispute filed", {
          description: "Add evidence, then send it for adjudication.",
        });
        setIsOpen(false);
        resetForm();
        return;
      }
      error("Failed to file dispute", {
        description: "The transaction completed without a successful outcome.",
      });
    });
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open);
        if (!open) resetForm();
      }}
    >
      <DialogTrigger asChild>
        <Button disabled={!isConnected || isLoading} className="gap-2">
          <Gavel className="w-4 h-4" />
          File a dispute
        </Button>
      </DialogTrigger>

      <DialogContent className="brand-card border-2 sm:max-w-[560px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold">
            {step === "form" ? "File a dispute" : "Review and submit"}
          </DialogTitle>
          <DialogDescription>
            {step === "form"
              ? "OmniCourt adjudicates disputes from any chain, or none at all."
              : "Review the fee quote and approve the transaction in your wallet."}
          </DialogDescription>
        </DialogHeader>

        {step === "form" ? (
          <div className="space-y-4 mt-2">
            <div className="space-y-2">
              <Label>Relationship type</Label>
              <div className="grid gap-2">
                {DISPUTE_TYPES.map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setDisputeType(type)}
                    className={`text-left rounded-lg border p-3 transition-colors ${
                      disputeType === type
                        ? "border-accent bg-accent/10"
                        : "border-white/10 hover:border-white/25"
                    }`}
                  >
                    <div className="font-semibold text-sm">
                      {DISPUTE_TYPE_LABELS[type]}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {DISPUTE_TYPE_DESCRIPTIONS[type]}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="complainant">Complainant reference</Label>
              <Input
                id="complainant"
                value={complainantRef}
                onChange={(e) => setComplainantRef(e.target.value)}
                placeholder="buyer:alice@example.com, or a wallet on any chain"
              />
              {errors.complainantRef && (
                <p className="text-xs text-destructive">{errors.complainantRef}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="respondent">Respondent reference</Label>
              <Input
                id="respondent"
                value={respondentRef}
                onChange={(e) => setRespondentRef(e.target.value)}
                placeholder="agent:0xfeed..., a Solana address, an email"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="claim">What went wrong?</Label>
              <textarea
                id="claim"
                value={claim}
                onChange={(e) => setClaim(e.target.value)}
                rows={3}
                placeholder="Paid for a laptop on 2026-09-01. It never arrived."
                className="w-full rounded-md border border-white/10 bg-transparent px-3 py-2 text-sm outline-none focus:border-accent"
              />
              {errors.claim && (
                <p className="text-xs text-destructive">{errors.claim}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="remedy">Requested remedy</Label>
              <Input
                id="remedy"
                value={remedy}
                onChange={(e) => setRemedy(e.target.value)}
                placeholder="Full refund of 950 USDC"
              />
            </div>

            <Button onClick={handleReview} className="w-full">
              Review
            </Button>
          </div>
        ) : (
          <div className="space-y-4 mt-2">
            <div className="rounded-lg border border-white/10 p-3 text-sm space-y-1">
              <div>
                <span className="text-muted-foreground">Type: </span>
                {DISPUTE_TYPE_LABELS[disputeType]}
              </div>
              <div>
                <span className="text-muted-foreground">Complainant: </span>
                {complainantRef}
              </div>
              <div>
                <span className="text-muted-foreground">Respondent: </span>
                {respondentRef || "—"}
              </div>
              <div>
                <span className="text-muted-foreground">Claim: </span>
                {claim}
              </div>
              <div>
                <span className="text-muted-foreground">Remedy: </span>
                {remedy || "—"}
              </div>
            </div>

            {kit && contractAddress && (
              <GenLayerTransactionPanel
                kit={kit}
                tx={openDisputeTx}
                network={GENLAYER_NETWORK.chainName}
                theme="dark"
                trackUntil="decided"
                onDone={handleDone}
              />
            )}

            <Button
              variant="outline"
              onClick={() => setStep("form")}
              className="w-full gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
