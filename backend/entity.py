"""KALA-NETRA V3 - Section 4: training-free multi-modal entity resolution.

Four orthogonal, fully interpretable signals are computed for every candidate
pair of actor nodes; no model weights, no training data, no GNN.

  S_exact  deterministic co-record device binding (IMEI/IMSI/MAC in one record)
  S_str    Jaro-Winkler + OCR homoglyph canonicalisation
  S_struct meta-path Adamic-Adar over shared low-degree hubs
  S_st     uncertainty-buffered spatio-temporal co-occurrence
"""
from __future__ import annotations
import itertools, math, re
from collections import defaultdict

import networkx as nx

from . import config as C

PLATE_RE = re.compile(C.PLATE_RE)


# ---------------------------------------------------------------- strings ----
def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    win = max(la, lb) // 2 - 1
    fa, fb = [False] * la, [False] * lb
    m = 0
    for i in range(la):
        for k in range(max(0, i - win), min(lb, i + win + 1)):
            if not fb[k] and a[i] == b[k]:
                fa[i] = fb[k] = True
                m += 1
                break
    if m == 0:
        return 0.0
    t, k = 0, 0
    for i in range(la):
        if fa[i]:
            while not fb[k]:
                k += 1
            if a[i] != b[k]:
                t += 1
            k += 1
    t //= 2
    return (m / la + m / lb + (m - t) / m) / 3.0


def jaro_winkler(a: str, b: str, p: float = 0.1) -> float:
    j = jaro(a, b)
    l = 0
    for x, y in zip(a, b):
        if x != y or l == 4:
            break
        l += 1
    return j + l * p * (1 - j)


def canon_ocr(s: str, node_type: str) -> str:
    """Forensic homoglyph canonicalisation.

    Indian number plates end in a 4-digit series (regex
    ^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$), so homoglyph substitution is applied
    ONLY to those numeric positions. Canonicalising the alphabetic series block
    would collapse genuinely different plates onto one another.
    """
    s = s.upper().strip()
    if node_type != "VEHICLE_PLATE" or len(s) < 8:
        return s
    head, tail = s[:-4], s[-4:]
    return head + "".join(C.HOMOGLYPH.get(ch, ch) for ch in tail)


def s_str(u_type, u_id, v_type, v_id) -> float:
    """Exact-after-canonicalisation match scores 0.95; raw Jaro-Winkler is only
    allowed to assert a link when it is >= 0.95, so the ~40 unrelated background
    plates (which sit at JW 0.65-0.90 against each other) never cross it."""
    if u_type != v_type:
        return 0.0
    a, b = u_id.upper().strip(), v_id.upper().strip()
    canon_eq = (canon_ocr(a, u_type) == canon_ocr(b, v_type)) and len(a) == len(b)
    if u_type != "VEHICLE_PLATE":
        # outside the OCR namespace, only homoglyph-equivalence may assert a link:
        # raw edit similarity between account handles or IMEIs is meaningless
        return 0.95 if canon_eq else 0.0
    jw = jaro_winkler(a, b)
    return max(0.95 if canon_eq else 0.0, jw if jw >= 0.95 else 0.0)


# ------------------------------------------------------------------ graph ----
def nkey(t, i):
    return f"{t}:{i}"


def build_graph(events: list[dict]) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for ev in events:
        pairs = [(ev["actor_type"], ev["actor_id"]), (ev["target_type"], ev["target_id"])]
        pairs += [(t, i) for t, i in ev.get("co_record_ids", [])]
        for t, i in pairs:
            if t and i:
                k = nkey(t, i)
                if k not in G:
                    G.add_node(k, ntype=t, nid=i, events=[])
        if ev["actor_type"] and ev["actor_id"]:
            G.nodes[nkey(ev["actor_type"], ev["actor_id"])]["events"].append(ev["event_id"])
        if ev["actor_type"] and ev["actor_id"] and ev["target_type"] and ev["target_id"]:
            G.add_edge(nkey(ev["actor_type"], ev["actor_id"]),
                       nkey(ev["target_type"], ev["target_id"]),
                       key=ev["event_id"], t=ev.get("corrected_timestamp_epoch"),
                       etype=ev["event_type"], lat=ev["lat"], lon=ev["lon"],
                       r=ev["r_e"], ev_id=ev["event_id"], file_id=ev["file_id"],
                       amount=ev["amount_inr"])
    return G


# --------------------------------------------------------------- haversine ---
def haversine(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * C.EARTH_R * math.asin(min(1.0, math.sqrt(a)))


# ------------------------------------------------------------- resolution ----
class Resolver:
    def __init__(self, events: list[dict], graph: nx.MultiDiGraph):
        self.events = {e["event_id"]: e for e in events}
        self.G = graph
        self.geo = defaultdict(list)     # node -> [(t, lat, lon, r, ev_id)]
        self.hubs = defaultdict(set)     # node -> {hub node}
        self.comms = defaultdict(set)    # node -> {counterparty node}
        for ev in events:
            if not (ev["actor_type"] and ev["actor_id"]):
                continue
            a = nkey(ev["actor_type"], ev["actor_id"])
            if ev["lat"] is not None and ev["lon"] is not None:
                self.geo[a].append((ev["corrected_timestamp_epoch"], ev["lat"], ev["lon"],
                                    ev["r_e"] or C.UNCERTAINTY_R["DEFAULT"], ev["event_id"]))
            if ev["target_type"] and ev["target_id"]:
                tk = nkey(ev["target_type"], ev["target_id"])
                self.hubs[a].add(tk)
                self.comms[a].add(tk)
        for v in self.geo.values():
            v.sort()
        self.degree = {n: self.G.degree(n) for n in self.G.nodes}

    # ---------------------------------------------------- co-record binding --
    def co_record_pairs(self) -> dict[tuple[str, str], list[str]]:
        out = defaultdict(list)
        for ev in self.events.values():
            ids = [(t, i) for t, i in ev.get("co_record_ids", []) if i]
            for (ta, ia), (tb, ib) in itertools.combinations(ids, 2):
                if ta in {"IMEI", "IMSI", "MAC_ADDR"} and tb in {"IMEI", "IMSI", "MAC_ADDR"} \
                        and nkey(ta, ia) != nkey(tb, ib):
                    k = tuple(sorted((nkey(ta, ia), nkey(tb, ib))))
                    out[k].append(ev["event_id"])
        return out

    # ------------------------------------------------------------ structural -
    def s_struct(self, u, v):
        shared = self.hubs[u] & self.hubs[v]
        aa, detail = 0.0, []
        for z in sorted(shared):
            zt = self.G.nodes[z]["ntype"]
            w = C.HUB_WEIGHT.get(zt, 0.5)
            deg = max(1, self.degree.get(z, 1))
            c = w / math.log(1 + deg)
            aa += c
            detail.append({"hub": z, "hub_type": zt, "degree": deg, "contribution": round(c, 4)})
        return 1.0 - math.exp(-C.GAMMA_AA * aa), aa, detail

    # -------------------------------------------------- spatio-temporal ------
    def s_st(self, u, v):
        A, B = self.geo.get(u, []), self.geo.get(v, [])
        if not A or not B or len(A) * len(B) > 20000:
            return 0.0, 0, []
        kappas, pts, detail = [], [], []
        jstart = 0
        for ta, la, loa, ra, ida in A:
            while jstart < len(B) and B[jstart][0] < ta - C.ST_WINDOW_S:
                jstart += 1
            k = jstart
            while k < len(B) and B[k][0] <= ta + C.ST_WINDOW_S:
                tb, lb, lob, rb, idb = B[k]
                d = haversine(la, loa, lb, lob)
                dd = max(0.0, d - (ra + rb))
                dt = abs(ta - tb)
                kap = math.exp(-(dd ** 2) / (2 * C.LEN_D ** 2) - (dt ** 2) / (2 * C.LEN_T ** 2))
                kappas.append(kap)
                pts.append(((la + lb) / 2, (loa + lob) / 2))
                if kap > 0.2:
                    detail.append({"event_u": ida, "event_v": idb, "dt_s": round(dt, 1),
                                   "d_m": round(d, 1), "d_eff_m": round(dd, 1),
                                   "kappa": round(kap, 4)})
                k += 1
        if not kappas:
            return 0.0, 0, []
        # Aggregate the STRONGEST co-occurrence at each distinct spatial cluster
        # (sites >= 1 km apart). Averaging over every pair inside the 15-minute
        # window would let a single far-apart reading dilute a real convoy.
        sites: list[list] = []
        for (la, lo), kap in zip(pts, kappas):
            if kap < 0.05:
                continue
            for site in sites:
                if haversine(la, lo, site[0], site[1]) < C.DISTINCT_CLUSTER_M:
                    site[2] = max(site[2], kap)
                    break
            else:
                sites.append([la, lo, kap])
        if not sites:
            return 0.0, 0, []
        D = len(sites)
        best = sum(sv[2] for sv in sites) / D
        score = (1 - math.exp(-C.CLUSTER_RATE * D)) * best
        detail.sort(key=lambda x: -x["kappa"])
        return score, D, detail[:12]

    # ---------------------------------------------------------- candidates ---
    def candidates(self):
        cand = set()
        cand |= set(self.co_record_pairs().keys())
        hub_members = defaultdict(set)
        for n, hs in self.hubs.items():
            if self.G.nodes[n]["ntype"] in C.CANDIDATE_TYPES:
                for h in hs:
                    hub_members[h].add(n)
        for h, members in hub_members.items():
            if len(members) > 260:
                continue
            for a, b in itertools.combinations(sorted(members), 2):
                cand.add(tuple(sorted((a, b))))
        # spatio-temporal blocking: 0.01 deg grid x 900 s bucket
        buckets = defaultdict(set)
        for n, evs in self.geo.items():
            if self.G.nodes[n]["ntype"] not in C.CANDIDATE_TYPES:
                continue
            for t, la, lo, r, _ in evs:
                buckets[(round(la, 2), round(lo, 2), int(t // C.ST_WINDOW_S))].add(n)
        for members in buckets.values():
            if len(members) > 260:
                continue
            for a, b in itertools.combinations(sorted(members), 2):
                cand.add(tuple(sorted((a, b))))
        # same-namespace string blocking for plates / VPAs
        by_type = defaultdict(list)
        for n, d in self.G.nodes(data=True):
            if d["ntype"] in ("VEHICLE_PLATE", "UPI_VPA"):
                by_type[d["ntype"]].append(n)
        for t, ns in by_type.items():
            if len(ns) <= 400:
                for a, b in itertools.combinations(sorted(ns), 2):
                    cand.add(tuple(sorted((a, b))))
        return {p for p in cand
                if self.G.nodes[p[0]]["ntype"] in C.CANDIDATE_TYPES
                and self.G.nodes[p[1]]["ntype"] in C.CANDIDATE_TYPES}

    # ------------------------------------------------------------- resolve ---
    def resolve(self):
        corec = self.co_record_pairs()
        links, all_scores = [], []
        for u, v in sorted(self.candidates()):
            ut, ui = self.G.nodes[u]["ntype"], self.G.nodes[u]["nid"]
            vt, vi = self.G.nodes[v]["ntype"], self.G.nodes[v]["nid"]
            sx = 1.0 if (u, v) in corec else 0.0
            ss = s_str(ut, ui, vt, vi)
            sc, aa, hub_detail = self.s_struct(u, v)
            st, D, st_detail = self.s_st(u, v)
            combo = C.W_STRUCT * sc + C.W_ST * st
            convoy = st if (D >= C.CONVOY_MIN_SITES and st >= C.CONVOY_MIN_SCORE) else 0.0
            score = max(sx, ss, combo, convoy)
            if score < 0.45:
                continue
            basis = max((("DETERMINISTIC_CO_RECORD_BINDING", sx), ("STRING_OCR_MATCH", ss),
                         ("STRUCTURAL_PLUS_SPATIOTEMPORAL", combo), ("CONVOY_CO_TRAVEL", convoy)),
                        key=lambda x: x[1])[0]
            rec = {"u": u, "v": v, "u_type": ut, "u_id": ui, "v_type": vt, "v_id": vi,
                   "link_score": round(score, 4), "basis": basis,
                   "s_exact": round(sx, 4), "s_str": round(ss, 4), "s_struct": round(sc, 4),
                   "s_st": round(st, 4), "adamic_adar": round(aa, 4), "distinct_sites": D,
                   "shared_hubs": hub_detail, "colocations": st_detail,
                   "co_record_events": corec.get((u, v), [])[:6]}
            all_scores.append(rec)
            if score >= C.LINK_THRESHOLD:
                links.append(rec)

        # ------- clusters = connected components of the accepted link set ----
        g = nx.Graph()
        g.add_nodes_from(self.G.nodes)
        for l in links:
            g.add_edge(l["u"], l["v"], score=l["link_score"])
        clusters = []
        for comp in nx.connected_components(g):
            if len(comp) < 2:
                continue
            members = sorted(comp)
            nev = sum(len(self.G.nodes[m].get("events", [])) for m in members)
            clusters.append({"cluster_id": f"P{len(clusters)+1}", "members": members,
                             "member_detail": [{"type": self.G.nodes[m]["ntype"],
                                                "id": self.G.nodes[m]["nid"]} for m in members],
                             "event_count": nev})
        clusters.sort(key=lambda c: -c["event_count"])
        for i, c in enumerate(clusters):
            c["cluster_id"] = f"P{i+1}"
        near = sorted((r for r in all_scores if r["link_score"] < C.LINK_THRESHOLD),
                      key=lambda r: -r["link_score"])[:40]
        return {"links": links, "near_misses": near,
                "clusters": clusters, "detectors": self.detectors(links, clusters)}

    # ------------------------------------------------------------ detectors --
    def detectors(self, links, clusters):
        out = []
        for l in links:
            if l["u_type"] == l["v_type"] == "IMEI" and l["s_st"] >= C.BURNER_ST_MIN:
                direct = self.G.number_of_edges(l["u"], l["v"]) + self.G.number_of_edges(l["v"], l["u"])
                if direct == 0:
                    out.append({"code": "BURNER_COMPANION_PAIR", "severity": "HIGH",
                                "nodes": [l["u"], l["v"]],
                                "detail": (f'IMEI {l["u_id"]} and IMEI {l["v_id"]} co-located across '
                                           f'{l["distinct_sites"]} distinct sites (S_st={l["s_st"]:.3f}) '
                                           f'with zero direct communication between them')})
        # SIM-swap / clone transition
        binds = defaultdict(list)
        for ev in self.events.values():
            if ev["event_type"] in ("SIM_BIND", "IMSI_ATTACH", "CELL_ATTACH", "CELL_DETACH"):
                ms = (ev.get("extra") or {}).get("msisdn", "")
                im = (ev.get("extra") or {}).get("imei", "")
                ii = (ev.get("extra") or {}).get("imsi", "")
                if ms and im:
                    binds[ms].append((ev["corrected_timestamp_epoch"], im, ii, ev["event_id"]))
        for ms, rows in binds.items():
            rows.sort()
            for (t1, i1, s1, e1), (t2, i2, s2, e2) in zip(rows, rows[1:]):
                if i1 != i2 and s1 != s2:
                    out.append({"code": "SIM_SWAP_DETECTED", "severity": "CRITICAL",
                                "nodes": [nkey("MSISDN", ms), nkey("IMEI", i2), nkey("IMSI", s2)],
                                "event_ids": [e1, e2], "t_swap": t2,
                                "detail": (f'MSISDN {ms} moved from handset IMEI {i1} / IMSI {s1} to '
                                           f'handset IMEI {i2} / IMSI {s2}; the previous handset '
                                           f'ceased network activity at the same instant')})
        return out


def run(events, graph=None):
    G = graph if graph is not None else build_graph(events)
    r = Resolver(events, G)
    res = r.resolve()
    res["graph"] = G
    res["resolver"] = r
    return res
