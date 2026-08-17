#!/usr/bin/env python3
"""Minimal observed reproduction of the NX-001 final-status error."""

import os

from typesafe_client import TypeSafeClient
from typesafe_client.api.models import NoulQuestion

DOCUMENT = """ASSET LEDGER
For each asset and field, the latest timestamp is final.
An update changes only the fields that it names.
Earlier values remain in the ledger but are not final.

T10 NX-001: status=held, bay=C1, owner=Dorado.
T10 NX-002: status=inspection, bay=D1, owner=Aster.
T22 NX-002: bay=C1.
T23 NX-001: status=inspection.
T32 NX-001: bay=C2.
T32 NX-002: owner=Cygnus.
T44 NX-001: owner=Cygnus.
T44 NX-002: status=ready."""

QUESTION = "The final status for NX-001 is inspection."


def main() -> None:
    client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])
    response = client.system_one(
        model="speed_latest",
        document=DOCUMENT,
        questions={"target": NoulQuestion(instructions=QUESTION)},
    )

    probability_true = response.answers["target"].noul
    print(f"Expected: true; p(true)={probability_true:.2f}")


if __name__ == "__main__":
    main()
