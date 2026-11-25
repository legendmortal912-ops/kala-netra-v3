"""KALA-NETRA V3 - pipeline orchestrator, SQLite persistence and verification."""
from __future__ import annotations
import json, os, sqlite3, time
from datetime import datetime, timezone

from . import config as C
from . import ingest as ing
from . import clocksync, entity, kinematic, causal, finance, hypothesis, narrative

_CASE: dict | None = None


# ----------------------------------------------------------------- run -------
def run(data_dir: str | None = None, excluded_files: list[str] | None = None,
        excluded_events: list[str] | None = None, persist: bool = True) -> dict:
    t0 = time.time()
    data_dir = data_dir or C.DATA_DIR
    excluded_files = set(excluded_files or [])
    excluded_events = set(excluded_events or [])

    files, events, media = ing.ingest_all(data_dir)
    files = [f for f in files if f["file_id"] not in excluded_files]
    events = [e for e in events
              if e["file_id"] not in excluded_files and e["event_id"] not in excluded_events]
    media = [m for m in media if m["linked_event_id"] not in excluded_events]

    sync = clocksync.synchronise(files, events)
    ent = entity.run(events)
    kin = kinematic.analyse(events, ent["clusters"])
    cau = causal.build(events, ent["detectors"], clusters=ent["clusters"])
    fin = finance.analyse(events)
    hyp = hypothesis.compare(events, ent, kin, fin)
    nar = narrative.build(events, files, cau, kin, fin, ent)

    G = ent["graph"]
    graph_payload = {
        "nodes": [{"id": n, "type": d["ntype"], "label": d["nid"],
                   "degree": G.degree(n), "events": len(d.get("events", [])),
                   "cluster": next((c["cluster_id"] for c in ent["clusters"]
                                    if n in c["members"]), None)}
                  for n, d in G.nodes(data=True)],
        "edges": [{"source": u, "target": v, "etype": d.get("etype"),
                   "event_id": d.get("ev_id"), "t": d.get("t")}
                  for u, v, d in G.edges(data=True)],
        "entity_links": [{"source": l["u"], "target": l["v"], "score": l["link_score"],
                          "basis": l["basis"]} for l in ent["links"]],
    }

    case = {
        "case_id": C.CASE_ID, "case_title": C.CASE_TITLE,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runtime_ms": round((time.time() - t0) * 1000, 1),
        "excluded_files": sorted(excluded_files), "excluded_events": sorted(excluded_events),
        "files": [{k: v for k, v in f.items() if k != "leaves"} for f in files],
        "leaves": {f["file_id"]: f["leaves"] for f in files},
        "events": events, "media": media, "clock": sync, "entity": ent,
        "kinematic": kin, "causal": cau, "finance": fin, "hypotheses": hyp,
        "narrative": nar, "graph": graph_payload,
        "counts": {"events": len(events), "files": len(files),
                   "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                   "entity_links": len(ent["links"]), "clusters": len(ent["clusters"]),
                   "anchors": sync["anchor_count"],
                   "causal_edges": len(cau["storyline"]),
                   "anomalies": len(kin["anomalies"]), "mules": len(fin["mules"])},
    }
    if persist:
        persist_sqlite(case)
        global _CASE
        _CASE = case
    return case


def get_case(reload: bool = False) -> dict:
    global _CASE
    if _CASE is None or reload:
        _CASE = run()
    return _CASE


# --------------------------------------------------------- serialisation -----
def public(case: dict) -> dict:
    """The case minus heavy internals (NetworkX objects, Merkle leaf arrays)."""
    ent = {k: v for k, v in case["entity"].items() if k not in ("graph", "resolver")}
    return {**{k: v for k, v in case.items() if k not in ("entity", "leaves", "events")},
            "entity": ent}


# ------------------------------------------------------------- persistence ---
SCHEMA = """
DROP TABLE IF EXISTS evidence_file; DROP TABLE IF EXISTS canonical_event;
DROP TABLE IF EXISTS clock_anchor;  DROP TABLE IF EXISTS entity_link;
DROP TABLE IF EXISTS entity_cluster;DROP TABLE IF EXISTS causal_edge;
DROP TABLE IF EXISTS hypothesis_support; DROP TABLE IF EXISTS narrative_step;
DROP TABLE IF EXISTS media_integrity;
CREATE TABLE evidence_file(file_id TEXT PRIMARY KEY, filename TEXT, label TEXT,
  size_bytes INT, sha256_file TEXT, merkle_root TEXT, record_count INT,
  line_terminator TEXT, sigma_s REAL, estimated_clock_offset_sec REAL,
  is_clock_anchored INT, anchor_count INT);
CREATE TABLE canonical_event(event_id TEXT PRIMARY KEY, file_id TEXT, record_index INT,
  byte_offset_start INT, byte_offset_end INT, leaf_sha256 TEXT, raw_timestamp_utc TEXT,
  raw_epoch REAL, corrected_timestamp_epoch REAL, event_type TEXT, actor_type TEXT,
  actor_id TEXT, target_type TEXT, target_id TEXT, lat REAL, lon REAL, r_e REAL,
  amount_inr REAL, anchor_key_type TEXT, anchor_key TEXT, device_id TEXT,
  narrative_template_body TEXT, extra_json TEXT);
CREATE TABLE clock_anchor(anchor_id TEXT, anchor_type TEXT, anchor_key TEXT, file_i TEXT,
  file_j TEXT, tau_i REAL, tau_j REAL, weight REAL, residual_s REAL, z REAL, used INT,
  event_i TEXT, event_j TEXT);
CREATE TABLE entity_link(u TEXT, v TEXT, link_score REAL, basis TEXT, s_exact REAL,
  s_str REAL, s_struct REAL, s_st REAL, distinct_sites INT, detail_json TEXT);
CREATE TABLE entity_cluster(cluster_id TEXT, member TEXT, member_type TEXT, member_id TEXT);
CREATE TABLE causal_edge(src TEXT, dst TEXT, cause_type TEXT, effect_type TEXT, dt_s REAL,
  causal_score REAL, in_storyline INT, label TEXT);
CREATE TABLE hypothesis_support(hypothesis_id TEXT, title TEXT, support INT);
CREATE TABLE narrative_step(idx INT, event_id TEXT, text TEXT, citation TEXT);
CREATE TABLE media_integrity(file TEXT, sha256 TEXT, container TEXT, flags_json TEXT,
  exif_json TEXT, linked_event_id TEXT);
"""


def persist_sqlite(case: dict, db_path: str | None = None) -> str:
    db_path = db_path or C.DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executemany(
        "INSERT INTO evidence_file VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(f["file_id"], f["filename"], f["label"], f["size_bytes"], f["sha256_file"],
          f["merkle_root"], f["record_count"], f["line_terminator"], f["sigma_s"],
          f["estimated_clock_offset_sec"], f["is_clock_anchored"], f["anchor_count"])
         for f in case["files"]])
    con.executemany(
        "INSERT INTO canonical_event VALUES (" + ",".join("?" * 23) + ")",
        [(e["event_id"], e["file_id"], e["record_index"], e["byte_offset_start"],
          e["byte_offset_end"], e["leaf_sha256"], e["raw_timestamp_utc"], e["raw_epoch"],
          e["corrected_timestamp_epoch"], e["event_type"], e["actor_type"], e["actor_id"],
          e["target_type"], e["target_id"], e["lat"], e["lon"], e["r_e"], e["amount_inr"],
          e["anchor_key_type"], e["anchor_key"], e["device_id"], e["narrative"],
          json.dumps(e["extra"])) for e in case["events"]])
    con.executemany(
        "INSERT INTO clock_anchor VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(a["anchor_id"], a["anchor_type"], a["anchor_key"], a["file_i"], a["file_j"],
          a["tau_i"], a["tau_j"], a["weight"], a["residual_s"], a["z"], int(a["used"]),
          a["event_i"], a["event_j"]) for a in case["clock"]["anchors"]])
    con.executemany(
        "INSERT INTO entity_link VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(l["u"], l["v"], l["link_score"], l["basis"], l["s_exact"], l["s_str"],
          l["s_struct"], l["s_st"], l["distinct_sites"],
          json.dumps({"shared_hubs": l["shared_hubs"], "colocations": l["colocations"],
                      "co_record_events": l["co_record_events"]}))
         for l in case["entity"]["links"]])
    con.executemany(
        "INSERT INTO entity_cluster VALUES (?,?,?,?)",
        [(c["cluster_id"], m, d["type"], d["id"])
         for c in case["entity"]["clusters"]
         for m, d in zip(c["members"], c["member_detail"])])
    story = {(e["src"], e["dst"]) for e in case["causal"]["storyline"]}
    con.executemany(
        "INSERT INTO causal_edge VALUES (?,?,?,?,?,?,?,?)",
        [(e["src"], e["dst"], e["cause_type"], e["effect_type"], e["dt_s"],
          e["causal_score"], int((e["src"], e["dst"]) in story), e["label"])
         for e in case["causal"]["edges"]])
    con.executemany("INSERT INTO hypothesis_support VALUES (?,?,?)",
                    [(h["id"], h["title"], h["support"]) for h in case["hypotheses"]["hypotheses"]])
    con.executemany("INSERT INTO narrative_step VALUES (?,?,?,?)",
                    [(s["index"], s["event_id"], s["text"], s["citation"])
                     for s in case["narrative"]["steps"]])
    con.executemany("INSERT INTO media_integrity VALUES (?,?,?,?,?,?)",
                    [(m["file"], m["sha256"], m["container"], json.dumps(m["flags"]),
                      json.dumps(m.get("exif", {})), m["linked_event_id"])
                     for m in case["media"]])
    con.commit()
    con.close()
    return db_path


# ------------------------------------------------------------ verification ---
def provenance(case: dict, event_id: str, data_dir: str | None = None) -> dict:
    data_dir = data_dir or C.DATA_DIR
    ev = next((e for e in case["events"] if e["event_id"] == event_id), None)
    if ev is None:
        return {"error": "unknown event_id"}
    f = next(x for x in case["files"] if x["file_id"] == ev["file_id"])
    with open(os.path.join(data_dir, f["filename"]), "rb") as fh:
        raw = fh.read()
    sl = raw[ev["byte_offset_start"]:ev["byte_offset_end"]]
    recomputed = ing.leaf_hash(sl)
    leaves = case["leaves"][ev["file_id"]]
    proof = ing.merkle_proof(leaves, ev["record_index"])
    return {
        "event_id": event_id, "file_id": ev["file_id"], "filename": f["filename"],
        "byte_offset_start": ev["byte_offset_start"], "byte_offset_end": ev["byte_offset_end"],
        "raw_bytes": sl.decode("utf-8", errors="replace"),
        "leaf_sha256_stored": ev["leaf_sha256"], "leaf_sha256_recomputed": recomputed,
        "leaf_match": recomputed == ev["leaf_sha256"],
        "merkle_root": f["merkle_root"], "merkle_proof": proof,
        "proof_valid": ing.verify_proof(recomputed, proof, f["merkle_root"]),
        "file_sha256": f["sha256_file"],
        "raw_timestamp_utc": ev["raw_timestamp_utc"],
        "clock_offset_applied_sec": f["estimated_clock_offset_sec"],
        "corrected_timestamp_utc": narrative.fmt_utc(ev["corrected_timestamp_epoch"]) + " UTC",
    }


def verify_all(case: dict, data_dir: str | None = None) -> dict:
    data_dir = data_dir or C.DATA_DIR
    ok = bad = 0
    failures = []
    cache: dict[str, bytes] = {}
    for f in case["files"]:
        with open(os.path.join(data_dir, f["filename"]), "rb") as fh:
            cache[f["file_id"]] = fh.read()
    for ev in case["events"]:
        raw = cache[ev["file_id"]]
        sl = raw[ev["byte_offset_start"]:ev["byte_offset_end"]]
        h = ing.leaf_hash(sl)
        proof = ing.merkle_proof(case["leaves"][ev["file_id"]], ev["record_index"])
        root = next(x["merkle_root"] for x in case["files"] if x["file_id"] == ev["file_id"])
        if h == ev["leaf_sha256"] and ing.verify_proof(h, proof, root):
            ok += 1
        else:
            bad += 1
            failures.append(ev["event_id"])
    files_ok = all(ing.sha256(cache[f["file_id"]]) == f["sha256_file"] for f in case["files"])
    return {"events_verified": ok, "events_failed": bad,
            "verification_rate": round(100.0 * ok / max(1, ok + bad), 4),
            "file_digests_match": files_ok, "failures": failures[:20]}


# --------------------------------------------------------- counterfactual ----
def counterfactual(excluded_files=None, excluded_events=None) -> dict:
    base = get_case()
    alt = run(excluded_files=excluded_files, excluded_events=excluded_events, persist=False)
    d_support = {h: alt["hypotheses"]["totals"].get(h, 0) for h in base["hypotheses"]["totals"]}
    delta = {h: base["hypotheses"]["totals"][h] - d_support[h] for h in d_support}
    base_links = {(l["u"], l["v"]) for l in base["entity"]["links"]}
    alt_links = {(l["u"], l["v"]) for l in alt["entity"]["links"]}
    base_causal = {(e["src"], e["dst"]) for e in base["causal"]["storyline"]}
    alt_causal = {(e["src"], e["dst"]) for e in alt["causal"]["storyline"]}
    return {
        "excluded_files": sorted(excluded_files or []),
        "excluded_events": sorted(excluded_events or []),
        "runtime_ms": alt["runtime_ms"],
        "support_before": base["hypotheses"]["totals"],
        "support_after": d_support, "delta_support": delta,
        "severed_entity_links": [{"u": u, "v": v} for u, v in sorted(base_links - alt_links)],
        "severed_causal_edges": [{"src": s, "dst": d} for s, d in sorted(base_causal - alt_causal)],
        "new_entity_links": [{"u": u, "v": v} for u, v in sorted(alt_links - base_links)],
        "clock": {"before": base["clock"]["beta"], "after": alt["clock"]["beta"],
                  "rmse_before": base["clock"]["rmse_clock"],
                  "rmse_after": alt["clock"]["rmse_clock"],
                  "unanchored_after": alt["clock"]["unanchored_sources"]},
        "counts_before": base["counts"], "counts_after": alt["counts"],
        "anomalies_after": len(alt["kinematic"]["anomalies"]),
        "mules_after": len(alt["finance"]["mules"]),
        "clusters_after": [c["cluster_id"] + ": " + ", ".join(m["id"] for m in c["member_detail"])
                           for c in alt["entity"]["clusters"]],
    }
