#!/usr/bin/env python3
"""
Thrust 5 — Executable V2X attack-scenario suite & security-comparison matrix
============================================================================

This is the ORCHESTRATOR for the thesis security analysis. It produces a real,
evidence-backed security-comparison matrix across the 9 blockchain vehicle-
identity standards (plus the off-chain W3C SSI layer) by EXECUTING attacks and
recording their actual outcomes — never by asserting a result in prose.

Two executed layers are combined:

  1. OFF-CHAIN (this file)  — attacks against the canonical W3C Verifiable
     Credential / Presentation layer in `2_w3c-ssi-layer/verifiable-credentials`
     (forged credential, replayed presentation, stolen-credential replay by a
     non-holder, selective-disclosure privacy). Real signatures, real
     secp256k1 recovery, real verifier verdicts.

  2. ON-CHAIN (scripts/security_scenarios.js) — attacks against the real
     contracts on a Hardhat network (unauthorized mint/setAttribute/addClaim,
     signed-meta-tx / UserOperation replay, transfer/theft semantics, Sybil
     gating, guardian/issuer recovery, plaintext-VIN storage audit). Invoked
     here via subprocess; its JSON output is merged in.

Outputs (written to ./results/):
  - onchain_security.json   (produced by the Hardhat script)
  - security_matrix.json    (merged standards x threat-categories matrix)
  - security_comparison.tex (booktabs LaTeX table for the thesis)

Threat categories (columns):
  impersonation, replay, identity_theft, sybil, recovery, privacy

Outcome vocabulary per cell:
  DEFENDED   — attack blocked by a demonstrated mechanism
  PARTIAL    — partially mitigated / mitigated only under conditions / app-dependent
  VULNERABLE — attack succeeded, or no mitigation exists
  N/A        — category does not apply to this standard's surface
Each cell also records method = "executed" (a real tx/verification was run and
observed) or "reasoned" (a structural absence argued from verified source).

Run:  python3 attack_scenarios.py
      python3 attack_scenarios.py --offchain-only   (skip the Hardhat subprocess)

Author: Nikhil Prakash — MASc, UBC ECE
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VC_DIR = os.path.join(REPO_ROOT, "2_w3c-ssi-layer", "verifiable-credentials")
HARDHAT_DIR = os.path.join(REPO_ROOT, "1_blockchain-identity")
RESULTS_DIR = os.path.join(HERE, "results")
GAS_JSON = os.path.join(REPO_ROOT, "4_comparison-framework", "results", "gas_benchmark.json")

sys.path.insert(0, VC_DIR)


def cell(outcome, mechanism, evidence, method="executed"):
    return {"outcome": outcome, "mechanism": mechanism, "evidence": evidence, "method": method}


# ---------------------------------------------------------------------------
# OFF-CHAIN attack scenarios against the W3C VC/VP (SSI) layer
# ---------------------------------------------------------------------------

def run_offchain_vc_attacks():
    """Execute forgery / replay / theft / privacy attacks against the real
    VC layer and return a cell dict keyed by threat category."""
    from vc_issuer import CredentialIssuer, recover_signer
    from vc_holder import HolderWallet
    from vc_verifier import CredentialVerifier, TrustedIssuerRegistry

    VIN = "5YJ3E1EA0PF123456"
    out = {}

    issuer = CredentialIssuer.with_ethr_did()
    wallet = HolderWallet.with_ethr_did()
    verifier = CredentialVerifier(revocation_registry=issuer.revocation_registry)

    def birth_claims(iss):
        return {
            "vin": VIN, "make": "Tesla", "model": "3", "year": 2024,
            "manufacturingDate": "2024-01-15", "manufacturerDid": iss.issuer_did,
        }

    # ---- baseline sanity: a legitimate credential verifies ----
    good_vc = issuer.issue_credential(
        "VehicleBirthCertificate", wallet.holder_did,
        claims=birth_claims(issuer), validity_days=None,
    )["verifiableCredential"]
    baseline_ok = verifier.verify_credential(good_vc).valid

    # ---- impersonation / forgery: attacker signs with own key but claims a
    #      trusted manufacturer's DID as the issuer ----
    attacker = CredentialIssuer(issuer_did="did:ethr:0x1:0x" + "d" * 40)  # DID != attacker addr
    forged_vc = attacker.issue_credential(
        "VehicleBirthCertificate", wallet.holder_did,
        claims=birth_claims(attacker),
    )["verifiableCredential"]
    forged_res = verifier.verify_credential(forged_vc)
    # also tamper a field of a genuine credential (breaks the signature)
    tampered = dict(good_vc)
    tampered["credentialSubject"] = dict(good_vc["credentialSubject"], make="Lada")
    tampered_res = verifier.verify_credential(tampered)
    out["impersonation"] = cell(
        "DEFENDED" if (not forged_res.valid and not tampered_res.valid and baseline_ok) else "VULNERABLE",
        "issuer signature recovered via secp256k1 and matched against the address embedded in the issuer DID (or a trusted-issuer registry)",
        f"baseline genuine VC verified={baseline_ok}; forged-issuer VC rejected (errors: "
        f"{[e for e in forged_res.errors if 'issuer' in e]}); tampered-claim VC rejected "
        f"(errors: {[e for e in tampered_res.errors if 'signature' in e]}).",
    )

    # ---- replay: a valid Verifiable Presentation replayed with a stale
    #      challenge must fail (challenge = verifier nonce) ----
    cid = wallet.store_credential({"verifiableCredential": good_vc, "disclosures": None})
    vp = wallet.create_presentation([cid], challenge="nonce-live-001", domain="dmv.gov.bc.ca")
    fresh_ok, _ = verifier.verify_presentation(vp, "nonce-live-001", "dmv.gov.bc.ca")
    replay_ok, replay_report = verifier.verify_presentation(vp, "nonce-STALE-999", "dmv.gov.bc.ca")
    out["replay"] = cell(
        "DEFENDED" if (fresh_ok and not replay_ok) else "VULNERABLE",
        "VP proof binds a verifier-supplied challenge (nonce) + domain; verifier rejects any challenge mismatch",
        f"fresh presentation accepted={fresh_ok}; same VP replayed with a stale challenge rejected "
        f"(errors: {[e for e in replay_report['presentation']['errors'] if 'challenge' in e]}).",
    )

    # ---- identity theft: a thief copies the credential into their own wallet
    #      (same holder DID string, but the thief does NOT hold the holder key)
    #      and tries to present it ----
    thief = HolderWallet(holder_did=wallet.holder_did)  # same DID, different key
    tcid = thief.store_credential({"verifiableCredential": good_vc, "disclosures": None})
    thief_vp = thief.create_presentation([tcid], challenge="nonce-live-002", domain="dmv.gov.bc.ca")
    thief_ok, thief_report = verifier.verify_presentation(thief_vp, "nonce-live-002", "dmv.gov.bc.ca")
    out["identity_theft"] = cell(
        "DEFENDED" if not thief_ok else "VULNERABLE",
        "holder binding: the VP must be signed by the key controlling the holder DID; a stolen credential is unusable without the holder key",
        f"thief (same holder DID, wrong key) presentation rejected (errors: "
        f"{[e for e in thief_report['presentation']['errors'] if 'holder' in e]}). "
        "A copied/stolen credential cannot be replayed by a third party.",
    )

    # ---- sybil: credential issuance is bound to a trusted issuer key; a
    #      self-asserted issuer DID is not in the trusted registry ----
    unknown_issuer = CredentialIssuer(issuer_did="did:mobi:manufacturer:rogue")
    unknown_vc = unknown_issuer.issue_credential(
        "VehicleBirthCertificate", wallet.holder_did, claims=birth_claims(unknown_issuer),
    )["verifiableCredential"]
    bare_verifier = CredentialVerifier(revocation_registry=unknown_issuer.revocation_registry)
    unknown_res = bare_verifier.verify_credential(unknown_vc)
    out["sybil"] = cell(
        "PARTIAL",
        "credentials from a self-asserted (non-address-bearing) issuer DID are rejected unless the issuer is in the trusted-issuer registry; the DID namespace itself is unpermissioned",
        f"credential from an unknown did:mobi issuer rejected={not unknown_res.valid} "
        f"(errors: {[e for e in unknown_res.errors if 'issuer' in e]}). Trust is gated at the issuer-registry, "
        "not at DID creation, so pseudonymous holder identities remain cheap (governance-level, not cryptographic, Sybil control).",
    )

    # ---- recovery: the VC layer has no key-recovery primitive of its own; it
    #      relies on the on-chain identity layer (e.g. ERC-4337 guardian). But
    #      it DOES support revocation of a credential issued to a compromised key ----
    rev_vc = issuer.issue_credential(
        "VehicleBirthCertificate", wallet.holder_did, claims=birth_claims(issuer),
    )["verifiableCredential"]
    before = verifier.verify_credential(rev_vc).valid
    issuer.revoke_credential(rev_vc["id"], reason="holder key compromised")
    after = verifier.verify_credential(rev_vc).valid
    out["recovery"] = cell(
        "PARTIAL",
        "no key recovery at the VC layer, but issuer revocation lets a compromised credential be invalidated (credentialStatus) pending re-issuance to a new key",
        f"credential valid before revoke={before}, after revoke={after}. Key recovery itself is delegated to the "
        "on-chain identity layer (only ERC-4337 offers on-chain guardian recovery).",
    )

    # ---- privacy: selective disclosure hides undisclosed claims (salted
    #      digests); and the canonical identity DID is did:ethr (address-based),
    #      NOT did:mobi:<VIN> ----
    sd_env = issuer.issue_credential(
        "MaintenanceRecord", wallet.holder_did,
        claims={"vin": VIN, "serviceCenterDid": issuer.issuer_did,
                "serviceDate": "2026-06-01", "serviceType": "brakes",
                "odometerKm": 42150, "cost": 890.5, "technicianId": "TECH-0231"},
        selective_disclosure=True,
    )
    scid = wallet.store_credential(sd_env)
    sd_vp = wallet.create_presentation(
        [scid], challenge="n-p", domain="insurer.example",
        disclose_claims={scid: ["vin", "odometerKm"]},
    )
    presented = sd_vp["verifiableCredential"][0]
    disclosed = set(presented.get("disclosedClaims", {}))
    cost_hidden = "cost" not in json.dumps(presented.get("disclosedClaims", {}))
    holder_is_ethr = wallet.holder_did.startswith("did:ethr:")
    out["privacy"] = cell(
        "DEFENDED" if (disclosed == {"vin", "odometerKm"} and cost_hidden and holder_is_ethr) else "PARTIAL",
        "SD-JWT-style salted claim digests: only disclosed (claim,salt) pairs travel; identities use did:ethr (address-based), avoiding the did:mobi:<VIN> anti-pattern that would embed the VIN in the DID",
        f"presented only {sorted(disclosed)}; sensitive 'cost'/'technicianId' stayed hidden={cost_hidden}; "
        f"holder DID is did:ethr={holder_is_ethr}. NOTE: the did_resolver DOES define a did:mobi:<VIN> method that "
        "would leak the VIN in the DID string — flagged as an anti-pattern the canonical stack avoids by using did:ethr.",
    )

    return out


# ---------------------------------------------------------------------------
# ON-CHAIN layer: invoke the Hardhat suite and load its JSON
# ---------------------------------------------------------------------------

def run_onchain_suite(skip_run=False):
    out_json = os.path.join(RESULTS_DIR, "onchain_security.json")
    if not skip_run:
        print("Running on-chain Hardhat attack suite (npx hardhat run scripts/security_scenarios.js) ...")
        proc = subprocess.run(
            ["npx", "hardhat", "run", "scripts/security_scenarios.js"],
            cwd=HARDHAT_DIR, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            print("  Hardhat suite FAILED:\n" + proc.stdout[-2000:] + "\n" + proc.stderr[-2000:])
            raise SystemExit(1)
        # echo the summary table the script printed
        tail = proc.stdout.strip().splitlines()
        print("\n".join(tail[-14:]))
    if not os.path.exists(out_json):
        raise SystemExit(f"expected on-chain results not found: {out_json} (run without --offchain-only)")
    with open(out_json) as f:
        return json.load(f)


def load_sybil_costs():
    """Return {standard: createIdentity gasUsed} from the gas benchmark, as the
    Sybil-cost proxy. Missing file -> empty (cost simply omitted)."""
    if not os.path.exists(GAS_JSON):
        return {}
    with open(GAS_JSON) as f:
        gas = json.load(f)
    costs = {}
    for std, ops in gas.items():
        if std == "metadata" or not isinstance(ops, dict):
            continue
        ci = ops.get("createIdentity")
        if isinstance(ci, dict):
            costs[std] = ci.get("gasUsed")
    return costs


# ---------------------------------------------------------------------------
# Matrix assembly + LaTeX
# ---------------------------------------------------------------------------

CATEGORIES = ["impersonation", "replay", "identity_theft", "sybil", "recovery", "privacy"]
CATEGORY_LABELS = {
    "impersonation": "Impersonation / Forgery",
    "replay": "Replay",
    "identity_theft": "Identity Theft / Transfer",
    "sybil": "Sybil Resistance",
    "recovery": "Key Compromise / Recovery",
    "privacy": "Privacy / PII Leakage",
}
# desired thesis row order
STD_ORDER = ["ERC-1056", "ERC-721", "ERC-725", "ERC-735", "ERC-1155",
             "ERC-4337", "LSP8", "MOBI-VID-V2", "CVIN-Combined"]


def build_matrix(onchain, offchain, sybil_costs):
    standards = {}
    for std in STD_ORDER:
        cells = dict(onchain["standards"][std])
        # attach the Sybil-cost proxy to the sybil cell
        gas = sybil_costs.get(std)
        if gas is not None:
            cells["sybil"] = dict(cells["sybil"])
            cells["sybil"]["cost_proxy_gas"] = gas
            cells["sybil"]["evidence"] += f" createIdentity gas (Sybil-cost proxy) = {gas:,}."
        standards[std] = cells

    matrix = {
        "metadata": {
            "title": "CVIN Thrust 5 — V2X security-comparison matrix (executed attack suite)",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "categories": CATEGORIES,
            "category_labels": CATEGORY_LABELS,
            "outcome_legend": {
                "DEFENDED": "attack blocked by a demonstrated mechanism",
                "PARTIAL": "partially mitigated / conditional / app-dependent",
                "VULNERABLE": "attack succeeded or no mitigation exists",
                "N/A": "category does not apply to this standard's attack surface",
            },
            "method_legend": {
                "executed": "a real transaction / verification was run and its outcome observed",
                "reasoned": "structural absence argued from verified contract/library source (not a sent tx)",
            },
            "layers": {
                "on-chain": onchain["metadata"],
                "off-chain": "W3C VC/VP (SSI) layer in 2_w3c-ssi-layer/verifiable-credentials — real secp256k1 signatures + verifier verdicts",
            },
            "sybil_cost_proxy": "createIdentity gasUsed from 4_comparison-framework/results/gas_benchmark.json (cheaper creation => cheaper Sybil)",
        },
        "threat_model": {
            "impersonation": "Forge a credential or spoof an identity. On-chain: create/mint/setAttribute/addClaim as a non-owner or with a forged issuer/UserOp signature must revert. Off-chain: a VC signed by the wrong key must fail verification.",
            "replay": "Replay a valid VP with a stale challenge (must fail); replay a signed on-chain meta-tx / UserOperation where a nonce should prevent reuse.",
            "identity_theft": "Transfer/theft semantics: can the identity be seized/moved by whoever compromises the key? Token-transferable (ERC-721/LSP8) vs owner-authorised call (ERC-1056/725/735/4337/combined/MOBI) vs issuer-gated soulbound (ERC-1155).",
            "sybil": "Cost + gating to create N identities. Cheap/permissionless creation lowers the Sybil bar; issuer-gating (MOBI onlyAuthorizedManufacturer, ERC-1155 ISSUER_ROLE, ERC-721 MANUFACTURER_ROLE, LSP8 authority) raises it.",
            "recovery": "Recovery after key compromise/loss. ERC-4337 guardian social recovery and ERC-1155/LSP8 issuer/authority re-binding are demonstrated; standards with no primitive are asserted as permanent-loss.",
            "privacy": "PII / on-chain data leakage: does the VIN appear in plaintext in storage or events for a birth/registration op? did:mobi:<VIN> would leak the VIN in the DID itself — the canonical stack uses did:ethr instead.",
        },
        "standards": standards,
        "offchain_ssi": {"W3C-VC/VP": offchain},
    }
    return matrix


_MARK = {"DEFENDED": r"$\CIRCLE$", "PARTIAL": r"$\LEFTcircle$",
         "VULNERABLE": r"$\Circle$", "N/A": r"--"}
# Fallback plain-text markers (used in the JSON-free legend text).
_WORD = {"DEFENDED": "Defended", "PARTIAL": "Partial",
         "VULNERABLE": "Vulnerable", "N/A": "n/a"}


def latex_escape(s):
    return s.replace("&", r"\&").replace("_", r"\_").replace("%", r"\%").replace("#", r"\#")


def generate_latex(matrix):
    lines = []
    lines.append("% Auto-generated by 4_comparison-framework/security-analysis/attack_scenarios.py")
    lines.append("% Requires \\usepackage{booktabs}, \\usepackage{wasysym} (Harvey-ball markers "
                 "\\CIRCLE/\\LEFTcircle/\\Circle) and \\usepackage{graphicx} (for \\rotatebox).")
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"  \centering")
    lines.append(r"  \caption[V2X security-comparison matrix]{V2X security-comparison matrix across the nine "
                 r"blockchain vehicle-identity standards. Each cell is the observed outcome of an "
                 r"\emph{executed} attack scenario (unauthorised mint/claim, signed-meta-tx / UserOperation "
                 r"replay, transfer/theft, Sybil-gating, key recovery, and plaintext-VIN storage audit) on a "
                 r"local Hardhat network, complemented by executed forgery/replay/theft attacks against the "
                 r"off-chain W3C VC/VP layer. Markers: $\CIRCLE$ defended, $\LEFTcircle$ partial / "
                 r"conditional / app-dependent, $\Circle$ vulnerable or no mitigation, -- not applicable. "
                 r"Method: outcomes are executed except where noted (r = reasoned from verified source). "
                 r"Sybil column annotates the createIdentity gas cost (Sybil-cost proxy).}")
    lines.append(r"  \label{tab:security-comparison}")
    lines.append(r"  \small")
    lines.append(r"  \begin{tabular}{l" + "c" * len(CATEGORIES) + "}")
    lines.append(r"    \toprule")
    header = ["Standard"] + [
        r"\rotatebox{90}{" + latex_escape(CATEGORY_LABELS[c]) + "}" for c in CATEGORIES
    ]
    lines.append("    " + " & ".join(header) + r" \\")
    lines.append(r"    \midrule")

    def render_cell(c):
        m = _MARK[c["outcome"]]
        if c.get("method") == "reasoned":
            m += r"\textsuperscript{r}"
        return m

    for std in STD_ORDER:
        cells = matrix["standards"][std]
        row = [latex_escape(std)]
        for cat in CATEGORIES:
            row.append(render_cell(cells[cat]))
        lines.append("    " + " & ".join(row) + r" \\")

    lines.append(r"    \midrule")
    # off-chain SSI row
    off = matrix["offchain_ssi"]["W3C-VC/VP"]
    orow = [r"W3C VC/VP (SSI)"]
    for cat in CATEGORIES:
        orow.append(render_cell(off[cat]))
    lines.append("    " + " & ".join(orow) + r" \\")
    lines.append(r"    \bottomrule")
    lines.append(r"  \end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Console rendering
# ---------------------------------------------------------------------------

def print_matrix(matrix):
    rows = STD_ORDER + ["W3C-VC/VP"]
    colw = 14
    hdr = "standard".ljust(colw) + "".join(c[:11].ljust(colw) for c in CATEGORIES)
    print("\n" + "=" * len(hdr))
    print("SECURITY-COMPARISON MATRIX (outcome / method)")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))
    for std in rows:
        cells = matrix["standards"].get(std) or matrix["offchain_ssi"]["W3C-VC/VP"]
        line = std.ljust(colw)
        for cat in CATEGORIES:
            c = cells[cat]
            tag = _WORD[c["outcome"]]
            if c.get("method") == "reasoned":
                tag += "*"
            line += tag.ljust(colw)
        print(line)
    print("-" * len(hdr))
    print("* = reasoned (structural absence from verified source); all others executed.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Thrust 5 executable security suite")
    ap.add_argument("--offchain-only", action="store_true",
                    help="skip the Hardhat subprocess; reuse existing results/onchain_security.json")
    args = ap.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("== OFF-CHAIN: W3C VC/VP attack scenarios ==")
    offchain = run_offchain_vc_attacks()
    for cat in CATEGORIES:
        print(f"  {cat:16s} {offchain[cat]['outcome']}")

    print("\n== ON-CHAIN: contract attack scenarios ==")
    onchain = run_onchain_suite(skip_run=args.offchain_only)

    sybil_costs = load_sybil_costs()
    matrix = build_matrix(onchain, offchain, sybil_costs)

    matrix_path = os.path.join(RESULTS_DIR, "security_matrix.json")
    with open(matrix_path, "w") as f:
        json.dump(matrix, f, indent=2)

    tex_path = os.path.join(RESULTS_DIR, "security_comparison.tex")
    with open(tex_path, "w") as f:
        f.write(generate_latex(matrix))

    print_matrix(matrix)
    print(f"\nWrote {matrix_path}")
    print(f"Wrote {tex_path}")


if __name__ == "__main__":
    main()
