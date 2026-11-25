"""KALA-NETRA V3 - Section 5: spatio-temporal kinematic plausibility and
alibi-spoofing classification."""
from __future__ import annotations
import math
from . import config as C
from .entity import haversine, nkey


def _layer(etype: str) -> str:
    if etype in C.APP_LAYER:
        return "APPLICATION"
    if etype in C.PHYSICAL_LAYER:
        return "PHYSICAL"
    return "OTHER"


def trajectory(cluster_members, events_by_actor):
    pts = []
    for m in cluster_members:
        for ev in events_by_actor.get(m, []):
            if ev["lat"] is None or ev["lon"] is None:
                continue
            pts.append({"event_id": ev["event_id"], "t": ev["corrected_timestamp_epoch"],
                        "lat": ev["lat"], "lon": ev["lon"],
                        "r": ev["r_e"] or C.UNCERTAINTY_R["DEFAULT"],
                        "etype": ev["event_type"], "file_id": ev["file_id"],
                        "actor": m, "layer": _layer(ev["event_type"])})
    pts.sort(key=lambda p: (p["t"], p["event_id"]))
    return pts


def analyse(events: list[dict], clusters: list[dict]) -> dict:
    by_actor: dict[str, list[dict]] = {}
    for ev in events:
        if ev["actor_type"] and ev["actor_id"]:
            by_actor.setdefault(nkey(ev["actor_type"], ev["actor_id"]), []).append(ev)

    out_tracks, anomalies = [], []
    for cl in clusters:
        traj = trajectory(cl["members"], by_actor)
        out_tracks.append({"cluster_id": cl["cluster_id"], "points": traj})

        # ---- pass 1: falsified digital alibi -------------------------------
        # An application-layer fix is contradicted when the NEAREST bracketing
        # physical-layer radio records on both sides are kinematically
        # unreachable from it. Physical RF association (cell attach, Wi-Fi
        # association, ATM actuator) cannot be spoofed remotely.
        spoofed = set()
        for k, b in enumerate(traj):
            if b["layer"] != "APPLICATION":
                continue
            prev = next((traj[i] for i in range(k - 1, -1, -1)
                         if traj[i]["layer"] == "PHYSICAL"), None)
            nxt = next((traj[i] for i in range(k + 1, len(traj))
                        if traj[i]["layer"] == "PHYSICAL"), None)
            if prev is None or nxt is None:
                continue
            worst = None
            for other in (prev, nxt):
                d = haversine(b["lat"], b["lon"], other["lat"], other["lon"])
                dmin = max(0.0, d - (b["r"] + other["r"])) * C.KAPPA_ROAD
                dt = abs(other["t"] - b["t"])
                v = dmin / max(1.0, dt)
                K = max(0.0, v / C.V_MAX - 1.0)
                if K > 0 and (worst is None or K > worst[0]):
                    worst = (K, other, d, dmin, dt, v)
            if worst is None:
                continue
            K, other, d, dmin, dt, v = worst
            spoofed.add(b["event_id"])
            anomalies.append({
                "code": "DIGITAL_LOCATION_SPOOF", "severity": "CRITICAL",
                "cluster_id": cl["cluster_id"], "event_from": prev["event_id"],
                "event_to": nxt["event_id"], "flagged_event": b["event_id"],
                "d_hav_m": round(d, 1), "d_min_m": round(dmin, 1), "dt_s": round(dt, 1),
                "v_req_ms": round(v, 2), "v_max_ms": C.V_MAX, "kinematic_score": round(K, 3),
                "from_layer": prev["layer"], "to_layer": b["layer"],
                "from_type": prev["etype"], "to_type": b["etype"],
                "detail": (f'application-layer fix {b["event_id"]} ({b["etype"]}) is bracketed by '
                           f'physical-layer records {prev["event_id"]} ({prev["etype"]}) and '
                           f'{nxt["event_id"]} ({nxt["etype"]}); reaching it would require '
                           f'{v:.0f} m/s against a {C.V_MAX:.1f} m/s ceiling, so the fix is a '
                           f'falsified digital alibi'),
            })

        # ---- pass 2: consecutive-transition plausibility -------------------
        for k in range(len(traj) - 1):
            a, b = traj[k], traj[k + 1]
            if a["event_id"] in spoofed or b["event_id"] in spoofed:
                continue
            d = haversine(a["lat"], a["lon"], b["lat"], b["lon"])
            dmin = max(0.0, d - (a["r"] + b["r"])) * C.KAPPA_ROAD
            dt = abs(b["t"] - a["t"])
            v = dmin / max(1.0, dt)
            K = max(0.0, v / C.V_MAX - 1.0)
            if K <= 0:
                continue
            if a["layer"] == "PHYSICAL" and b["layer"] == "PHYSICAL" and a["actor"] != b["actor"]:
                code, sev = "SPLIT_CUSTODY_ANOMALY", "HIGH"
                target, detail = b, (
                    f'two distinct physical devices of the same resolved profile '
                    f'({a["actor"]} and {b["actor"]}) produced physical-layer records '
                    f'{dmin/1000:.2f} km apart within {dt:.0f} s')
            else:
                code, sev = "IMPOSSIBLE_TRANSITION", "MEDIUM"
                target, detail = b, "transition exceeds the maximum plausible ground velocity"
            anomalies.append({
                "code": code, "severity": sev, "cluster_id": cl["cluster_id"],
                "event_from": a["event_id"], "event_to": b["event_id"],
                "flagged_event": target["event_id"],
                "d_hav_m": round(d, 1), "d_min_m": round(dmin, 1), "dt_s": round(dt, 1),
                "v_req_ms": round(v, 2), "v_max_ms": C.V_MAX, "kinematic_score": round(K, 3),
                "detail": detail,
                "from_layer": a["layer"], "to_layer": b["layer"],
                "from_type": a["etype"], "to_type": b["etype"],
            })
    anomalies.sort(key=lambda x: -x["kinematic_score"])
    return {"tracks": out_tracks, "anomalies": anomalies,
            "spoofed_events": sorted({a["flagged_event"] for a in anomalies
                                      if a["code"] == "DIGITAL_LOCATION_SPOOF"})}
