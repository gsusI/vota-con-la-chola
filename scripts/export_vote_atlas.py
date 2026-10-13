#!/usr/bin/env python3
"""Export the vote atlas: party and deputy directions per topic axis, from every classified Congreso vote.

Inputs: the vote database, the ballot-party mapping of the voting aid seed, the axes codebook and the
classification seed (one entry per contested non-amendment vote: up to two axes, the pole a Sí vote pushes
towards, and a confidence).

Direction of a party on an axis = weighted mean over its votes of push = sign x (Sí - No) / (Sí + No + Abst)
of its deputies (sign = +1 if Sí pushes to the positive pole). Weights: high/medium confidence count, low
confidence is listed but not scored; the points of one motion share one unit of weight per axis, so a
motion voted point by point counts as one initiative. A deputy's direction uses their own Sí/No/Abst.
Nothing is imputed: no votes on an axis -> no score.

Outputs (static, for /citizen):
- vote_atlas_v1.json: axes, party scores, every classified vote with its party majorities (drill-down).
- vote_atlas_people_v1.json: every deputy, their vote string over all roll-call votes (amendments included),
  loyalty to their party, and their axis scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.export_voting_aid_snapshot import DEFAULT_SEED, direction_balance, majority_choice  # noqa: E402
from scripts.vote_atlas import (  # noqa: E402
    AMENDMENT_KINDS,
    CURRENT_LEGISLATURE,
    LEG_ROMAN,
    XIV_GROUP_PARTY,
    affiliation_resolver,
    fold,
    text_key,
    CLASSIFIABLE_KINDS,
    DEFAULT_AXES,
    DEFAULT_TEXTS,
    KIND_LABELS,
    clean,
    contested,
    load_congreso_events,
    motion_key,
)

ATLAS_SCHEMA_VERSION = "vote_atlas_v1"
PEOPLE_SCHEMA_VERSION = "vote_atlas_people_v1"
CLASSIFICATIONS_SCHEMA_VERSION = "vote_atlas_classifications_v1"
DEFAULT_CLASSIFICATIONS = BASE_DIR / "etl/data/seeds/vote_atlas_classifications_v1.json"
SCORED_CONFIDENCE = {"alta", "media"}
CHOICE_CODES = {"Sí": "S", "No": "N", "Abstención": "A", "No vota": "-"}
VOTE_URL_PREFIX = "url:https://www.congreso.es/webpublica/opendata/votaciones/"
MIN_PERSON_AXIS_VOTES = 3


def short_id(vote_event_id: str) -> str:
    return "v-" + hashlib.sha1(vote_event_id.encode("utf-8")).hexdigest()[:10]


def vote_path(vote_event_id: str) -> str:
    return vote_event_id[len(VOTE_URL_PREFIX):] if vote_event_id.startswith(VOTE_URL_PREFIX) else vote_event_id


def validate_classifications(cls: dict[str, Any], axes: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    axis_ids = {a["axis_id"] for a in axes["axes"]}
    null_reasons = set(axes.get("null_reasons") or {})
    if cls.get("schema_version") != CLASSIFICATIONS_SCHEMA_VERSION:
        errors.append(f"schema_version debe ser {CLASSIFICATIONS_SCHEMA_VERSION}")
    for vid, item in (cls.get("votes") or {}).items():
        ax = item.get("axes") or []
        if len(ax) > 2:
            errors.append(f"{vid}: más de dos ejes")
        seen = set()
        for a in ax:
            if a.get("axis_id") not in axis_ids:
                errors.append(f"{vid}: eje desconocido {a.get('axis_id')!r}")
            if a.get("axis_id") in seen:
                errors.append(f"{vid}: eje repetido {a.get('axis_id')!r}")
            seen.add(a.get("axis_id"))
            if a.get("yes_pushes") not in {"+", "-"}:
                errors.append(f"{vid}: yes_pushes debe ser '+' o '-'")
            if a.get("confidence") not in {"alta", "media", "baja"}:
                errors.append(f"{vid}: confidence inválida {a.get('confidence')!r}")
        if not ax and item.get("null_reason") not in null_reasons:
            errors.append(f"{vid}: sin eje necesita null_reason válido")
    return errors


def load_member_votes(conn: sqlite3.Connection, legislature: str) -> list[tuple[str, str, int | None, str, str]]:
    return conn.execute(
        """
        SELECT m.vote_event_id, m.member_name, m.person_id, m.group_code, m.vote_choice
        FROM parl_vote_member_votes m JOIN parl_vote_events e USING (vote_event_id)
        WHERE e.source_id = 'congreso_votaciones' AND e.legislature = ?
        """,
        (legislature,),
    ).fetchall()


def name_key(name: str) -> str:
    return fold(clean(name))


def person_keys(rows: list[tuple]) -> dict[str, str]:
    """member_name -> stable person key, shared across legislatures: person_id when any row with that name
    (accents and case aside) has one, else a hash of the folded name."""
    ids: dict[str, Counter] = defaultdict(Counter)
    for _vid, name, pid, _g, _c in rows:
        if pid is not None:
            ids[name_key(name)][pid] += 1
    out = {}
    for _vid, name, _pid, _g, _c in rows:
        if name in out:
            continue
        k = name_key(name)
        out[name] = f"p{ids[k].most_common(1)[0][0]}" if ids.get(k) else "n-" + hashlib.sha1(k.encode()).hexdigest()[:8]
    return out


def weighted_mean(pairs: list[tuple[float, float]]) -> float | None:
    total = sum(w for _p, w in pairs)
    return None if total <= 0 else sum(p * w for p, w in pairs) / total


def ballot_majority(majorities: dict[str, str | None], legislature: str, pid: str) -> str | None:
    """Majority of a ballot party on a vote; in earlier legislatures, through its group then (or None)."""
    if legislature == CURRENT_LEGISLATURE:
        return majorities.get(pid)
    group = next((g for g, p in XIV_GROUP_PARTY.items() if p == pid), None)
    return majorities.get(f"g{legislature}:{group}") if group else None


def build(conn: sqlite3.Connection, seed: dict[str, Any], axes_doc: dict[str, Any], cls: dict[str, Any],
          texts: dict[str, Any], *, legislature: str, generated_at: str,
          earlier: list[tuple[str, str]] | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """`legislature` drives parties and the voting aid; `earlier` [(legislature, since_date)] adds older votes to
    the deputies' record only (their groups then do not map cleanly to today's ballot parties)."""
    party_ids = [p["party_id"] for p in seed["parties"]]
    legs = [(lg, since) for lg, since in (earlier or [])] + [(legislature, None)]
    events: list[dict[str, Any]] = []
    rows: list[tuple] = []
    for lg, since in legs:
        evs = load_congreso_events(conn, lg, since)
        ids = {e["vote_event_id"] for e in evs}
        events.extend(evs)
        rows.extend(r for r in load_member_votes(conn, lg) if r[0] in ids)
    current = [e for e in events if e["legislature"] == legislature]
    ev_index = {e["vote_event_id"]: i for i, e in enumerate(events)}
    resolvers = {lg: affiliation_resolver(seed, lg) for lg, _s in legs}
    keys = person_keys(rows)

    tallies: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    person_choice: dict[str, dict[int, str]] = defaultdict(dict)
    person_aff: dict[str, dict[int, str | None]] = defaultdict(dict)
    person_groups: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    names: dict[str, Counter] = defaultdict(Counter)
    person_group_last: dict[str, str] = {}
    person_group_last_i: dict[str, int] = {}
    unmapped: Counter = Counter()
    for vid, name, _pid, group, choice in rows:
        i = ev_index[vid]
        lg = events[i]["legislature"]
        name = str(name or "")
        key = keys[name]
        aff = resolvers[lg](name, str(group or ""))
        names[key][name] += 1
        person_choice[key][i] = str(choice or "")
        person_aff[key][i] = aff
        person_groups[key][lg][str(group or "")] += 1
        if i >= person_group_last_i.get(key, -1):
            person_group_last_i[key], person_group_last[key] = i, str(group or "")
        if aff is None:
            if lg == legislature:
                unmapped[name] += 1
            continue
        tallies[vid][aff][str(choice or "")] += 1

    majorities = {e["vote_event_id"]: {aff: majority_choice(c) for aff, c in tallies[e["vote_event_id"]].items()} for e in events}
    for e in current:
        for pid in party_ids:
            majorities[e["vote_event_id"]].setdefault(pid, None)

    def ballot_codes(ev: dict[str, Any]) -> str:
        maj = majorities[ev["vote_event_id"]]
        out = []
        for pid in party_ids:
            m = ballot_majority(maj, ev["legislature"], pid)
            out.append("=" if m == "tie" else CHOICE_CODES.get(m or "", "?"))
        return "".join(out)

    # --- classified votes -> weighted pushes per axis
    axis_ids = [a["axis_id"] for a in axes_doc["axes"]]
    votes_cls = cls.get("votes") or {}
    group_sizes: Counter = Counter()
    scored: list[tuple[dict[str, Any], str, int]] = []  # (event, axis_id, sign)
    for ev in events:
        item = votes_cls.get(ev["vote_event_id"])
        if not item:
            continue
        for a in item.get("axes") or []:
            if a["confidence"] in SCORED_CONFIDENCE:
                group_sizes[(text_key(ev["legislature"], ev["expediente_text"]), a["axis_id"])] += 1
                scored.append((ev, a["axis_id"], 1 if a["yes_pushes"] == "+" else -1))

    party_pairs: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    party_inits: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    person_pairs: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    axis_votes: Counter = Counter()
    axis_inits: dict[str, set] = defaultdict(set)
    for ev, axis_id, sign in scored:
        vid = ev["vote_event_id"]
        gkey = (text_key(ev["legislature"], ev["expediente_text"]), axis_id)
        w = 1.0 / group_sizes[gkey]
        if ev["legislature"] == legislature:
            # Parties: only the current legislature, where deputies map to today's ballot parties.
            axis_votes[axis_id] += 1
            axis_inits[axis_id].add(gkey[0])
            for pid in party_ids:
                c = tallies[vid][pid]
                n = c.get("Sí", 0) + c.get("No", 0) + c.get("Abstención", 0)
                if n:
                    party_pairs[pid][axis_id].append((sign * (c.get("Sí", 0) - c.get("No", 0)) / n, w))
                    party_inits[pid][axis_id].add(gkey[0])
        i = ev_index[vid]
        for key, choices in person_choice.items():
            ch = choices.get(i)
            if ch in ("Sí", "No", "Abstención"):
                push = sign * (1 if ch == "Sí" else -1 if ch == "No" else 0)
                person_pairs[key][axis_id].append((push, w))

    def axis_cell(pairs: list[tuple[float, float]], inits: int) -> dict[str, Any] | None:
        score = weighted_mean(pairs)
        if score is None:
            return None
        return {"score": round(score, 3), "votes": len(pairs), "initiatives": inits}

    party_axes = {
        pid: {ax: cell for ax in axis_ids if (cell := axis_cell(party_pairs[pid][ax], len(party_inits[pid][ax])))}
        for pid in party_ids
    }

    # --- atlas votes (classified, for drill-down)
    atlas_votes = []
    status_by_leg: dict[str, Counter] = defaultdict(Counter)
    for ev in events:
        vid = ev["vote_event_id"]
        item = votes_cls.get(vid)
        count = status_by_leg[ev["legislature"]]
        if ev["kind"] in AMENDMENT_KINDS:
            count["enmienda_sin_texto"] += 1
        elif ev["kind"] not in CLASSIFIABLE_KINDS:
            count["tramite"] += 1
        elif not contested(majorities[vid]):
            count["sin_division"] += 1
        elif not item:
            count["pendiente"] += 1
        elif item.get("axes"):
            count["con_eje"] += 1
        else:
            count[f"sin_eje:{item.get('null_reason')}"] += 1
        if not item:
            continue
        text = (texts.get(text_key(ev["legislature"], ev["expediente_text"])) or {}).get("text") or {}
        atlas_votes.append({
            "id": short_id(vid),
            "path": vote_path(vid),
            **({"leg": ev["legislature"]} if ev["legislature"] != legislature else {}),
            "date": ev["vote_date"],
            "kind": ev["kind"],
            "title": clean(str(ev["expediente_text"]).split("\n")[0]),
            "subgroup": clean(" ".join(x for x in (ev["subgroup_title"], ev["subgroup_text"]) if x)),
            "summary_yes": item.get("summary_yes") or "",
            "axes": [[a["axis_id"], a["yes_pushes"], a["confidence"]] for a in item.get("axes") or []],
            "null_reason": None if item.get("axes") else item.get("null_reason"),
            "approved": (ev["yes"] or 0) > (ev["no"] or 0),
            "totals": [ev["yes"], ev["no"], ev["abstain"]],
            "parties": ballot_codes(ev),
            **({"text_url": text["url"]} if text.get("url") else {}),
        })
    classified_count = status_by_leg[legislature]
    n_events = len(current)

    # --- people
    people = []
    for key, choices in person_choice.items():
        idx = sorted(choices)
        name = names[key].most_common(1)[0][0]
        # Ballot party at the last vote (None for no adscritos, and for deputies who only sat in earlier legislatures).
        last_aff = person_aff[key][idx[-1]]
        last_party = last_aff if last_aff in party_ids else None
        party_history = list(dict.fromkeys(a for i in idx if (a := person_aff[key][i]) in party_ids))
        agree = total = 0
        by_leg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        rebels = []
        for i in idx:
            ch = choices[i]
            aff = person_aff[key][i]
            if ch not in ("Sí", "No", "Abstención") or not aff:
                continue
            maj = majorities[events[i]["vote_event_id"]].get(aff)
            if maj in (None, "tie"):
                continue
            total += 1
            by_leg[events[i]["legislature"]][1] += 1
            if ch == maj:
                agree += 1
                by_leg[events[i]["legislature"]][0] += 1
            else:
                rebels.append([i, CHOICE_CODES[maj]])
        seated = len(idx)
        voted = sum(1 for i in idx if choices[i] in ("Sí", "No", "Abstención"))
        first, last = idx[0], idx[-1]
        legs_present = sorted(person_groups[key], key=int)
        people.append({
            "id": key,
            "name": name,
            "party_id": last_party,
            "party_history": party_history,
            "last_group": person_group_last[key],
            "groups": [g for lg in legs_present for g, _n in person_groups[key][lg].most_common() if g],
            "groups_by_leg": {lg: [g for g, _n in person_groups[key][lg].most_common() if g] for lg in legs_present},
            "legislatures": legs_present,
            "first": first,
            "votes": "".join(CHOICE_CODES.get(choices.get(i, ""), ".") if i in choices else "." for i in range(first, last + 1)),
            "seated": seated,
            "participation": round(voted / seated, 3) if seated else None,
            "loyalty": round(agree / total, 3) if total else None,
            "loyalty_votes": total,
            "loyalty_by_leg": {lg: [round(a / t, 3), t] for lg, (a, t) in sorted(by_leg.items()) if t},
            "rebels": rebels,
            "axes": {
                ax: [round(s, 3), len(person_pairs[key][ax])]
                for ax in axis_ids
                if len(person_pairs[key][ax]) >= MIN_PERSON_AXIS_VOTES and (s := weighted_mean(person_pairs[key][ax])) is not None
            },
        })
    people.sort(key=lambda p: (p["party_id"] or "zz", p["name"]))

    dates = [e["vote_date"] for e in current if e["vote_date"]]
    all_dates = [e["vote_date"] for e in events if e["vote_date"]]
    review = cls.get("review") or {}
    meta_common = {
        "generated_at": generated_at,
        "institution": "Congreso de los Diputados",
        "legislature": legislature,
        "votes_first_date": min(dates) if dates else None,
        "votes_last_date": max(dates) if dates else None,
        "review": review,
    }
    atlas = {
        "meta": {
            **meta_common,
            "schema_version": ATLAS_SCHEMA_VERSION,
            "method": {
                "party_direction": "Media ponderada, por eje, de signo × (Sí − No) / (Sí + No + Abstención) de los diputados del partido; signo +1 si votar Sí empuja hacia el polo positivo.",
                "weights": "Solo cuentan las clasificaciones de confianza alta o media. Los puntos de una misma moción comparten un peso por eje: una moción votada por puntos cuenta como una iniciativa.",
                "classification": "Cada votación se clasifica por su contenido (texto oficial del BOCG cuando existe), sin ver cómo votaron los partidos.",
                "not_classified": "Las enmiendas y votos particulares no se clasifican: los datos de votación solo dan su número, no su texto. Sí cuentan en el historial de cada diputado.",
            },
            "coverage": {
                "events_total": n_events,
                "by_status": dict(sorted(classified_count.items())),
                "scored_votes": len({ev["vote_event_id"] for ev, _a, _s in scored if ev["legislature"] == legislature}),
                "axes_with_votes": sum(1 for ax in axis_ids if axis_votes[ax]),
            },
            "earlier_legislatures": {
                lg: {"since": since, "events_total": sum(1 for e in events if e["legislature"] == lg),
                     "by_status": dict(sorted(status_by_leg[lg].items())),
                     "note": "Solo cuentan para el historial y la dirección de cada diputado/a; no para los partidos."}
                for lg, since in (earlier or [])
            },
            "unmapped_member_votes": dict(sorted(unmapped.items())),
            "honesty": [
                "Las direcciones salen solo de votaciones nominales del Pleno del Congreso; no de programas ni declaraciones.",
                "La clasificación de cada votación en un eje es una lectura del texto votado hecha con IA y revisable: cada votación enlaza a su texto oficial.",
                "Una puntuación cercana a 0 puede significar abstención, votos divididos o votos en ambos sentidos; mira las votaciones.",
                "Las enmiendas a las leyes no están clasificadas: una parte de la acción legislativa queda fuera.",
            ],
        },
        "topics": axes_doc["topics"],
        "axes": [
            {k: a[k] for k in ("axis_id", "topic_id", "label", "pos", "neg", "pos_short", "neg_short")}
            | {"votes": axis_votes[a["axis_id"]], "initiatives": len(axis_inits[a["axis_id"]])}
            for a in axes_doc["axes"]
        ],
        "null_reasons": axes_doc.get("null_reasons") or {},
        "parties": [{"party_id": p["party_id"], "label": p["label"]} for p in seed["parties"]],
        "party_axes": party_axes,
        "kind_labels": KIND_LABELS,
        "votes": atlas_votes,
    }
    people_doc = {
        "meta": {
            **meta_common,
            "schema_version": PEOPLE_SCHEMA_VERSION,
            "votes_first_date": min(all_dates) if all_dates else None,
            "legislatures": [
                {"legislature": lg, "label": LEG_ROMAN.get(lg, lg), "since": since,
                 "first_index": next((i for i, e in enumerate(events) if e["legislature"] == lg), None),
                 "events": sum(1 for e in events if e["legislature"] == lg)}
                for lg, since in legs
            ],
            "vote_codes": {"S": "Sí", "N": "No", "A": "Abstención", "-": "No vota", ".": "No era diputado/a en esa votación"},
            "loyalty": (
                "Porcentaje de votaciones en que votó igual que la mayoría de su partido (solo Sí/No/Abstención; empates excluidos). "
                "En legislaturas anteriores se compara con su grupo parlamentario de entonces, salvo los grupos Mixto y Plural, que "
                "reunían a varios partidos y no cuentan."
            ),
            "axes": f"Dirección personal por eje con al menos {MIN_PERSON_AXIS_VOTES} votaciones clasificadas; mismo método y pesos que los partidos.",
            "path_prefix": VOTE_URL_PREFIX[4:],
        },
        "parties": atlas["parties"],
        "votes": [
            [short_id(e["vote_event_id"]), vote_path(e["vote_event_id"]), e["vote_date"], e["kind"],
             clean(str(e["expediente_text"]).split("\n")[0])[:220],
             clean(" ".join(x for x in (e["subgroup_title"], e["subgroup_text"]) if x))[:120], e["legislature"]]
            for e in events
        ],
        "people": people,
    }
    ctx = {"events": current, "tallies": tallies, "majorities": majorities, "votes_cls": votes_cls, "party_ids": party_ids}
    return atlas, people_doc, ctx


AID_SCHEMA_VERSION = "voting_aid_snapshot_v2"
AID_SEED_SCHEMA_VERSION = "voting_aid_statements_v2"
DEFAULT_AID_SEED = BASE_DIR / "etl/data/seeds/voting_aid_generales_v2.json"
AGREE_AT = 0.33


def score_position(score: float | None) -> str:
    if score is None:
        return "no_data"
    if score >= AGREE_AT:
        return "agree"
    if score <= -AGREE_AT:
        return "disagree"
    return "mixed"


def build_voting_aid(ctx: dict[str, Any], seed: dict[str, Any], aid_seed: dict[str, Any], axes_doc: dict[str, Any],
                     texts: dict[str, Any], atlas_meta: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    """Multi-vote statements: one per axis, backed by every vote whose PRIMARY axis it is (high/medium confidence)."""
    axis_by_id = {a["axis_id"]: a for a in axes_doc["axes"]}
    topic_by_id = {t["topic_id"]: t for t in axes_doc["topics"]}
    party_ids = ctx["party_ids"]
    min_votes = int(aid_seed.get("min_votes") or 1)
    primary: dict[str, list[tuple[dict[str, Any], int]]] = defaultdict(list)
    for ev in ctx["events"]:
        item = ctx["votes_cls"].get(ev["vote_event_id"])
        axes = (item or {}).get("axes") or []
        if axes and axes[0]["confidence"] in SCORED_CONFIDENCE:
            primary[axes[0]["axis_id"]].append((ev, 1 if axes[0]["yes_pushes"] == "+" else -1))
    statements = []
    skipped = []
    cell_counts: Counter = Counter()
    for st in aid_seed["statements"]:
        axis = axis_by_id[st["axis_id"]]
        pole = 1 if st["pole"] == "+" else -1
        votes = primary.get(st["axis_id"], [])
        if len(votes) < min_votes:
            skipped.append({"statement_id": st["statement_id"], "votes": len(votes)})
            continue
        groups = Counter(motion_key(ev["expediente_text"]) for ev, _s in votes)
        pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)
        votes_out = []
        for ev, sign in sorted(votes, key=lambda x: x[0]["vote_date"] or "", reverse=True):
            vid = ev["vote_event_id"]
            w = 1.0 / groups[motion_key(ev["expediente_text"])]
            toward = sign * pole  # +1: voting Sí moves towards the statement
            for pid in party_ids:
                c = ctx["tallies"][vid][pid]
                n = c.get("Sí", 0) + c.get("No", 0) + c.get("Abstención", 0)
                if n:
                    pairs[pid].append((toward * (c.get("Sí", 0) - c.get("No", 0)) / n, w))
            maj = ctx["majorities"][vid]
            text = (texts.get(motion_key(ev["expediente_text"])) or {}).get("text") or {}
            votes_out.append({
                "id": short_id(vid),
                "vote_event_id": vid,
                "vote_date": ev["vote_date"],
                "title": clean(str(ev["expediente_text"]).split("\n")[0]),
                "subgroup": clean(" ".join(x for x in (ev["subgroup_title"], ev["subgroup_text"]) if x)),
                "summary_yes": ctx["votes_cls"][vid].get("summary_yes") or "",
                "g": motion_key(ev["expediente_text"])[:8],  # initiative key: points of one motion share it
                "kind": ev["kind"],
                "agree_vote": "Sí" if toward > 0 else "No",
                "approved": (ev["yes"] or 0) > (ev["no"] or 0),
                "totals": [ev["yes"], ev["no"], ev["abstain"]],
                "parties": "".join(CHOICE_CODES.get(maj[pid] or "", "?") if maj[pid] != "tie" else "=" for pid in party_ids),
                "source_url": ev["source_url"] or (vid[4:] if vid.startswith("url:") else None),
                **({"text_url": text["url"]} if text.get("url") else {}),
            })
        # Examples first: the latest vote of each initiative (laws and decrees before motions), then the rest.
        kind_rank = {"final": 0, "rdl": 0, "toma": 1, "totalidad": 1, "pnl": 2, "mocion": 2}
        seen_groups: set[str] = set()
        heads, rest = [], []
        for v, (ev, _s) in zip(votes_out, sorted(votes, key=lambda x: x[0]["vote_date"] or "", reverse=True)):
            g = motion_key(ev["expediente_text"])
            (rest if g in seen_groups else heads).append((kind_rank.get(ev["kind"], 3), v))
            seen_groups.add(g)
        heads.sort(key=lambda x: x[0])
        votes_out = [v for _r, v in heads] + [v for _r, v in rest]
        cells = {}
        for pid in party_ids:
            score = weighted_mean(pairs[pid])
            position = score_position(score)
            cell_counts[position] += 1
            cells[pid] = {
                "position": position,
                "score": None if score is None else round(score, 3),
                "votes_with_data": len(pairs[pid]),
                "votes_total": len(votes),
            }
        topic = topic_by_id[axis["topic_id"]]
        statements.append({
            "statement_id": st["statement_id"],
            "axis_id": st["axis_id"],
            "pole": st["pole"],
            "concern_id": topic.get("concern_id"),
            "theme": topic["label"],
            "text": st["text"],
            "context": st.get("context") or f"Eje «{axis['label']}»: {axis['pos_short']} frente a {axis['neg_short']}.",
            "votes_total": len(votes),
            "initiatives_total": len(groups),
            "cells": cells,
            "votes": votes_out,
        })
    balance = direction_balance(statements, aid_seed.get("balance_reference_parties") or ["psoe", "pp"])
    return {
        "meta": {
            "schema_version": AID_SCHEMA_VERSION,
            "generated_at": generated_at,
            "election": aid_seed.get("election"),
            "legislature": aid_seed.get("legislature"),
            "institution": aid_seed.get("institution"),
            "review": aid_seed.get("review"),
            "classification_review": atlas_meta.get("review"),
            "method": aid_seed.get("method"),
            "votes_first_date": atlas_meta.get("votes_first_date"),
            "votes_last_date": atlas_meta.get("votes_last_date"),
            "quality": {
                "statements_total": len(statements),
                "statements_skipped": skipped,
                "votes_total": sum(s["votes_total"] for s in statements),
                "initiatives_total": sum(s["initiatives_total"] for s in statements),
                "cells_by_position": dict(sorted(cell_counts.items())),
                "direction_balance": balance,
            },
            "honesty": [
                "Las posiciones salen solo de votaciones nominales del Pleno del Congreso; no de programas ni declaraciones.",
                "Cada afirmación resume muchas votaciones; un partido puede haber votado distinto en alguna. El porcentaje indica cuán constante fue.",
                "Qué votación va a qué tema lo decidió una IA leyendo el texto oficial, sin ver los votos; cada votación está enlazada para comprobarlo.",
            ],
        },
        "parties": [{"party_id": p["party_id"], "label": p["label"], **({"note": p["note"]} if p.get("note") else {})} for p in seed["parties"]],
        "unmapped_members": seed.get("unmapped_members") or [],
        "statements": statements,
    }


def write_json(path: Path, doc: dict[str, Any], max_bytes: int) -> int:
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"
    size = len(body.encode("utf-8"))
    if size > max_bytes:
        raise SystemExit(f"ERROR: {path.name} ocupa {size} bytes (> {max_bytes})")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return size


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", required=True)
    p.add_argument("--legislature", default="15")
    p.add_argument("--seed", default=str(DEFAULT_SEED))
    p.add_argument("--axes", default=str(DEFAULT_AXES))
    p.add_argument("--classifications", default=str(DEFAULT_CLASSIFICATIONS))
    p.add_argument("--texts", default=str(DEFAULT_TEXTS))
    p.add_argument("--aid-seed", default=str(DEFAULT_AID_SEED))
    p.add_argument("--earlier", action="append", default=[], metavar="LEG:YYYY-MM-DD",
                   help="Legislatura anterior a añadir al historial de diputados, desde una fecha (p. ej. 14:2022-10-01)")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--max-bytes", type=int, default=4_500_000)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    axes_doc = json.loads(Path(args.axes).read_text(encoding="utf-8"))
    cls = json.loads(Path(args.classifications).read_text(encoding="utf-8"))
    errors = validate_classifications(cls, axes_doc)
    if errors:
        for e in errors[:30]:
            print(f"ERROR clasificación: {e}", file=sys.stderr)
        return 2
    texts = json.loads(Path(args.texts).read_text(encoding="utf-8")).get("motions", {}) if Path(args.texts).exists() else {}
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        earlier = [tuple(x.split(":", 1)) for x in args.earlier]
        atlas, people, ctx = build(conn, seed, axes_doc, cls, texts, legislature=args.legislature, generated_at=generated_at, earlier=earlier)
    finally:
        conn.close()
    aid_seed = json.loads(Path(args.aid_seed).read_text(encoding="utf-8"))
    if aid_seed.get("schema_version") != AID_SEED_SCHEMA_VERSION:
        print(f"ERROR: {args.aid_seed} debe tener schema_version {AID_SEED_SCHEMA_VERSION}", file=sys.stderr)
        return 2
    unknown = [st["axis_id"] for st in aid_seed["statements"] if st["axis_id"] not in {a["axis_id"] for a in axes_doc["axes"]}]
    if unknown:
        print(f"ERROR: ejes desconocidos en {args.aid_seed}: {unknown}", file=sys.stderr)
        return 2
    aid = build_voting_aid(ctx, seed, aid_seed, axes_doc, texts, atlas["meta"], generated_at=generated_at)
    out = Path(args.out_dir)
    a = write_json(out / "vote_atlas_v1.json", atlas, args.max_bytes)
    p = write_json(out / "vote_atlas_people_v1.json", people, args.max_bytes)
    v = write_json(out / "voting_aid_generales_v2.json", aid, args.max_bytes)
    q = aid["meta"]["quality"]
    print(f"OK voting aid v2 ({v}B): statements={q['statements_total']} votes={q['votes_total']} "
          f"initiatives={q['initiatives_total']} cells={q['cells_by_position']} balance={q['direction_balance']} skipped={q['statements_skipped']}")
    cov = atlas["meta"]["coverage"]
    print(f"OK vote atlas -> {out} (atlas={a}B people={p}B events={cov['events_total']} scored={cov['scored_votes']} "
          f"status={cov['by_status']} people={len(people['people'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
