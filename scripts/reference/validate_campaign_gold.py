#!/usr/bin/env python3
"""Independently recompute gold labels for all tail-ledger candidates."""

from __future__ import annotations

import re

from campaign_candidates import CAMPAIGN_CANDIDATES


def validate(candidate_id: str) -> int:
    item = CAMPAIGN_CANDIDATES[candidate_id]
    state: dict[str, dict[str, tuple[int, str]]] = {}
    consignments: dict[str, dict[str, str]] = {}
    for line in item.document.splitlines():
        ledger = re.fullmatch(r"T(\d+) (ZX-\d+): (.+)\.", line)
        if ledger:
            timestamp, asset, assignments = ledger.groups()
            for assignment in assignments.split(", "):
                field, value = assignment.split("=", 1)
                previous = state.setdefault(asset, {}).get(field, (-1, ""))
                if int(timestamp) > previous[0]:
                    state[asset][field] = (int(timestamp), value)
        elif " | carrier=" in line:
            item_id, carrier, destination, seal, crates = line.split(" | ")
            consignments[item_id] = {
                "carrier": carrier.removeprefix("carrier="),
                "destination": destination.removeprefix("destination="),
                "seal": seal.removeprefix("seal="),
                "crates": crates.removeprefix("crates="),
            }
    for question in item.questions:
        ledger = re.fullmatch(r"The final (status|bay|owner) for (ZX-\d+) is (.+)\.", question.text)
        direct = re.fullmatch(r"Consignment (\S+) has (carrier|destination|seal|crates) (.+)\.", question.text)
        assert bool(ledger) != bool(direct), question.id
        if ledger:
            field, asset, claimed = ledger.groups()
            expected = state[asset][field][1] == claimed
        else:
            item_id, field, claimed = direct.groups()
            expected = consignments[item_id][field] == claimed
        assert expected == question.expected, question.id
    return len(item.questions)


def main() -> None:
    total = sum(validate(candidate_id) for candidate_id in CAMPAIGN_CANDIDATES if candidate_id.startswith("tail"))
    print(f"Independently validated {total} tail-ledger gold labels from rendered documents.")


if __name__ == "__main__":
    main()
