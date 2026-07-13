#!/usr/bin/env python3
"""
generate_tables.py

Reads ../results/gas_benchmark.json (produced by
1_blockchain-identity/scripts/benchmark_gas.js) and emits thesis-ready
comparison tables:

  ../results/gas_comparison.csv  - machine-readable table
  ../results/gas_comparison.tex  - LaTeX booktabs tabular

Layout: STANDARDS AS ROWS, operations as columns (rotated when the benchmark
grew from 4 to 9 standards - 9 standard-columns no longer fit a thesis page).
For every operation, a relative-cost factor (x cheapest implemented standard
for that operation) is reported next to the raw gasUsed. Operations a
standard does not support are shown as an em dash.

Usage:
  python3 generate_tables.py [path/to/gas_benchmark.json]
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE.parent / "results"
DEFAULT_INPUT = RESULTS_DIR / "gas_benchmark.json"

NULL_DISPLAY = "—"  # em dash

OPERATION_LABELS = {
    "deployRegistry": "Deploy registry",
    "createIdentity": "Create identity",
    "updateAttribute": "Update key/attribute",
    "updateAttributeVia4337": "Update via 4337 EntryPoint",
    "addDelegateOrClaim": "Add delegate/claim",
    "revoke": "Revoke",
    "transferOwnership": "Transfer ownership",
}

# Compact column headers for the (rotated) LaTeX table.
OPERATION_SHORT_LABELS = {
    "deployRegistry": "Deploy",
    "createIdentity": "Create",
    "updateAttribute": "Update",
    "updateAttributeVia4337": "Update via EP",
    "addDelegateOrClaim": "Deleg./Claim",
    "revoke": "Revoke",
    "transferOwnership": "Transfer",
}

# LaTeX-safe labels for standards (hyphens are fine; escape specials if any).
def tex_escape(s: str) -> str:
    replacements = {
        "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(c, c) for c in s)


def load_benchmark(path: Path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    metadata = data.pop("metadata", {})
    standards = list(data.keys())
    operations = metadata.get("operations") or sorted(
        {op for std in data.values() for op in std}
    )
    return data, standards, operations, metadata


def relative_factors(data, standards, operation):
    """Return {standard: factor} where factor = gasUsed / min(gasUsed) per op."""
    values = {
        std: data[std][operation]["gasUsed"]
        for std in standards
        if operation in data[std] and data[std][operation]["gasUsed"] is not None
    }
    if not values:
        return {}
    cheapest = min(values.values())
    return {std: gas / cheapest for std, gas in values.items()}


def write_csv(data, standards, operations, metadata, out_path: Path):
    """Rotated layout: one row per standard, two columns (gas, rel.) per operation."""
    factors_by_op = {op: relative_factors(data, standards, op) for op in operations}
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["standard"]
        for op in operations:
            label = OPERATION_LABELS.get(op, op)
            header += [f"{label} gasUsed", f"{label} rel. cost (x cheapest)"]
        writer.writerow(header)

        for std in standards:
            row = [std]
            for op in operations:
                entry = data.get(std, {}).get(op)
                gas = entry["gasUsed"] if entry else None
                if gas is None:
                    row += [NULL_DISPLAY, NULL_DISPLAY]
                else:
                    row += [gas, f"{factors_by_op[op][std]:.2f}"]
            writer.writerow(row)

        writer.writerow([])
        writer.writerow([
            "Conditions",
            f"solc {metadata.get('solcVersion', '?')} (optimizer on, 200 runs, viaIR)",
            f"OpenZeppelin {metadata.get('ozVersion', '?')}",
            f"network {metadata.get('network', '?')}",
            f"measured {metadata.get('date', '?')}",
        ])
    print(f"Wrote {out_path}")


def write_tex(data, standards, operations, metadata, out_path: Path):
    date = metadata.get("date", "")
    try:
        date_h = datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(
            timezone.utc
        ).strftime("%Y-%m-%d")
    except ValueError:
        date_h = date or "n/a"

    caption = (
        "Gas cost comparison of blockchain vehicle-identity standards "
        "(rows: standards, columns: lifecycle operations). "
        "Each cell reports the measured \\texttt{gasUsed} of one representative "
        "transaction, with the relative cost versus the cheapest standard "
        "supporting that operation in parentheses. "
        f"Measured on a local Hardhat network (chain id {metadata.get('chainId', 31337)}) "
        f"with Solidity {metadata.get('solcVersion', '?')} "
        "(optimizer enabled, 200 runs, via-IR) and "
        f"OpenZeppelin Contracts {metadata.get('ozVersion', '?')}, {date_h}. "
        "``\\textemdash'' denotes an operation not supported by the standard; "
        "for ERC-725, ERC-735 and ERC-4337 the per-identity contract deployment "
        "is counted as identity creation. "
        "``Update via EP'' is the ERC-4337-only measurement of the same attribute "
        "update routed through the EntryPoint as a UserOperation (indirection "
        "overhead; bundler overhead excluded)."
    )

    factors_by_op = {op: relative_factors(data, standards, op) for op in operations}
    col_spec = "l" + "r" * len(operations)
    lines = [
        "% Auto-generated by generate_tables.py -- do not edit by hand.",
        "% Requires \\usepackage{booktabs}.",
        "\\begin{table}[htbp]",
        "  \\centering",
        f"  \\caption{{{caption}}}",
        "  \\label{tab:gas-comparison}",
        "  \\footnotesize",
        "  \\setlength{\\tabcolsep}{4pt}",
        "  \\resizebox{\\textwidth}{!}{%",
        f"  \\begin{{tabular}}{{{col_spec}}}",
        "    \\toprule",
        "    Standard & "
        + " & ".join(tex_escape(OPERATION_SHORT_LABELS.get(op, op)) for op in operations)
        + " \\\\",
        "    \\midrule",
    ]

    for std in standards:
        cells = []
        for op in operations:
            entry = data.get(std, {}).get(op)
            gas = entry["gasUsed"] if entry else None
            if gas is None:
                cells.append("\\textemdash")
            else:
                factor = factors_by_op[op][std]
                factor_str = (
                    "1.00$\\times$" if abs(factor - 1.0) < 1e-9
                    else f"{factor:.2f}$\\times$"
                )
                cells.append(f"{gas:,} ({factor_str})")
        lines.append(f"    {tex_escape(std)} & " + " & ".join(cells) + " \\\\")

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
            "Run the benchmark first:\n"
            "  cd 1_blockchain-identity && npx hardhat run scripts/benchmark_gas.js"
        )

    data, standards, operations, metadata = load_benchmark(input_path)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(data, standards, operations, metadata, RESULTS_DIR / "gas_comparison.csv")
    write_tex(data, standards, operations, metadata, RESULTS_DIR / "gas_comparison.tex")


if __name__ == "__main__":
    main()
