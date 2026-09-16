/**
 * Whether a deployment receipt represents a decision we can build on.
 *
 * Only ACCEPTED (5) and FINALIZED (7) count. UNDETERMINED and the timeout
 * states must not be read as success: the contract address they carry may
 * never become canonical.
 */
export function isSuccessfulDeploymentReceipt(receipt) {
  const numericStatus = Number(receipt?.status);
  return (
    numericStatus === 5 ||
    numericStatus === 7 ||
    receipt?.statusName === "ACCEPTED" ||
    receipt?.statusName === "FINALIZED"
  );
}
