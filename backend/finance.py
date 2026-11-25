"""KALA-NETRA V3 - Section 6B: financial mule-flow and pass-through velocity."""
from __future__ import annotations
import statistics, math
import networkx as nx
from . import config as C

TXN_TYPES = {"UPI_DEBIT_TXN", "UPI_MULE_HOP", "UPI_CREDIT_TXN", "ATM_CASH_WDL"}


def analyse(events: list[dict]) -> dict:
    txns = [e for e in events if e["event_type"] in TXN_TYPES and e["amount_inr"]]
    G = nx.DiGraph()
    legs = []
    for e in txns:
        a, b = e["actor_id"], (e["extra"] or {}).get("target_acct") or e["target_id"]
        if not a or not b:
            continue
        amt = float(e["amount_inr"])
        legs.append({"src": a, "dst": b, "amount": amt,
                     "t": e["corrected_timestamp_epoch"], "event_id": e["event_id"],
                     "etype": e["event_type"]})
        if G.has_edge(a, b):
            G[a][b]["amount"] += amt
            G[a][b]["events"].append(e["event_id"])
        else:
            G.add_edge(a, b, amount=amt, events=[e["event_id"]])

    inflow, outflow = {}, {}
    ins, outs = {}, {}
    for l in legs:
        inflow[l["dst"]] = inflow.get(l["dst"], 0.0) + l["amount"]
        outflow[l["src"]] = outflow.get(l["src"], 0.0) + l["amount"]
        ins.setdefault(l["dst"], []).append(l)
        outs.setdefault(l["src"], []).append(l)

    scores = []
    for acct in sorted(set(inflow) | set(outflow)):
        In, Out = inflow.get(acct, 0.0), outflow.get(acct, 0.0)
        if In <= 0 or Out <= 0:
            continue
        rho = min(In, Out) / (max(In, Out) + 1.0)
        holds = []
        for i in sorted(ins.get(acct, []), key=lambda x: x["t"]):
            nxt = [o for o in outs.get(acct, []) if o["t"] >= i["t"]]
            if nxt:
                holds.append(min(o["t"] for o in nxt) - i["t"])
        hold = statistics.median(holds) if holds else 0.0
        din = len({l["src"] for l in ins.get(acct, [])}) or 1
        dout = len({l["dst"] for l in outs.get(acct, [])}) or 1
        deg_in_legs = len(ins.get(acct, []))
        deg_out_legs = len(outs.get(acct, []))
        fan = 1.0 - 1.0 / (1.0 + deg_in_legs * deg_out_legs)
        score = rho * math.exp(-math.log(2) / C.MULE_HALF_LIFE * hold) * fan
        scores.append({"account": acct, "in_inr": round(In, 2), "out_inr": round(Out, 2),
                       "rho_flow": round(rho, 4), "hold_median_s": round(hold, 1),
                       "legs_in": deg_in_legs, "legs_out": deg_out_legs,
                       "counterparties_in": din, "counterparties_out": dout,
                       "fan_factor": round(fan, 4), "mule_score": round(score, 4),
                       "is_mule": score >= C.MULE_SCORE_MIN})
    scores.sort(key=lambda x: -x["mule_score"])

    # ------- max-flow attribution from victim to the cash-out account --------
    flow = None
    victim = next((e["actor_id"] for e in events if e["event_type"] == "UPI_DEBIT_TXN"), None)
    cash = next(((e["actor_id"]) for e in events if e["event_type"] == "ATM_CASH_WDL"
                 and (e["extra"] or {}).get("channel") == "ATM"
                 and float(e["amount_inr"] or 0) >= 100000), None)
    if victim and cash and victim in G and cash in G:
        H = nx.DiGraph()
        for u, v, d in G.edges(data=True):
            H.add_edge(u, v, capacity=round(d["amount"], 2))
        try:
            val, fdict = nx.maximum_flow(H, victim, cash, capacity="capacity")
            paths = [{"src": u, "dst": v, "flow": round(f, 2)}
                     for u, d in fdict.items() for v, f in d.items() if f > 0]
            flow = {"source": victim, "sink": cash, "traced_inr": round(val, 2),
                    "paths": sorted(paths, key=lambda p: -p["flow"])}
        except Exception as exc:
            flow = {"source": victim, "sink": cash, "error": str(exc)}

    return {"accounts": scores, "mules": [s for s in scores if s["is_mule"]],
            "graph_edges": [{"src": u, "dst": v, "amount": round(d["amount"], 2),
                             "events": d["events"]} for u, v, d in G.edges(data=True)],
            "max_flow": flow, "legs": legs,
            "total_debited_inr": round(sum(l["amount"] for l in legs
                                           if l["etype"] == "UPI_DEBIT_TXN"), 2)}
