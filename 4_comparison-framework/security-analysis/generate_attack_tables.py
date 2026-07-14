#!/usr/bin/env python3
"""
generate_attack_tables.py

Reads ./results/attack_results.json (produced by
1_blockchain-identity/test/security/securityScenarios.test.js) and emits
thesis-ready security tables:

  ./results/attack_results.csv  - machine-readable outcome matrix
  ./results/attack_results.tex  - LaTeX booktabs tabular

Layout mirrors the gas-comparison table: STANDARDS AS ROWS, attack scenarios as
columns. Each cell is the REAL observed attack outcome recorded on-chain:
  DEFENDED   - the malicious transaction reverted (defense held)
  VULNERABLE - the malicious transaction succeeded (a finding)
  N/A        - the attack does not apply to the standard's identity model
A "Defended" summary column reports defended / applicable per standard.

Usage:
  python3 generate_attack_tables.py [path/to/attack_results.json]
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
DEFAULT_INPUT = RESULTS_DIR / "attack_results.json"

# CSV / plain-text cell rendering.
OUTCOME_DISPLAY = {
    "DEFENDED": "DEFENDED",
    "VULNERABLE": "VULNERABLE",
    "N/A": "—",  # em dash, matching the gas table's unsupported marker
}

# LaTeX cell rendering (checkmark = defended, cross = vulnerable, dash = n/a).
OUTCOME_TEX = {
    "DEFENDED": r"\checkmark",
    "VULNERABLE": r"\times",
    "N/A": r"\textemdash",
}

ATTACK_LABELS = {
    "unauthorizedIssuance": "Unauthorized issuance",
    "unauthorizedAttributeWrite": "Unauthorized attribute write",
    "unauthorizedDelegateOrClaim": "Unauthorized delegate/claim",
    "unauthorizedRevocation": "Unauthorized revocation",
    "identityHijack": "Identity hijack",
    "signatureReplay": "Signature replay",
}

ATTACK_SHORT_LABELS = {
    "unauthorizedIssuance": "Issuance",
    "unauthorizedAttributeWrite": "Attr. write",
    "unauthorizedDelegateOrClaim": "Deleg./Claim",
    "unauthorizedRevocation": "Revocation",
    "identityHijack": "Hijack",
    "signatureReplay": "Replay",
}


def tex_escape(s: str) -> str:
    replacements = {
        "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(c, c) for c in s)


def load_matrix(path: Path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    metadata = data.pop("metadata", {})
    standards = list(data.keys())
    attacks = metadata.get("attacks") or sorted(
        {a for std in data.values() for a in std}
    )
    return data, standards, attacks, metadata


def outcome_of(data, std, attack):
    cell = data.get(std, {}).get(attack)
    return cell.get("outcome") if cell else "N/A"


def defense_summary(data, std, attacks):
    """Return (defended, applicable) counts for a standard."""
    applicable = 0
    defended = 0
    for a in attacks:
        o = outcome_of(data, std, a)
        if o == "N/A":
            continue
        applicable += 1
        if o == "DEFENDED":
            defended += 1
    return defended, applicable


def write_csv(data, standards, attacks, metadata, out_path: Path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["standard"] + [ATTACK_LABELS.get(a, a) for a in attacks] + [
            "Defended (of applicable)"
        ]
        writer.writerow(header)

        for std in standards:
            row = [std]
            for a in attacks:
                row.append(OUTCOME_DISPLAY.get(outcome_of(data, std, a), outcome_of(data, std, a)))
            defended, applicable = defense_summary(data, std, attacks)
            row.append(f"{defended}/{applicable}")
            writer.writerow(row)

        # Per-attack totals row.
        totals = ["TOTAL defended/applicable"]
        for a in attacks:
            d = sum(1 for s in standards if outcome_of(data, s, a) == "DEFENDED")
            n = sum(1 for s in standards if outcome_of(data, s, a) != "N/A")
            totals.append(f"{d}/{n}")
        grand_def = sum(defense_summary(data, s, attacks)[0] for s in standards)
        grand_app = sum(defense_summary(data, s, attacks)[1] for s in standards)
        totals.append(f"{grand_def}/{grand_app}")
        writer.writerow(totals)

        writer.writerow([])
        writer.writerow([
            "Legend",
            "DEFENDED = malicious tx reverted",
            "VULNERABLE = malicious tx mined",
            "— = attack N/A to this standard's model",
        ])
        writer.writerow([
            "Conditions",
            f"solc {metadata.get('solcVersion', '?')} (optimizer on, 200 runs, viaIR)",
            f"OpenZeppelin {metadata.get('ozVersion', '?')}",
            f"network {metadata.get('network', '?')}",
            f"measured {metadata.get('date', '?')}",
        ])
    print(f"Wrote {out_path}")


def write_tex(data, standards, attacks, metadata, out_path: Path):
    date = metadata.get("date", "")
    try:
        date_h = datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(
            timezone.utc
        ).strftime("%Y-%m-%d")
    except ValueError:
        date_h = date or "n/a"

    caption = (
        "Security outcome matrix of blockchain vehicle-identity standards "
        "(rows: standards, columns: attack scenarios). "
        "Each cell is the real observed outcome of executing a concrete "
        "adversarial transaction against the deployed contract: "
        "\\checkmark{} = DEFENDED (the malicious transaction reverted), "
        "$\\times$ = VULNERABLE (it was mined), "
        "\\textemdash{} = attack not applicable to the standard's identity model. "
        "The final column reports defended attacks out of those applicable. "
        f"Measured on a local Hardhat network (chain id {metadata.get('chainId', 31337)}) "
        f"with Solidity {metadata.get('solcVersion', '?')} "
        "(optimizer enabled, 200 runs, via-IR) and "
        f"OpenZeppelin Contracts {metadata.get('ozVersion', '?')}, {date_h}. "
        "Attack scenarios parallel the gas benchmark's lifecycle operation set "
        "(create / update / delegate-or-claim / revoke / transfer) plus a "
        "cross-cutting signature-replay attack; each cell is backed by a "
        "differential control that confirms the same operation succeeds for the "
        "authorized party."
    )

    col_spec = "l" + "c" * len(attacks) + "c"
    lines = [
        "% Auto-generated by generate_attack_tables.py -- do not edit by hand.",
        "% Requires \\usepackage{booktabs} and \\usepackage{amssymb} (\\checkmark, \\times).",
        "\\begin{table}[htbp]",
        "  \\centering",
        f"  \\caption{{{caption}}}",
        "  \\label{tab:security-matrix}",
        "  \\footnotesize",
        "  \\setlength{\\tabcolsep}{4pt}",
        "  \\resizebox{\\textwidth}{!}{%",
        f"  \\begin{{tabular}}{{{col_spec}}}",
        "    \\toprule",
        "    Standard & "
        + " & ".join(tex_escape(ATTACK_SHORT_LABELS.get(a, a)) for a in attacks)
        + " & Defended \\\\",
        "    \\midrule",
    ]

    for std in standards:
        cells = []
        for a in attacks:
            o = outcome_of(data, std, a)
            tex = OUTCOME_TEX.get(o, tex_escape(o))
            # Wrap math-mode symbols.
            if tex in (r"\checkmark", r"\times"):
                cells.append(f"${tex}$")
            else:
                cells.append(tex)
        defended, applicable = defense_summary(data, std, attacks)
        lines.append(
            f"    {tex_escape(std)} & " + " & ".join(cells) + f" & {defended}/{applicable} \\\\"
        )

    lines += [
        "    \\bottomrule",
        "  \\end{tabular}}",
        "\\end{table}",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if not input_path.exists():
        sys.exit(
            f"Input not found: {input_path}\n"
            "Run the security scenarios first:\n"
            "  cd 1_blockchain-identity && npx hardhat test test/security/securityScenarios.test.js"
        )

    data, standards, attacks, metadata = load_matrix(input_path)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(data, standards, attacks, metadata, RESULTS_DIR / "attack_results.csv")
    write_tex(data, standards, attacks, metadata, RESULTS_DIR / "attack_results.tex")


if __name__ == "__main__":
    main()
