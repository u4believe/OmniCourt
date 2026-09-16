/**
 * Deploy an OmniCourt build to GenLayer Studio Next.
 *
 * The published GenLayer CLI (0.39.2) has no Studio Next preset — it only
 * knows Studio (chain 61999), so `genlayer deploy` signs for the wrong chain
 * and the RPC rejects it with InvalidChainId. This script builds the Studio
 * Next chain the same way the frontend does, from genlayer-js directly.
 *
 * Usage:
 *   DEPLOY_KEY_FILE=/path/to/key node deploy/deployStudioNext.mjs
 *
 * DEPLOY_KEY_FILE holds a hex private key and is never logged.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { createAccount, createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

import { isSuccessfulDeploymentReceipt } from "./receipt.mjs";

const RPC_URL = process.env.GENLAYER_RPC_URL ?? "https://studio-next.genlayer.com/api";
const CHAIN_ID = Number(process.env.GENLAYER_CHAIN_ID ?? 61997);
const CHAIN_NAME = process.env.GENLAYER_CHAIN_NAME ?? "GenLayer Studio Next";
const CONTRACT_PATH = process.env.CONTRACT_PATH ?? "contracts/omnicourt.py";
const KEY_FILE = process.env.DEPLOY_KEY_FILE;

if (!KEY_FILE) {
  console.error("DEPLOY_KEY_FILE is required (path to a hex private key file)");
  process.exit(1);
}

/** Studio Next shares Studio's Consensus v0.6 shape; only id/name/RPC differ. */
const chain = {
  ...studioDevnet,
  id: CHAIN_ID,
  name: CHAIN_NAME,
  nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
  rpcUrls: { default: { http: [RPC_URL] } },
};

/** Consensus v0.6 funds execution from the transaction itself, so a deploy
 *  with no fee value reverts with FeeValueMustBeNonZero. Quote the active
 *  policy rather than hardcoding a number that drifts with the network. */
const FEE_ESTIMATE_OPTIONS = {
  leaderTimeunitsAllocation: 100,
  validatorTimeunitsAllocation: 200,
  rotations: [1],
};

const account = createAccount(readFileSync(KEY_FILE, "utf8").trim());
const client = createClient({ chain, account });

console.log(`Deploying ${CONTRACT_PATH}`);
console.log(`  network : ${CHAIN_NAME} (chain ${CHAIN_ID})`);
console.log(`  rpc     : ${RPC_URL}`);
console.log(`  deployer: ${account.address}`);

const estimate = await client.estimateTransactionFees(FEE_ESTIMATE_OPTIONS);
const fees = { distribution: estimate.distribution, feeValue: estimate.feeValue };
console.log(`  fee     : ${estimate.feeValue} wei`);

const balance = await client.getBalance({ address: account.address });
console.log(`  balance : ${balance} wei`);
if (balance < BigInt(estimate.feeValue)) {
  console.error(
    `\nDeployer has ${balance} wei but the deploy needs ${estimate.feeValue} wei.` +
      `\nFund ${account.address} on ${CHAIN_NAME} and re-run.`,
  );
  process.exit(1);
}

const code = new Uint8Array(readFileSync(path.resolve(process.cwd(), CONTRACT_PATH)));
const hash = await client.deployContract({ code, args: [], fees });
console.log(`  tx      : ${hash}`);

const receipt = await client.waitForTransactionReceipt({
  hash,
  waitUntil: "decided",
  retries: 200,
});

if (!isSuccessfulDeploymentReceipt(receipt)) {
  console.error("Deployment failed. Receipt:");
  console.error(JSON.stringify(receipt, (_k, v) => (typeof v === "bigint" ? v.toString() : v), 2));
  process.exit(1);
}

const address =
  receipt?.txDataDecoded?.contractAddress ?? receipt?.data?.contract_address;

if (!address) {
  console.error("Receipt carried no contract address.");
  process.exit(1);
}

console.log(`\nContract deployed at address: ${address}`);
console.log(`Set NEXT_PUBLIC_CONTRACT_ADDRESS=${address} in frontend/.env`);
