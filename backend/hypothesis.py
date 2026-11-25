"""KALA-NETRA V3 - Section 7: redundancy-clustered hypothesis comparator.

The engine NEVER outputs a probability of guilt. It outputs an auditable
ordinal support tally per competing hypothesis, computed over de-duplicated
evidentiary clusters so that one underlying fact logged by two systems is
counted once.
"""
from __future__ import annotations
import networkx as nx
from . import config as C

HYPOTHESES = [
    {"id": "H1", "title": "Coordinated cyber-physical heist (suspect profile)",
     "detail": "An external operator ran phishing plus a SIM-swap, siphoned funds through "
               "pass-through mule accounts, fabricated a GPS alibi and withdrew cash in person "
               "at the Nehru Place terminal."},
    {"id": "H2", "title": "Purely remote cyber intrusion",
     "detail": "Malware drained the account remotely with no local physical presence at "
               "Connaught Place or Nehru Place."},
    {"id": "H3", "title": "First-party customer fraud / false dispute",
     "detail": "The complainant authorised the transactions from his own device and fabricated "
               "the complaint."},
]
SCALE = {"EXACT_MATCH": 30, "STRONG": 20, "CIRCUMSTANTIAL": 10,
         "NEUTRAL": 0, "CONTRADICTION": -20}


def _rule(ev, ctx):
    """Deterministic ordinal support table. Returns (band, {H: s}, rationale)."""
    et, prof = ev["event_type"], ctx["profile_nodes"]
    a = f'{ev["actor_type"]}:{ev["actor_id"]}'
    t = f'{ev["target_type"]}:{ev["target_id"]}'
    in_prof = a in prof or t in prof
    if ev["event_id"] in ctx["spoofed"]:
        return ("STRONG", {"H1": 20, "H2": -20, "H3": -20},
                "an application-layer location fix was proved physically impossible, i.e. an "
                "actively fabricated alibi, which is conduct consistent with H1 and incompatible "
                "with a purely remote intrusion or a first-party dispute")
    if ev["event_id"] in ctx["split_custody"]:
        return ("STRONG", {"H1": 20, "H2": -20, "H3": 0},
                "two devices of one resolved profile were simultaneously present at sites "
                "kilometres apart, showing a deliberately staged decoy handset")
    if et == "SIM_BIND":
        return ("EXACT_MATCH", {"H1": 30, "H2": 0, "H3": -20},
                "operator records bind the complainant's MSISDN to a different handset and "
                "subscriber module, which the complainant could not have caused himself")
    if et == "OTP_SMS_INTERCEPT" and in_prof:
        return ("EXACT_MATCH", {"H1": 30, "H2": 0, "H3": -20},
                "the bank OTP for the complainant's account was delivered to the suspect handset")
    if et == "ATM_CASH_WDL" and ev["amount_inr"] and ev["amount_inr"] >= 100000:
        return ("EXACT_MATCH", {"H1": 30, "H2": -20, "H3": 0},
                "the consolidated balance was physically dispensed at an ATM, which requires a "
                "person at the terminal")
    if et == "CCTV_ANPR_SIGHTING" and in_prof:
        return ("STRONG", {"H1": 20, "H2": -20, "H3": 0},
                "automatic number-plate recognition places a vehicle of the resolved profile at "
                "the cash-out terminal")
    if et in ("APK_INSTALL", "PERM_ACCESSIBILITY"):
        return ("STRONG", {"H1": 20, "H2": 20, "H3": -20},
                "privileged SMS/accessibility capture was installed on the complainant's handset, "
                "which is inconsistent with an authorised first-party transaction")
    if et in ("PHISHING_SMS_IN", "PHISHING_SMS_OUT"):
        return ("STRONG", {"H1": 20, "H2": 20, "H3": -20},
                "an inbound SMS carrying the dropper URL precedes the compromise")
    if et == "UPI_MULE_HOP" and ev["actor_id"] in ctx["mules"]:
        return ("STRONG", {"H1": 20, "H2": 10, "H3": -20},
                "funds were layered through a pass-through account within seconds of receipt, "
                "a laundering pattern rather than a customer payment")
    if et == "UPI_DEBIT_TXN":
        return ("CIRCUMSTANTIAL", {"H1": 10, "H2": 10, "H3": 10},
                "the debit itself is consistent with every hypothesis and is therefore only "
                "circumstantial")
    if et in ("WIFI_ASSOC", "WIFI_DHCPACK", "WIFI_DHCP_CLIENT") and in_prof:
        return ("STRONG", {"H1": 20, "H2": -20, "H3": 0},
                "physical 802.11 association places the suspect device inside the premises")
    if et in ("CELL_ATTACH", "IMSI_ATTACH") and in_prof:
        return ("CIRCUMSTANTIAL", {"H1": 10, "H2": -20, "H3": 0},
                "a single cell-sector attachment places the device within roughly 500 m")
    if et == "GPS_PING" and in_prof:
        return ("CIRCUMSTANTIAL", {"H1": 10, "H2": 0, "H3": 0},
                "an uncontested application-layer fix")
    return (None, None, None)


def redundancy_clusters(events: list[dict]) -> list[list[str]]:
    g = nx.Graph()
    for ev in events:
        g.add_node(ev["event_id"])
    by_anchor: dict[str, list[str]] = {}
    for ev in events:
        for kt, kv in ((ev.get("anchor_key_type"), ev.get("anchor_key")),
                       (ev.get("anchor_key_2_type"), ev.get("anchor_key_2"))):
            if kt and kv:
                by_anchor.setdefault(f"{kt}:{kv}", []).append(ev["event_id"])
    for ids in by_anchor.values():
        for a, b in zip(ids, ids[1:]):
            g.add_edge(a, b)
    key: dict[tuple, list[dict]] = {}
    for ev in events:
        key.setdefault((ev["file_id"], ev["event_type"], ev["actor_id"]), []).append(ev)
    for group in key.values():
        group.sort(key=lambda e: e["corrected_timestamp_epoch"])
        for a, b in zip(group, group[1:]):
            if abs(b["corrected_timestamp_epoch"] - a["corrected_timestamp_epoch"]) \
                    <= C.REDUNDANCY_WINDOW_S:
                g.add_edge(a["event_id"], b["event_id"])
    return [sorted(c) for c in nx.connected_components(g)]


def compare(events, entity_res, kin, fin) -> dict:
    prof = set()
    swap = next((d for d in entity_res["detectors"] if d["code"] == "SIM_SWAP_DETECTED"), None)
    chosen_cluster = None
    for cl in entity_res["clusters"]:
        if swap and any(n in cl["members"] for n in swap["nodes"][1:]):
            chosen_cluster = cl
            break
    if chosen_cluster is None and entity_res["clusters"]:
        chosen_cluster = entity_res["clusters"][0]
    if chosen_cluster:
        prof = set(chosen_cluster["members"])
    ctx = {"profile_nodes": prof,
           "spoofed": {a["flagged_event"] for a in kin["anomalies"]
                       if a["code"] == "DIGITAL_LOCATION_SPOOF"},
           "split_custody": {a["flagged_event"] for a in kin["anomalies"]
                             if a["code"] == "SPLIT_CUSTODY_ANOMALY"},
           "mules": {m["account"] for m in fin["mules"]}}

    scored = {}
    for ev in events:
        band, sup, why = _rule(ev, ctx)
        if band is None:
            continue
        scored[ev["event_id"]] = {
            "event_id": ev["event_id"], "file_id": ev["file_id"],
            "event_type": ev["event_type"], "band": band, "support": sup,
            "rationale": why, "t": ev["corrected_timestamp_epoch"],
            "narrative": ev["narrative"],
        }
    clusters = [c for c in redundancy_clusters(events) if any(i in scored for i in c)]
    totals = {h["id"]: 0 for h in HYPOTHESES}
    cluster_rows = []
    for ci, members in enumerate(clusters, 1):
        items = [scored[i] for i in members if i in scored]
        row = {"cluster_id": f"C{ci}", "event_ids": [i["event_id"] for i in items],
               "representative": None, "support": {}, "band": None, "rationale": None,
               "redundant_count": len(items)}
        for h in HYPOTHESES:
            best = max(items, key=lambda it: (abs(it["support"][h["id"]]),
                                              -it["t"]))
            s = best["support"][h["id"]]
            row["support"][h["id"]] = s
            totals[h["id"]] += s
            if h["id"] == "H1":
                row["representative"] = best["event_id"]
                row["band"] = best["band"]
                row["rationale"] = best["rationale"]
                row["narrative"] = best["narrative"]
        cluster_rows.append(row)
    cluster_rows.sort(key=lambda r: -abs(r["support"]["H1"]))
    ranked = sorted(HYPOTHESES, key=lambda h: -totals[h["id"]])
    return {"hypotheses": [{**h, "support": totals[h["id"]]} for h in HYPOTHESES],
            "ranked": [h["id"] for h in ranked], "totals": totals,
            "clusters": cluster_rows, "scored_event_count": len(scored),
            "cluster_count": len(clusters),
            "profile_cluster": chosen_cluster["cluster_id"] if chosen_cluster else None}
