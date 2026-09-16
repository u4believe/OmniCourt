"use client";

import { Badge } from "./ui/badge";
import {
  VERDICT_ACTION_LABELS,
  isFinancialAction,
  type VerdictAction,
} from "@/lib/contracts/types";

/** Colour carries meaning: who the verdict favours, or that it was punted. */
const ACTION_STYLES: Record<Exclude<VerdictAction, "">, string> = {
  favor_complainant: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  favor_respondent: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  split: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  warn: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  constrain: "bg-orange-500/15 text-orange-300 border-orange-500/30",
  revoke: "bg-red-500/15 text-red-300 border-red-500/30",
  escalate: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

export function VerdictBadge({ action }: { action: VerdictAction }) {
  if (!action) return null;
  return (
    <Badge variant="outline" className={ACTION_STYLES[action]}>
      {VERDICT_ACTION_LABELS[action]}
    </Badge>
  );
}

/**
 * Renders the allocation as a share of the disputed value.
 *
 * Behavioural verdicts (warn/constrain/revoke/escalate) carry no financial
 * dimension, so showing "0% to complainant" there would be misleading.
 */
export function AllocationBar({
  action,
  allocationBps,
}: {
  action: VerdictAction;
  allocationBps: number;
}) {
  if (!isFinancialAction(action)) return null;

  const percent = Math.round((allocationBps / 10000) * 100);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Complainant {percent}%</span>
        <span>Respondent {100 - percent}%</span>
      </div>
      <div
        className="h-2 w-full rounded-full bg-sky-500/30 overflow-hidden"
        role="img"
        aria-label={`${percent}% of the disputed value to the complainant`}
      >
        <div
          className="h-full bg-emerald-400/80"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className="text-xs text-muted-foreground">
        allocation_bps: {allocationBps}
      </div>
    </div>
  );
}
