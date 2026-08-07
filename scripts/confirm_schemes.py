"""
Interactive scheme confirmation — the actual human checkpoint.

lookup_schemes.py's candidates are ranked by text similarity, which
Session 6 proved isn't good enough on its own: "Quant Tax Plan" auto-
matched "Quantum ELSS Tax Saver Fund" (a different AMC entirely), and
6 similar near-miss mismatches also made it into the database before
anyone actually looked. Text similarity can't tell "Nifty 50" from
"Nifty Next 50" apart as well as a human glancing at the name can.

This script walks through resolved_schemes.json one fund at a time,
shows you the real candidates, and makes you actually pick — no
auto-accept, no silent trust of whichever came out on top.

Usage:
    python scripts/confirm_schemes.py

Safe to stop partway (Ctrl+C) and resume later — it saves after every
single confirmation, not just at the end.
"""

from __future__ import annotations

import json
from pathlib import Path

RESOLVED_SCHEMES_PATH = Path(__file__).parent / "resolved_schemes.json"


def load() -> list[dict]:
    return json.loads(RESOLVED_SCHEMES_PATH.read_text())


def save(entries: list[dict]) -> None:
    RESOLVED_SCHEMES_PATH.write_text(json.dumps(entries, indent=2))


def prompt_for_entry(entry: dict) -> str | None:
    """Show one fund's candidates and get a human decision.
    Returns the confirmed scheme_code, or None to skip for now."""
    print(f"\n{'=' * 70}")
    print(f"Category: {entry['category']}  |  Expected AMC: {entry['amc']}")
    print(f"Search term was: {entry['search_term']!r}")

    if not entry["candidates"]:
        print("  (no candidates at all — needs manual lookup on tigzig.com)")
        return None

    for i, c in enumerate(entry["candidates"], start=1):
        print(f"  [{i}] {c['scheme_name']}  (code={c['scheme_code']}, isin={c.get('isin')}, "
              f"match_score={c.get('match_score', 0):.2f})")

    choice = input("Pick number, 's' to skip, or paste a scheme_code directly: ").strip()

    if choice.lower() == "s" or choice == "":
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(entry["candidates"]):
        return str(entry["candidates"][int(choice) - 1]["scheme_code"])
    # Treat anything else as a manually-typed scheme code (e.g. found via
    # tigzig.com directly, not in the candidate list)
    return choice


def main() -> None:
    entries = load()
    already_confirmed = sum(1 for e in entries if e.get("confirmed_scheme_code"))
    print(f"{already_confirmed}/{len(entries)} already confirmed. Reviewing the rest...")

    for entry in entries:
        if entry.get("confirmed_scheme_code"):
            continue  # already done in a previous run of this script
        code = prompt_for_entry(entry)
        entry["confirmed_scheme_code"] = code
        save(entries)  # save immediately — safe to Ctrl+C anytime

    confirmed = sum(1 for e in entries if e.get("confirmed_scheme_code"))
    print(f"\nDone. {confirmed}/{len(entries)} confirmed and saved to {RESOLVED_SCHEMES_PATH.name}.")
    if confirmed < len(entries):
        print(f"{len(entries) - confirmed} still unconfirmed — run this script again to finish them.")


if __name__ == "__main__":
    main()