/**
 * attackHarness.js
 *
 * Shared harness for the Thrust 5 security analysis of the CVIN vehicle-identity
 * standards. Mirrors the structure of scripts/benchmark_gas.js: instead of
 * recording the REAL gasUsed of a legitimate lifecycle operation, it EXECUTES a
 * concrete attack transaction against each standard's real contract on the
 * in-process Hardhat network and records the REAL observed outcome — never a
 * hard-coded verdict.
 *
 * Outcome model (one per (standard, attack) cell of the security matrix):
 *   "DEFENDED"   — the malicious transaction reverted (the contract's access
 *                  control / signature check / replay guard held).
 *   "VULNERABLE" — the malicious transaction was mined successfully (the attack
 *                  achieved its effect; a real finding to surface).
 *   "N/A"        — the attack is not applicable to this standard's identity
 *                  model (e.g. no gated issuance to bypass on a self-sovereign
 *                  registry, or no signed/relayed operation to replay).
 *
 * Differential rigor: most scenarios also run a CONTROL — the SAME operation
 * performed by the legitimately authorized party — and assert it SUCCEEDS. A
 * cell is only trustworthy as "DEFENDED" when (a) the attacker's call reverts
 * AND (b) the authorized call of the very same operation succeeds, proving the
 * revert is due to authorization/verification and not an unrelated malformed
 * call. Where relevant we also assert the protected state was not mutated.
 *
 * The accumulated matrix is written to
 *   ../../../4_comparison-framework/security-analysis/results/attack_results.json
 * by the after() hook in securityScenarios.test.js.
 */

const fs = require("fs");
const path = require("path");

// Ordered attack set (parallels the gas benchmark's lifecycle operation set:
// createIdentity, updateAttribute, addDelegateOrClaim, revoke, transferOwnership,
// plus the cross-cutting cryptographic replay attack).
const ATTACKS = [
  "unauthorizedIssuance", // attacker mints/registers an identity without the required role
  "unauthorizedAttributeWrite", // attacker rewrites a victim identity's attributes/keys/metadata
  "unauthorizedDelegateOrClaim", // attacker adds a delegate / anchors a (possibly forged) claim
  "unauthorizedRevocation", // attacker revokes/burns/deactivates a victim's identity or credential
  "identityHijack", // attacker seizes ownership/control of a victim's identity
  "signatureReplay", // attacker replays a consumed signed/relayed operation
];

const ATTACK_LABELS = {
  unauthorizedIssuance: "Unauthorized issuance",
  unauthorizedAttributeWrite: "Unauthorized attribute write",
  unauthorizedDelegateOrClaim: "Unauthorized delegate/claim",
  unauthorizedRevocation: "Unauthorized revocation",
  identityHijack: "Identity hijack",
  signatureReplay: "Signature replay",
};

// Accumulator: RESULTS[standard][attack] = { outcome, threat, attack, defense, revertReason, control }
const RESULTS = {};

function record(standard, attack, data) {
  if (!ATTACKS.includes(attack)) {
    throw new Error(`Unknown attack key: ${attack}`);
  }
  RESULTS[standard] = RESULTS[standard] || {};
  RESULTS[standard][attack] = data;
}

/** Best-effort human-readable revert reason from an ethers/hardhat error. */
function reasonOf(err) {
  if (!err) return null;
  return (
    err.shortMessage ||
    err.reason ||
    (err.info && err.info.error && err.info.error.message) ||
    (err.message ? String(err.message).split("\n")[0] : String(err))
  );
}

/**
 * Execute a malicious transaction and classify the outcome.
 * @param {() => Promise<any>} txThunk a thunk returning a tx-sending promise
 * @returns {Promise<{outcome: string, revertReason: string|null}>}
 */
async function attempt(txThunk) {
  try {
    const tx = await txThunk();
    if (tx && typeof tx.wait === "function") {
      await tx.wait();
    }
    return { outcome: "VULNERABLE", revertReason: null };
  } catch (err) {
    return { outcome: "DEFENDED", revertReason: reasonOf(err) };
  }
}

/**
 * Execute a legitimate control transaction (the authorized party performing the
 * same operation the attacker attempted) and classify it.
 * @returns {Promise<string>} "PASS" or "FAIL: <reason>"
 */
async function control(txThunk) {
  try {
    const tx = await txThunk();
    if (tx && typeof tx.wait === "function") {
      await tx.wait();
    }
    return "PASS";
  } catch (err) {
    return "FAIL: " + reasonOf(err);
  }
}

function naCell(standard, attack, threat, note) {
  record(standard, attack, {
    outcome: "N/A",
    threat,
    attack: note,
    defense: null,
    revertReason: null,
    control: null,
  });
}

/** Serialize the accumulated matrix to the comparison-framework results dir. */
function writeMatrix(metadata) {
  const output = { ...RESULTS, metadata: { ...metadata, attacks: ATTACKS } };
  const outDir = path.resolve(
    __dirname,
    "../../../4_comparison-framework/security-analysis/results"
  );
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "attack_results.json");
  fs.writeFileSync(outFile, JSON.stringify(output, null, 2));
  return outFile;
}

module.exports = {
  ATTACKS,
  ATTACK_LABELS,
  RESULTS,
  record,
  attempt,
  control,
  naCell,
  reasonOf,
  writeMatrix,
};
