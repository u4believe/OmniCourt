"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";

import OmniCourt from "../contracts/OmniCourt";
import type { Dispute, Verdict } from "../contracts/types";
import { getContractAddress } from "../genlayer/client";
import { useWallet } from "../genlayer/wallet";

/**
 * The OmniCourt registry instance, or null when no address is configured.
 *
 * Reads work without a connected wallet — anyone can audit the registry.
 */
export function useOmniCourtContract(): OmniCourt | null {
  const { address } = useWallet();
  const contractAddress = getContractAddress();

  return useMemo(() => {
    if (!contractAddress) return null;
    return new OmniCourt(contractAddress, address);
  }, [contractAddress, address]);
}

export function useDisputes() {
  const contract = useOmniCourtContract();

  return useQuery<Dispute[], Error>({
    queryKey: ["disputes"],
    queryFn: () => (contract ? contract.getDisputes() : Promise.resolve([])),
    refetchOnWindowFocus: true,
    staleTime: 2000,
    enabled: !!contract,
  });
}

export function useDispute(id: number | null) {
  const contract = useOmniCourtContract();

  return useQuery<Dispute | null, Error>({
    queryKey: ["dispute", id],
    queryFn: () =>
      contract && id !== null ? contract.getDispute(id) : Promise.resolve(null),
    enabled: !!contract && id !== null,
    staleTime: 2000,
  });
}

export function useVerdict(id: number | null) {
  const contract = useOmniCourtContract();

  return useQuery<Verdict | null, Error>({
    queryKey: ["verdict", id],
    queryFn: () =>
      contract && id !== null ? contract.getVerdict(id) : Promise.resolve(null),
    enabled: !!contract && id !== null,
    staleTime: 2000,
  });
}

export function useDisputeCount() {
  const contract = useOmniCourtContract();

  return useQuery<number, Error>({
    queryKey: ["disputeCount"],
    queryFn: () => (contract ? contract.getDisputeCount() : Promise.resolve(0)),
    refetchOnWindowFocus: true,
    staleTime: 2000,
    enabled: !!contract,
  });
}

/** Called after any write so the registry view reflects the new state. */
export function useInvalidateDisputes() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["disputes"] });
    queryClient.invalidateQueries({ queryKey: ["dispute"] });
    queryClient.invalidateQueries({ queryKey: ["verdict"] });
    queryClient.invalidateQueries({ queryKey: ["disputeCount"] });
  }, [queryClient]);
}
