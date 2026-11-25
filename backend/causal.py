"""KALA-NETRA V3 - Section 6A: rule-based causal attack-chain reconstruction.

No point-process fitting, no learned parameters: a transparent domain
transition table with explicit base weights and half-lives, followed by a
maximum-weight spanning arborescence to extract the single cleanest storyline.
"""
from __future__ import annotations
import json, math, os
import networkx as nx

from . import config as C


DEFAULT_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "causal_rules.json")


def load_rules(path: str | None = None) -> dict:
    """Load the domain causal transition table.

    A copy dropped in data/causal_rules.json overrides the shipped default, so an
    investigator can retune base weights and half-lives without touching code.
    """
    if path is None:
        override = os.path.join(C.DATA_DIR, "causal_rules.json")
        path = override if os.path.exists(override) else DEFAULT_RULES
    with open(path) as f:
        return json.load(f)


# ------------------------------------------------------------- constraints ---
def _ex(ev, k, d=""):
    return (ev.get("extra") or {}).get(k, d)


def constraint_ok(name, a, b, ctx) -> bool:
    victim_ms = ctx.get("victim_msisdn", "")
    if name == "victim_msisdn_device":
        return b["event_type"] == "APK_INSTALL" and a["target_id"] == ctx.get("victim_msisdn")
    if name == "same_ufdr_device":
        return a.get("device_id") and a.get("device_id") == b.get("device_id")
    if name == "victim_msisdn_link":
        return _ex(a, "imei") == ctx.get("victim_imei") or a.get("actor_id") == ctx.get("victim_imei")
    if name == "swapped_msisdn":
        return a["target_id"] == b["actor_id"] or _ex(a, "msisdn") == _ex(b, "msisdn")
    if name == "rrn_or_victim_account":
        return (_ex(a, "rrn") and _ex(a, "rrn") == _ex(b, "rrn")) or \
               b["actor_id"] == ctx.get("victim_account") or \
               a["target_id"] == ctx.get("victim_account")
    if name == "target_equals_actor":
        return a["target_id"] and a["target_id"] == b["actor_id"]
    if name == "same_terminal":
        ta, tb = _ex(a, "terminal_id"), _ex(b, "terminal_id")
        return bool(ta) and ta == tb
    if name == "same_terminal_same_profile":
        ta, tb = _ex(a, "terminal_id"), _ex(b, "terminal_id")
        if not (ta and ta == tb):
            return False
        prof = ctx.get("suspect_profile")
        if not prof:
            return True
        return f'{b["actor_type"]}:{b["actor_id"]}' in prof
    return True


def build(events: list[dict], detectors: list[dict], rules: dict | None = None,
          clusters: list[dict] | None = None) -> dict:
    rules = rules or load_rules()
    by_type: dict[str, list[dict]] = {}
    for ev in events:
        by_type.setdefault(ev["event_type"], []).append(ev)

    # context facts derived (non-circularly) from the deterministic detectors
    ctx = {}
    swap = next((d for d in detectors if d["code"] == "SIM_SWAP_DETECTED"), None)
    if swap:
        ctx["victim_msisdn"] = swap["nodes"][0].split(":", 1)[1]
        # the resolved profile that took control of the victim MSISDN; used to keep
        # unrelated vehicles at the same ATM terminal out of the crime storyline
        for cl in (clusters or []):
            if any(n in cl["members"] for n in swap["nodes"][1:]):
                ctx["suspect_profile"] = set(cl["members"])
                ctx["suspect_profile_id"] = cl["cluster_id"]
                break
    phish = by_type.get("PHISHING_SMS_IN", [])
    if phish and "victim_msisdn" not in ctx:
        ctx["victim_msisdn"] = phish[0]["target_id"]
    apk = by_type.get("APK_INSTALL", [])
    if apk:
        ctx["victim_imei"] = apk[0]["actor_id"]
    deb = by_type.get("UPI_DEBIT_TXN", [])
    if deb:
        ctx["victim_account"] = deb[0]["actor_id"]

    edges = []
    for rule in rules["rules"]:
        causes, effects = by_type.get(rule["cause"], []), by_type.get(rule["effect"], [])
        lam = math.log(2) / rule["half_life_s"]
        for a in causes:
            for b in effects:
                dt = b["corrected_timestamp_epoch"] - a["corrected_timestamp_epoch"]
                if dt <= 0 or dt > rules["window_s"]:
                    continue
                if not constraint_ok(rule["constraint"], a, b, ctx):
                    continue
                score = rule["w"] * math.exp(-lam * dt)
                if score < rules["min_score"]:
                    continue
                edges.append({"src": a["event_id"], "dst": b["event_id"],
                              "cause_type": rule["cause"], "effect_type": rule["effect"],
                              "dt_s": round(dt, 2), "base_weight": rule["w"],
                              "half_life_s": rule["half_life_s"],
                              "constraint": rule["constraint"], "label": rule["label"],
                              "causal_score": round(score, 4)})

    # ---- maximum-weight spanning arborescence --------------------------------
    # every candidate edge runs strictly forward in time, so the graph is a DAG
    # and selecting each node's highest-weight incoming edge is exactly optimal.
    G = nx.DiGraph()
    for e in edges:
        if G.has_edge(e["src"], e["dst"]):
            if G[e["src"]][e["dst"]]["weight"] >= e["causal_score"]:
                continue
        G.add_edge(e["src"], e["dst"], weight=e["causal_score"], meta=e)
    chosen = {}
    for n in G.nodes:
        ins = list(G.in_edges(n, data=True))
        if ins:
            best = max(ins, key=lambda x: (x[2]["weight"], x[0]))
            chosen[n] = best[2]["meta"]
    arb = sorted(chosen.values(), key=lambda e: e["dt_s"])
    roots = sorted(n for n in G.nodes if n not in chosen)

    # ---- primary storyline: the arborescence branch rooted at the intrusion --
    first_cause = rules["rules"][0]["cause"]
    primary = next((r for r in roots
                    if any(ev["event_id"] == r and ev["event_type"] == first_cause
                           for ev in events)), roots[0] if roots else None)
    tree = {}
    for e in arb:
        tree.setdefault(e["src"], []).append(e)
    storyline, seen, stack = [], set(), [primary] if primary else []
    while stack:
        n = stack.pop(0)
        if n in seen:
            continue
        seen.add(n)
        for e in sorted(tree.get(n, []), key=lambda x: x["dt_s"]):
            storyline.append(e)
            stack.append(e["dst"])
    ts = {ev["event_id"]: ev["corrected_timestamp_epoch"] for ev in events}
    storyline.sort(key=lambda e: (ts.get(e["src"], 0), ts.get(e["dst"], 0)))
    return {"edges": edges, "arborescence": arb, "roots": roots,
            "primary_root": primary, "storyline": storyline,
            "node_count": G.number_of_nodes(), "context": ctx,
            "rules": rules["rules"]}
