"""KALA-NETRA V3 - Section 3: non-circular clock-offset synchronisation.

Runs BEFORE entity resolution and uses ONLY identity-free infrastructure
anchors (PDU hash, RRN, ATM dispenser trigger, DHCP XID, radio uptime
counter), so no suspect-attribution decision can leak into the clock model.
"""
from __future__ import annotations
import itertools, math
import numpy as np
import networkx as nx

from . import config as C

ANCHOR_TYPES = ["SMS_PDU_HASH", "RRN", "ATM_TERM_TRIG", "DHCP_XID", "CELL_HANDOVER_SEQ"]


def collect_anchors(events: list[dict]) -> list[dict]:
    buckets: dict[tuple[str, str], list[dict]] = {}
    for ev in events:
        for kt, kv in ((ev.get("anchor_key_type"), ev.get("anchor_key")),
                       (ev.get("anchor_key_2_type"), ev.get("anchor_key_2"))):
            if kt and kv:
                buckets.setdefault((kt, str(kv)), []).append(ev)
    anchors = []
    for (kt, kv), evs in sorted(buckets.items()):
        by_file: dict[str, dict] = {}
        for ev in sorted(evs, key=lambda e: e["event_id"]):
            by_file.setdefault(ev["file_id"], ev)       # first record per file
        if len(by_file) < 2:
            continue
        for fa, fb in itertools.combinations(sorted(by_file), 2):
            ea, eb = by_file[fa], by_file[fb]
            ia, ib = C.SOURCE_INDEX[fa], C.SOURCE_INDEX[fb]
            si, sj = C.SIGMA[fa], C.SIGMA[fb]
            anchors.append({
                "anchor_id": f"{kt}:{kv}:{fa}~{fb}", "anchor_type": kt, "anchor_key": kv,
                "file_i": fa, "file_j": fb, "i": ia, "j": ib,
                "tau_i": ea["raw_epoch"], "tau_j": eb["raw_epoch"],
                "event_i": ea["event_id"], "event_j": eb["event_id"],
                "weight": 1.0 / (si ** 2 + sj ** 2), "sigma_pair": math.sqrt(si ** 2 + sj ** 2),
                "used": True, "residual_s": None, "z": None,
            })
    return anchors


def _solve(anchors, active_files):
    """Weighted-least-squares offsets on the connected component of the reference."""
    M = len(C.SOURCES)
    g = nx.Graph()
    g.add_nodes_from(range(M))
    for a in anchors:
        if a["used"]:
            g.add_edge(a["i"], a["j"])
    comp = nx.node_connected_component(g, C.REFERENCE_SOURCE) if g.degree(C.REFERENCE_SOURCE) \
        else {C.REFERENCE_SOURCE}
    nodes = sorted(comp)
    pos = {n: k for k, n in enumerate(nodes)}
    n = len(nodes)
    L = np.zeros((n, n))
    b = np.zeros(n)
    for a in anchors:
        if not a["used"] or a["i"] not in pos or a["j"] not in pos:
            continue
        i, jx, w = pos[a["i"]], pos[a["j"]], a["weight"]
        L[i, i] += w; L[jx, jx] += w
        L[i, jx] -= w; L[jx, i] -= w
        d = a["tau_j"] - a["tau_i"]
        b[i] += w * d
        b[jx] -= w * d
    beta = {s[0]: 0.0 for s in C.SOURCES}
    if n > 1:
        ref = pos[C.REFERENCE_SOURCE]
        keep = [k for k in range(n) if k != ref]
        Lr, br = L[np.ix_(keep, keep)], b[keep]
        try:
            sol = np.linalg.solve(Lr, br)
        except np.linalg.LinAlgError:
            sol = np.linalg.lstsq(Lr, br, rcond=None)[0]
        for k, idx in enumerate(keep):
            beta[nodes[idx]] = float(sol[k])
    return beta, comp


def synchronise(files: list[dict], events: list[dict]) -> dict:
    anchors = collect_anchors(events)
    beta, comp = _solve(anchors, files)

    def residuals():
        out = []
        for a in anchors:
            if not a["used"]:
                a["residual_s"], a["z"] = None, None
                continue
            r = abs((a["tau_i"] + beta[a["i"]]) - (a["tau_j"] + beta[a["j"]]))
            a["residual_s"] = r
            a["z"] = r / a["sigma_pair"]
            out.append(r)
        return out

    residuals()
    rejected = []
    bad = [a for a in anchors if a["used"] and a["z"] and a["z"] > C.ANCHOR_RESIDUAL_Z]
    if bad:
        for a in bad:
            a["used"] = False
            rejected.append(a["anchor_id"])
        beta, comp = _solve(anchors, files)
        residuals()

    used = [a for a in anchors if a["used"]]
    rs = [a["residual_s"] for a in used]
    rmse = math.sqrt(sum(r * r for r in rs) / len(rs)) if rs else 0.0

    per_file = {}
    for sidx, fid, *_ in [(s[0], s[1]) + tuple(s[2:]) for s in C.SOURCES]:
        cnt = sum(1 for a in used if a["i"] == sidx or a["j"] == sidx)
        per_file[fid] = {"beta": round(beta[sidx], 4), "anchored": int(sidx in comp),
                         "anchors": cnt}
    for f in files:
        pf = per_file[f["file_id"]]
        f["estimated_clock_offset_sec"] = pf["beta"]
        f["is_clock_anchored"] = pf["anchored"]
        f["anchor_count"] = pf["anchors"]
    for ev in events:
        ev["corrected_timestamp_epoch"] = ev["raw_epoch"] + per_file[ev["file_id"]]["beta"]

    return {"anchors": anchors, "beta": {f: per_file[f]["beta"] for f in per_file},
            "per_file": per_file, "rmse_clock": rmse,
            "anchor_count": len(used), "rejected_anchors": rejected,
            "connected_component": sorted(comp),
            "unanchored_sources": [s[1] for s in C.SOURCES if s[0] not in comp]}
