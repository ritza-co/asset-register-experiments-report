#!/usr/bin/env python3
"""Observed reliable prompt for the NX-001 final-status question."""

import os

from typesafe_client import TypeSafeClient
from typesafe_client.api.models import NoulQuestion

from minimal_typesafe_repro import DOCUMENT

QUESTION = (
    "Relevant NX-001 rows are: T10 status=held, bay=C1, owner=Dorado; "
    "T23 status=inspection; T32 bay=C2; T44 owner=Cygnus. Apply the ledger rules. "
    "The final status for NX-001 is inspection."
)


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
