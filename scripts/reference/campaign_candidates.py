"""Ten deterministic candidate tasks for the TypeSafe/Luna discovery campaign."""

from __future__ import annotations

import random
import re

from candidates import Candidate, Question, entity_binding, superseded_ledger


def candidate(
    candidate_id: str,
    title: str,
    lines: list[str],
    rows: list[tuple[str, str, bool, str, str]],
) -> Candidate:
    questions = tuple(Question(*row) for row in rows)
    ids = [question.id for question in questions]
    assert len(ids) == len(set(ids))
    assert len(questions) >= 100
    assert 0.45 <= sum(question.expected for question in questions) / len(questions) <= 0.55
    return Candidate(candidate_id, title, "\n".join(lines), questions)


def exact_catalog() -> Candidate:
    """Large direct lookup with visually similar identifiers."""
    colors = ("amber", "blue", "coral", "green", "ivory", "violet")
    zones = ("A1", "A2", "B1", "B2", "C1", "C2")
    lines = ["PARTS CATALOG", "Each row is final. Match the complete part ID exactly.", ""]
    records = []
    for index in range(180):
        part_id = f"PX-{index // 10:02d}-{index % 10:02d}"
        record = (colors[(index * 5 + 1) % 6], zones[(index * 7 + 2) % 6], 11 + (index * 13) % 89)
        records.append((part_id, *record))
        lines.append(f"{part_id} | color={record[0]} | zone={record[1]} | mass={record[2]}")
    rows = []
    for index, (part_id, color, zone, mass) in enumerate(records):
        field = ("color", "zone", "mass")[index % 3]
        actual = {"color": color, "zone": zone, "mass": mass}[field]
        expected = index % 2 == 0
        wrong = colors[(colors.index(color) + 1) % 6] if field == "color" else zones[(zones.index(zone) + 1) % 6] if field == "zone" else mass + 1
        claimed = actual if expected else wrong
        rows.append((f"x{index:03d}", f"Part {part_id} has {field} {claimed}.", expected, f"Catalog says {field}={actual}.", field))
    return candidate("exact180", "High-volume exact catalog lookup", lines, rows)


def sparse_evidence() -> Candidate:
    """Relevant facts separated by plausible but irrelevant prose."""
    rng = random.Random(4102)
    lines = ["FIELD NOTEBOOK", "Only lines beginning FACT define sample properties.", ""]
    records = []
    textures = ("smooth", "ribbed", "porous", "glassy")
    for index in range(120):
        sample = f"SM-{index:03d}"
        record = (textures[(index * 3) % 4], 2 + (index * 11) % 47)
        records.append((sample, *record))
        lines.extend([
            f"Observation {index + 1}: technicians discussed tray {rng.randint(10, 99)} and calibration procedure {rng.choice('ABCDE')}.",
            f"FACT {sample}: texture={record[0]}; density={record[1]}.",
            f"Comment: the next shift may revisit sample SM-{(index + 1) % 120:03d}; this is not a measurement.",
        ])
    rows = []
    for index, (sample, texture, density) in enumerate(records):
        field = "texture" if index % 2 == 0 else "density"
        actual = texture if field == "texture" else density
        expected = index % 4 < 2
        claimed = actual if expected else (textures[(textures.index(texture) + 1) % 4] if field == "texture" else density + 3)
        rows.append((f"s{index:03d}", f"The measured {field} of {sample} is {claimed}.", expected, f"FACT line says {field}={actual}.", field))
    return candidate("sparse120", "Sparse authoritative evidence", lines, rows)


def joins() -> Candidate:
    teams = ("Aster", "Beryl", "Cobalt", "Dahlia", "Ember", "Flint")
    regions = ("north", "south", "east", "west", "central", "coastal")
    levels = ("bronze", "silver", "gold", "platinum", "onyx", "pearl")
    lines = ["STAFF DIRECTORY AND TEAM TABLE", "A person's region and level are those of their assigned team.", "", "TEAMS"]
    team_data = {team: (regions[i], levels[(i * 5 + 2) % 6]) for i, team in enumerate(teams)}
    for team, (region, level) in team_data.items():
        lines.append(f"Team {team}: region={region}; level={level}.")
    lines.extend(["", "STAFF"])
    staff = []
    for index in range(144):
        person = f"P-{index:03d}"
        team = teams[(index * 5 + 1) % 6]
        staff.append((person, team))
        lines.append(f"{person} is assigned to Team {team}.")
    rows = []
    for index, (person, team) in enumerate(staff):
        field = "region" if index % 2 == 0 else "level"
        actual = team_data[team][0 if field == "region" else 1]
        pool = regions if field == "region" else levels
        expected = index % 4 in (0, 3)
        claimed = actual if expected else pool[(pool.index(actual) + 1) % 6]
        rows.append((f"j{index:03d}", f"Person {person}'s team {field} is {claimed}.", expected, f"{person}->{team}->{field}={actual}.", field))
    return candidate("join144", "Two-table staff-to-team join", lines, rows)


def intervals() -> Candidate:
    lines = ["PERMIT WINDOWS", "A permit is active from its start day through its end day, inclusive.", ""]
    permits = []
    for index in range(120):
        start = 1 + (index * 7) % 60
        end = start + 3 + (index * 5) % 15
        permit = f"PM-{index:03d}"
        permits.append((permit, start, end))
        lines.append(f"{permit}: start day {start}; end day {end}.")
    rows = []
    for index, (permit, start, end) in enumerate(permits):
        expected = index % 2 == 0
        day = start + (index % (end - start + 1)) if expected else end + 1 + index % 4
        rows.append((f"i{index:03d}", f"Permit {permit} is active on day {day}.", expected, f"Window is [{start}, {end}]; queried day={day}.", "active" if expected else "inactive"))
    return candidate("interval120", "Inclusive date-window evaluation", lines, rows)


def arithmetic() -> Candidate:
    lines = ["SHIPMENT CHARGES", "Total charge equals units times unit price plus the fixed fee. There are no other charges.", ""]
    shipments = []
    for index in range(120):
        units = 2 + (index * 7) % 18
        price = 3 + (index * 11) % 23
        fee = (index * 5) % 9
        shipment = f"CH-{index:03d}"
        total = units * price + fee
        shipments.append((shipment, units, price, fee, total))
        lines.append(f"{shipment}: units={units}; unit price={price}; fixed fee={fee}.")
    rows = []
    for index, (shipment, units, price, fee, total) in enumerate(shipments):
        expected = index % 2 == 0
        claimed = total if expected else total + 1 + index % 3
        rows.append((f"a{index:03d}", f"The total charge for {shipment} is {claimed}.", expected, f"{units}*{price}+{fee}={total}.", "total"))
    return candidate("arithmetic120", "Per-row charge arithmetic", lines, rows)


def overlaps() -> Candidate:
    lines = ["MACHINE BOOKINGS", "Two inclusive bookings conflict when they share at least one minute.", ""]
    bookings = []
    for index in range(120):
        a_start = 30 + (index * 17) % 500
        a_end = a_start + 10 + index % 30
        expected = index % 2 == 0
        b_start = a_end - index % 5 if expected else a_end + 1 + index % 9
        b_end = b_start + 8 + index % 20
        booking = f"BK-{index:03d}"
        bookings.append((booking, a_start, a_end, b_start, b_end, expected))
        lines.append(f"{booking}: first={a_start}-{a_end}; second={b_start}-{b_end}.")
    rows = [(f"o{i:03d}", f"The two bookings in {bid} conflict.", expected, f"Intervals [{a},{b}] and [{c},{d}].", "overlap" if expected else "separate") for i, (bid, a, b, c, d, expected) in enumerate(bookings)]
    return candidate("overlap120", "Interval-overlap detection", lines, rows)


def policy_matrix() -> Candidate:
    rng = random.Random(4107)
    lines = [
        "EXPORT RELEASE RULES",
        "Release is allowed only if inspection passed and payment cleared.",
        "Cold cargo additionally requires a temperature certificate.",
        "Hazardous cargo additionally requires both a permit and an escort.",
        "A director waiver replaces only the payment requirement; it replaces no other requirement.",
        "",
    ]
    items = []
    while len(items) < 120:
        item = dict(inspection=rng.choice((True, False)), payment=rng.choice((True, False)), cold=rng.choice((True, False)), certificate=rng.choice((True, False)), hazardous=rng.choice((True, False)), permit=rng.choice((True, False)), escort=rng.choice((True, False)), waiver=rng.choice((True, False)))
        allowed = item["inspection"] and (item["payment"] or item["waiver"]) and (not item["cold"] or item["certificate"]) and (not item["hazardous"] or (item["permit"] and item["escort"]))
        item_id = f"EX-{len(items):03d}"
        items.append((item_id, item, allowed))
    # Deterministically select a balanced subset from a larger generated pool.
    positives = [row for row in items if row[2]]
    while len(positives) < 60:
        index = len(items)
        item = dict(inspection=True, payment=index % 2 == 0, cold=index % 3 == 0, certificate=True, hazardous=index % 4 == 0, permit=True, escort=True, waiver=index % 2 == 1)
        row = (f"EX-{index:03d}", item, True)
        items.append(row); positives.append(row)
    negatives = [row for row in items if not row[2]][:60]
    selected = positives[:60] + negatives
    rng.shuffle(selected)
    for item_id, item, _ in selected:
        lines.append(item_id + ": " + "; ".join(f"{key}={'yes' if value else 'no'}" for key, value in item.items()) + ".")
    rows = [(f"p{i:03d}", f"Shipment {item_id} is allowed for release.", allowed, f"Computed from all applicable rules: allowed={allowed}.", "allowed" if allowed else "denied") for i, (item_id, _, allowed) in enumerate(selected)]
    return candidate("policy120", "Layered policy exceptions", lines, rows)


def aliases() -> Candidate:
    colors = ("red", "blue", "green", "white", "black", "gold")
    lines = ["VESSEL ALIAS LOG", "Each vessel has a code and alias. Later STATE lines replace earlier color for that same vessel.", ""]
    vessels = []
    for index in range(120):
        code = f"VS-{index:03d}"
        alias = f"{('Aurora','Beacon','Comet','Drift','Echo','Fable')[index % 6]}-{index // 6:02d}"
        initial = colors[index % 6]
        final = colors[(index * 5 + 2) % 6]
        vessels.append((code, alias, final))
        lines.append(f"REGISTER {code}: alias={alias}; color={initial}.")
        lines.append(f"STATE {alias}: color={final}.")
    rows = []
    for index, (code, alias, final) in enumerate(vessels):
        expected = index % 2 == 0
        claimed = final if expected else colors[(colors.index(final) + 1) % 6]
        rows.append((f"v{index:03d}", f"The final color of vessel {code} is {claimed}.", expected, f"{code} aliases {alias}; latest color={final}.", "alias-update"))
    return candidate("alias120", "Alias resolution plus updates", lines, rows)


def comparisons() -> Candidate:
    lines = ["SENSOR PAIRS", "Compare the exact readings shown for each pair.", ""]
    pairs = []
    for index in range(140):
        left = 10 + (index * 19) % 91
        delta = 1 + index % 7
        expected = index % 2 == 0
        right = left - delta if expected else left + delta
        pair_id = f"CP-{index:03d}"
        pairs.append((pair_id, left, right, expected))
        lines.append(f"{pair_id}: alpha={left}; beta={right}.")
    rows = [(f"c{i:03d}", f"For pair {pair_id}, alpha is greater than beta.", expected, f"alpha={left}, beta={right}.", "greater" if expected else "not-greater") for i, (pair_id, left, right, expected) in enumerate(pairs)]
    return candidate("compare140", "Numeric pair comparisons", lines, rows)


def ordered_chain() -> Candidate:
    lines = ["PACKAGE HANDOFFS", "Each arrow is one direct handoff. A two-step chain uses exactly two listed arrows.", ""]
    nodes = [f"H{i:02d}" for i in range(36)]
    edges = {(nodes[i], nodes[(i + step) % 36]) for i in range(36) for step in (1, 5)}
    adjacency = {node: set() for node in nodes}
    for source, target in edges:
        adjacency[source].add(target)
    for node in nodes:
        lines.append(f"{node} -> {', '.join(sorted(adjacency[node]))}")
    positives, negatives = [], []
    for source in nodes:
        two_step = {target for middle in adjacency[source] for target in adjacency[middle]}
        for target in nodes:
            if source == target:
                continue
            row = (source, target, target in two_step)
            (positives if row[2] else negatives).append(row)
    selected = positives[:60] + negatives[:60]
    random.Random(4110).shuffle(selected)
    rows = [(f"h{i:03d}", f"There is an exactly two-step handoff chain from {source} to {target}.", expected, f"Computed from outgoing arrows for {source} and its immediate successors.", "exists" if expected else "absent") for i, (source, target, expected) in enumerate(selected)]
    return candidate("chain120", "Exactly-two-step graph chains", lines, rows)


def tail_ledger(
    candidate_id: str,
    count: int,
    first_queried: int,
    seed: int,
    *,
    fields: tuple[str, ...] = ("status", "bay", "owner"),
    document_order: str = "time",
    question_order: str = "normal",
    direct_controls: int = 0,
) -> Candidate:
    """Query later entities in a dense superseding ledger."""
    base = superseded_ledger(count, candidate_id + "-source", "ZX", seed)
    headers, records = base.document.splitlines()[:5], base.document.splitlines()[5:]
    if document_order == "descending":
        records.sort(key=lambda line: int(re.match(r"T(\d+)", line).group(1)), reverse=True)
    elif document_order == "entity":
        records.sort(key=lambda line: (re.search(r"(ZX-\d+)", line).group(1), int(re.match(r"T(\d+)", line).group(1))))
    document = "\n".join(headers + records)
    questions = [
        q for q in base.questions
        if int(q.id[1:3]) >= first_queried and q.category in fields
    ]
    if question_order == "reverse":
        questions.reverse()
    elif question_order == "shuffle":
        random.Random(seed + 99).shuffle(questions)
    if direct_controls:
        direct = entity_binding()
        document += "\n\nCONTROL REGISTER\n\n" + direct.document
        questions.extend(direct.questions[:direct_controls])
    assert 0.45 <= sum(q.expected for q in questions) / len(questions) <= 0.55
    return Candidate(candidate_id, "Tail queries in superseding ledger", document, tuple(questions))


CAMPAIGN_CANDIDATES = {
    item.id: item
    for item in (
        exact_catalog(), sparse_evidence(), joins(), intervals(), arithmetic(),
        overlaps(), policy_matrix(), aliases(), comparisons(), ordered_chain(),
        tail_ledger("tail44", 44, 24, 4201),
        tail_ledger("tail60", 60, 30, 4202),
        tail_ledger("tail72", 72, 36, 4203),
        tail_ledger("tail48shuffle", 48, 24, 4204, question_order="shuffle"),
        tail_ledger("tail48reverseq", 48, 24, 4205, question_order="reverse"),
        tail_ledger("tail48descdoc", 48, 24, 4206, document_order="descending"),
        tail_ledger("tail48entitydoc", 48, 24, 4207, document_order="entity"),
        tail_ledger("tail60twofield", 60, 20, 4208, fields=("status", "bay")),
        tail_ledger("tail72status", 72, 12, 4209, fields=("status",)),
        tail_ledger("tail60mixed", 60, 32, 4210, direct_controls=18),
    )
}
