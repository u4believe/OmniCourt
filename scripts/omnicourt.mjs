/**
 * Drive a deployed OmniCourt registry from the command line.
 *
 * Reads and writes go to the same contract the frontend uses, so this is
 * also the fastest way to reproduce a full cycle when reviewing:
 *
 *   node scripts/omnicourt.mjs count
 *   node scripts/omnicourt.mjs open person_person <complainant> <respondent> <claim> <remedy>
 *   node scripts/omnicourt.mjs evidence <id> complainant <url>
 *   node scripts/omnicourt.mjs resolve <id>
 *   node scripts/omnicourt.mjs verdict <id>
 *   node scripts/omnicourt.mjs dispute <id>
 *   node scripts/omnicourt.mjs list
 *
 * Writes need DEPLOY_KEY_FILE (a file holding a hex private key); reads
 * do not. The contract address comes from CONTRACT_ADDRESS or frontend/.env.
 */
import { readFileSync } from "node:fs";

import { createAccount, createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

const RPC_URL = process.env.GENLAYER_RPC_URL ?? "https://studio-next.genlayer.com/api";
const CHAIN_ID = Number(process.env.GENLAYER_CHAIN_ID ?? 61997);

const FEE_ESTIMATE_OPTIONS = {
  leaderTimeunitsAllocation: 100,
  validatorTimeunitsAllocation: 200,
  rotations: [1],
};

function contractAddress() {
  if (process.env.CONTRACT_ADDRESS) return process.env.CONTRACT_ADDRESS;
  try {
    const env = readFileSync(new URL("../frontend/.env", import.meta.url), "utf8");
    const match = env.match(/^NEXT_PUBLIC_CONTRACT_ADDRESS=(.+)$/m);
    if (match && match[1].startsWith("0x")) return match[1].trim();
  } catch {
    /* fall through to the error below */
  }
  throw new Error(
    "No contract address. Set CONTRACT_ADDRESS or NEXT_PUBLIC_CONTRACT_ADDRESS in frontend/.env",
  );
}

const chain = {
  ...studioDevnet,
  id: CHAIN_ID,
  name: "GenLayer Studio Next",
  nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
  rpcUrls: { default: { http: [RPC_URL] } },
};

function readClient() {
  return createClient({ chain });
}

function writeClient() {
  const keyFile = process.env.DEPLOY_KEY_FILE;
  if (!keyFile) throw new Error("DEPLOY_KEY_FILE is required for write commands");
  const account = createAccount(readFileSync(keyFile, "utf8").trim());
  return { client: createClient({ chain, account }), account };
}

const show = (value) =>
  console.log(
    JSON.stringify(value, (_k, v) => (typeof v === "bigint" ? v.toString() : v), 2),
  );

async function read(functionName, args = []) {
  return readClient().readContract({ address: contractAddress(), functionName, args });
}

async function write(functionName, args, { waitRetries = 200 } = {}) {
  const { client, account } = writeClient();
  const estimate = await client.estimateTransactionFees(FEE_ESTIMATE_OPTIONS);
  const hash = await client.writeContract({
    address: contractAddress(),
    functionName,
    args,
    account,
    fees: { distribution: estimate.distribution, feeValue: estimate.feeValue },
  });
  console.error(`  ${functionName} tx: ${hash}`);
  const receipt = await client.waitForTransactionReceipt({
    hash,
    waitUntil: "decided",
    retries: waitRetries,
  });
  console.error(`  status: ${receipt.statusName ?? receipt.status}`);
  return receipt;
}

const [command, ...args] = process.argv.slice(2);

switch (command) {
  case "count":
    show(await read("dispute_count"));
    break;
  case "list":
    show(await read("list_disputes"));
    break;
  case "dispute":
    show(await read("get_dispute", [Number(args[0])]));
    break;
  case "verdict":
    show(await read("get_verdict", [Number(args[0])]));
    break;
  case "open": {
    const [type, complainant, respondent, claim, remedy] = args;
    await write("open_dispute", [type, complainant, respondent, claim, remedy]);
    const id = Number(await read("dispute_count")) - 1;
    console.log(`Opened dispute ${id}`);
    break;
  }
  case "evidence":
    await write("submit_evidence", [Number(args[0]), args[1], args[2]]);
    console.log(`Evidence recorded for dispute ${args[0]}`);
    break;
  case "resolve":
    // Adjudication runs an LLM per validator, so it needs a longer wait.
    await write("resolve_dispute", [Number(args[0])], { waitRetries: 400 });
    show(await read("get_verdict", [Number(args[0])]));
    break;
  case "address":
    console.log(contractAddress());
    break;
  default:
    console.error("Unknown command. See the header of this file for usage.");
    process.exit(1);
}
