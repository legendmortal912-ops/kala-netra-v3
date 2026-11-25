#!/usr/bin/env python3
"""Export a self-contained static demo bundle of KALA-NETRA V3 for GitHub Pages.

Runs the full deterministic pipeline and writes `dist/` containing:
  - frontend/ static files
  - static_api/*.json snapshots (case, timeline, clock, entity, graph, etc.)
  - static_api/provenance/<file_id>.json (per-record byte + Merkle proofs)
  - static_api/counterfactual.json (all non-empty subsets of exhibits)
  - static_api/frame/* (seized multimedia artifacts)
  - static_api/KALA_NETRA_BSA_Sec63_Dossier.pdf
"""
from __future__ import annotations
import itertools, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import config as C
from backend import eval as evaluator
from backend import generate_data, pipeline, report


def _dump(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))


def build_static(out_dir: str | None = None) -> str:
    out_dir = out_dir or os.path.join(ROOT, "dist")
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    frontend_dir = os.path.join(ROOT, "frontend")
    shutil.copytree(frontend_dir, out_dir)

    if not os.path.exists(C.GROUND_TRUTH):
        generate_data.generate()

    case = pipeline.get_case(reload=True)
    metrics = evaluator.evaluate(case)
    verify = pipeline.verify_all(case)

    api_dir = os.path.join(out_dir, "static_api")
    os.makedirs(api_dir, exist_ok=True)

    _dump(os.path.join(api_dir, "case.json"), {
        "case_id": case["case_id"], "case_title": case["case_title"],
        "generated_at": case["generated_at"], "runtime_ms": case["runtime_ms"],
        "counts": case["counts"], "files": case["files"], "media": case["media"],
        "clock": {k: v for k, v in case["clock"].items() if k != "anchors"},
        "detectors": case["entity"]["detectors"],
        "highlights": case["narrative"]["highlights"],
        "hypotheses": case["hypotheses"]["hypotheses"],
        "ranked": case["hypotheses"]["ranked"],
        "config": {
            "link_threshold": C.LINK_THRESHOLD, "v_max_ms": C.V_MAX,
            "mule_threshold": C.MULE_SCORE_MIN,
            "causal_min_score": C.CAUSAL_MIN_SCORE,
            "w_struct": C.W_STRUCT, "w_st": C.W_ST,
            "anchor_residual_z": C.ANCHOR_RESIDUAL_Z,
        },
    })

    _dump(os.path.join(api_dir, "timeline.json"), {
        "steps": case["narrative"]["steps"],
        "highlights": case["narrative"]["highlights"],
        "citation_precision": case["narrative"]["citation_precision"],
        "hallucination_rate": case["narrative"]["hallucination_rate"],
        "generator": case["narrative"]["generator"],
        "storyline": case["causal"]["storyline"],
        "primary_root": case["causal"]["primary_root"],
    })

    _dump(os.path.join(api_dir, "clock.json"), {
        **case["clock"],
        "files": [{k: f[k] for k in ("file_id", "filename", "label", "sigma_s",
                                     "estimated_clock_offset_sec", "is_clock_anchored",
                                     "anchor_count", "line_terminator")}
                  for f in case["files"]],
    })

    ent = case["entity"]
    _dump(os.path.join(api_dir, "entity.json"), {
        "links": ent["links"], "clusters": ent["clusters"],
        "detectors": ent["detectors"], "near_misses": ent["near_misses"],
    })
    _dump(os.path.join(api_dir, "graph.json"), case["graph"])
    _dump(os.path.join(api_dir, "kinematic.json"), case["kinematic"])
    _dump(os.path.join(api_dir, "finance.json"), case["finance"])
    _dump(os.path.join(api_dir, "hypotheses.json"), case["hypotheses"])
    _dump(os.path.join(api_dir, "metrics.json"), metrics)
    _dump(os.path.join(api_dir, "verify.json"), verify)

    ev_keys = ("event_id", "file_id", "event_type", "actor_type", "actor_id",
               "target_type", "target_id", "lat", "lon", "r_e", "amount_inr",
               "raw_timestamp_utc", "corrected_timestamp_epoch",
               "byte_offset_start", "byte_offset_end", "leaf_sha256",
               "narrative", "anchor_key_type", "anchor_key")
    sorted_evs = sorted(case["events"], key=lambda e: e["corrected_timestamp_epoch"])
    _dump(os.path.join(api_dir, "events.json"), {
        "event_types": sorted({e["event_type"] for e in case["events"]}),
        "events": [{k: e[k] for k in ev_keys} for e in sorted_evs],
    })

    by_file: dict[str, dict] = {}
    for ev in case["events"]:
        fid = ev["file_id"]
        by_file.setdefault(fid, {})[ev["event_id"]] = pipeline.provenance(case, ev["event_id"])
    for fid, payload in by_file.items():
        _dump(os.path.join(api_dir, "provenance", f"{fid}.json"), payload)

    fids = [f["file_id"] for f in case["files"]]
    cf_map = {}
    for r in range(1, len(fids) + 1):
        for combo in itertools.combinations(fids, r):
            key = "|".join(sorted(combo))
            cf_map[key] = pipeline.counterfactual(excluded_files=list(combo))
    _dump(os.path.join(api_dir, "counterfactual.json"), cf_map)

    frame_dir = os.path.join(api_dir, "frame")
    os.makedirs(frame_dir, exist_ok=True)
    for m in case["media"]:
        src = os.path.join(C.DATA_DIR, os.path.basename(m["file"]))
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(frame_dir, os.path.basename(m["file"])))

    pdf_path = os.path.join(api_dir, "KALA_NETRA_BSA_Sec63_Dossier.pdf")
    report.build_pdf(case, out_path=pdf_path, metrics=metrics)
    return out_dir


if __name__ == "__main__":
    dest = build_static()
    print(f"Static GitHub Pages bundle written to {dest}")
