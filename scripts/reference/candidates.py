"""Deterministic candidate benchmarks with auditable gold labels."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    expected: bool
    proof: str
    category: str


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    document: str
    questions: tuple[Question, ...]


def _validated(candidate: Candidate) -> Candidate:
    ids = [question.id for question in candidate.questions]
    assert len(ids) == len(set(ids))
    assert all(isinstance(question.expected, bool) for question in candidate.questions)
    assert 0.35 <= sum(question.expected for question in candidate.questions) / len(ids) <= 0.65
    return candidate


def superseded_ledger(
    count: int = 48,
    candidate_id: str = "ledger",
    prefix: str = "AX",
    seed: int = 3101,
) -> Candidate:
    rng = random.Random(seed)
    statuses = ["ready", "held", "inspection", "released"]
    bays = ["B1", "B2", "C1", "C2", "D1", "D2"]
    owners = ["Aster", "Boreal", "Cygnus", "Dorado", "Equinox", "Fjord"]
    records = {}
    entries = []
    for index in range(1, count + 1):
        asset = f"{prefix}-{index:03d}"
        state = {
            "status": statuses[index % len(statuses)],
            "bay": bays[(index * 2) % len(bays)],
            "owner": owners[(index * 3) % len(owners)],
        }
        entries.append((10, asset, dict(state)))
        for time in (20, 30, 40):
            field = ("status", "bay", "owner")[(index + time // 10) % 3]
            if field == "status":
                value = statuses[(statuses.index(state[field]) + index + time) % len(statuses)]
            elif field == "bay":
                value = bays[(bays.index(state[field]) + index + time) % len(bays)]
            else:
                value = owners[(owners.index(state[field]) + index + time) % len(owners)]
            state[field] = value
            entries.append((time + rng.randint(0, 4), asset, {field: value}))
        records[asset] = state
    entries.sort()
    lines = [
        "ASSET LEDGER",
        "For each asset and field, the latest timestamp is final.",
        "An update changes only the fields that it names.",
        "Earlier values remain in the ledger but are not final.",
        "",
    ]
    for time, asset, update in entries:
        values = ", ".join(f"{field}={value}" for field, value in update.items())
        lines.append(f"T{time:02d} {asset}: {values}.")
    questions = []
    for index, (asset, final) in enumerate(records.items()):
        for field, values in (("status", statuses), ("bay", bays), ("owner", owners)):
            expected = (index + len(field)) % 2 == 0
            value = final[field] if expected else values[(values.index(final[field]) + 1) % len(values)]
            questions.append(
                Question(
                    id=f"l{index:02d}{field[0]}",
                    text=f"The final {field} for {asset} is {value}.",
                    expected=expected,
                    proof=f"Latest {field} value for {asset} is {final[field]}; claim says {value}.",
                    category=field,
                )
            )
    return _validated(
        Candidate(
            candidate_id,
            "Superseded asset ledger",
            "\n".join(lines),
            tuple(questions),
        )
    )


def entity_binding() -> Candidate:
    rng = random.Random(3102)
    carriers = ["Nacre", "Opal", "Quartz", "Raven", "Sable", "Topaz"]
    cities = ["Arden", "Brim", "Cedar", "Dover", "Elm", "Fallow"]
    seals = ["K7P", "M2Q", "R9D", "T4X", "V6N", "Z3H"]
    records = {}
    lines = [
        "CONSIGNMENT REGISTER",
        "Each row is final and belongs only to the exact consignment ID on that row.",
        "Similar IDs identify different consignments.",
        "",
    ]
    prefixes = ["KA", "KB", "KC", "KD", "KE", "KF"]
    for index in range(72):
        consignment = f"{prefixes[index % 6]}-{index // 6:02d}-{index % 3}"
        record = {
            "carrier": carriers[(index * 5 + 1) % 6],
            "city": cities[(index * 7 + 2) % 6],
            "seal": seals[(index * 11 + 3) % 6],
            "crates": 2 + (index * 7) % 17,
        }
        records[consignment] = record
        lines.append(
            f"{consignment} | carrier={record['carrier']} | destination={record['city']} | "
            f"seal={record['seal']} | crates={record['crates']}"
        )
    questions = []
    for index, (consignment, record) in enumerate(records.items()):
        fields = ("carrier", "city", "seal", "crates")
        for offset in range(2):
            field = fields[(index + offset) % len(fields)]
            expected = (index + offset) % 2 == 0
            if expected:
                value = record[field]
            elif field == "crates":
                value = record[field] + rng.choice((1, 2, 3))
            else:
                pool = carriers if field == "carrier" else cities if field == "city" else seals
                value = pool[(pool.index(record[field]) + rng.randint(1, 5)) % len(pool)]
            label = "destination" if field == "city" else field
            questions.append(
                Question(
                    id=f"e{index:02d}{offset}",
                    text=f"Consignment {consignment} has {label} {value}.",
                    expected=expected,
                    proof=f"Exact row for {consignment} has {label} {record[field]}; claim says {value}.",
                    category=field,
                )
            )
    return _validated(
        Candidate("entities", "Similar-ID entity binding", "\n".join(lines), tuple(questions))
    )


def mixed_ledger(
    ledger_assets: int,
    direct_questions: int,
    candidate_id: str,
    prefix: str,
    seed: int,
) -> Candidate:
    ledger = superseded_ledger(
        ledger_assets, f"{candidate_id}-ledger", prefix, seed
    )
    entities = entity_binding()
    document = (
        "SECTION A: UPDATED ASSETS\n\n"
        + ledger.document
        + "\n\nSECTION B: FINAL CONSIGNMENT ROWS\n\n"
        + entities.document
    )
    questions = ledger.questions + entities.questions[:direct_questions]
    return _validated(
        Candidate(candidate_id, "Mixed update and direct lookup", document, questions)
    )


def policy_exceptions() -> Candidate:
    rng = random.Random(3103)
    candidates = []
    while len(candidates) < 1200:
        item = {
            "clearance": rng.randint(1, 4),
            "tier": rng.randint(1, 4),
            "training": rng.choice((True, False)),
            "suspended": rng.choice((False, False, False, True)),
            "worker": rng.choice(("employee", "contractor")),
            "sponsor": rng.choice((True, False)),
            "hour": rng.choice((2, 5, 8, 12, 18, 21, 23)),
            "emergency": rng.choice((False, False, True)),
        }
        standard_hours = 6 <= item["hour"] < 20
        time_allowed = standard_hours or (
            item["emergency"] and item["worker"] == "employee"
        )
        contractor_allowed = not (
            item["worker"] == "contractor"
            and item["tier"] == 4
            and not item["sponsor"]
        )
        approved = (
            not item["suspended"]
            and item["training"]
            and item["clearance"] >= item["tier"]
            and time_allowed
            and contractor_allowed
        )
        item["approved"] = approved
        candidates.append(item)
    selected = []
    for wanted in (True, False):
        selected.extend(
            [item for item in candidates if item["approved"] == wanted][:60]
        )
    rng.shuffle(selected)
    lines = [
        "ARCHIVE ACCESS POLICY",
        "Evaluate every request with all six rules.",
        "1. Suspended workers are always denied.",
        "2. Current training is required.",
        "3. Clearance must be equal to or greater than the archive tier.",
        "4. Standard access hours are 06:00 through 19:59.",
        "5. An emergency permits access outside standard hours only for employees.",
        "6. A tier-4 contractor also needs a sponsor. Other contractors do not.",
        "A request is approved only when every applicable rule permits it.",
        "",
        "REQUESTS",
    ]
    questions = []
    for index, item in enumerate(selected):
        request_id = f"RQ-{index:03d}"
        lines.append(
            f"{request_id} | worker={item['worker']} | clearance={item['clearance']} | "
            f"tier={item['tier']} | training={'current' if item['training'] else 'expired'} | "
            f"suspended={'yes' if item['suspended'] else 'no'} | "
            f"sponsor={'yes' if item['sponsor'] else 'no'} | hour={item['hour']:02d}:00 | "
            f"emergency={'yes' if item['emergency'] else 'no'}"
        )
        outcomes = {
            "not suspended": not item["suspended"],
            "training current": item["training"],
            "clearance sufficient": item["clearance"] >= item["tier"],
            "time permitted": (6 <= item["hour"] < 20)
            or (item["emergency"] and item["worker"] == "employee"),
            "contractor exception satisfied": not (
                item["worker"] == "contractor"
                and item["tier"] == 4
                and not item["sponsor"]
            ),
        }
        questions.append(
            Question(
                id=f"p{index:03d}",
                text=f"Request {request_id} is approved under the archive policy.",
                expected=item["approved"],
                proof="; ".join(f"{name}={value}" for name, value in outcomes.items()),
                category="approved" if item["approved"] else "denied",
            )
        )
    return _validated(
        Candidate("policy", "Policy with exceptions", "\n".join(lines), tuple(questions))
    )


def graph_routes() -> Candidate:
    rng = random.Random(3104)
    nodes = [f"N{index:02d}" for index in range(24)]
    edges = set()
    for source_index, source in enumerate(nodes):
        for step in (1, 4, 9):
            edges.add((source, nodes[(source_index + step) % len(nodes)]))
    adjacency = {node: set() for node in nodes}
    for source, target in edges:
        adjacency[source].add(target)

    def reachable(source: str, target: str) -> tuple[bool, str]:
        if target in adjacency[source]:
            return True, f"direct route {source}->{target}"
        for middle in sorted(adjacency[source]):
            if target in adjacency[middle]:
                return True, f"two-leg route {source}->{middle}->{target}"
        examined = ", ".join(
            f"{source}->{middle}->{{{','.join(sorted(adjacency[middle]))}}}"
            for middle in sorted(adjacency[source])
        )
        return False, f"no direct or two-leg route; examined {examined}"

    possible = []
    for source in nodes:
        for target in nodes:
            if source != target:
                answer, proof = reachable(source, target)
                possible.append((source, target, answer, proof))
    selected = []
    for wanted in (True, False):
        pool = [item for item in possible if item[2] == wanted]
        rng.shuffle(pool)
        selected.extend(pool[:64])
    rng.shuffle(selected)
    lines = [
        "DIRECTED ROUTE MAP",
        "An arrow permits travel only in the arrow direction.",
        "A valid trip uses one direct route or exactly two routes with one transfer.",
        "Trips with more than one transfer are invalid.",
        "No route exists unless an arrow is listed below.",
        "",
    ]
    for source in nodes:
        lines.append(f"{source} -> {', '.join(sorted(adjacency[source]))}")
    questions = tuple(
        Question(
            id=f"g{index:03d}",
            text=f"A valid trip exists from {source} to {target} with at most one transfer.",
            expected=answer,
            proof=proof,
            category="reachable" if answer else "unreachable",
        )
        for index, (source, target, answer, proof) in enumerate(selected)
    )
    return _validated(Candidate("routes", "Directed two-leg routes", "\n".join(lines), questions))


CANDIDATES = {
    candidate.id: candidate
    for candidate in (
        superseded_ledger(),
        superseded_ledger(36, "ledger36", "LX", 3201),
        superseded_ledger(42, "ledger42", "MX", 3301),
        superseded_ledger(44, "ledger44", "NX", 3401),
        superseded_ledger(46, "ledger46", "PX", 3501),
        mixed_ledger(30, 42, "mixed30", "QX", 3601),
        mixed_ledger(34, 30, "mixed34", "RX", 3701),
        mixed_ledger(38, 18, "mixed38", "SX", 3801),
        mixed_ledger(40, 12, "mixed40", "TX", 3901),
        entity_binding(),
        policy_exceptions(),
        graph_routes(),
    )
}
