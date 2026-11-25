"""KALA-NETRA V3 - FastAPI application (air-gapped: no outbound calls)."""
from __future__ import annotations
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config as C
from . import pipeline, report, copilot
from . import eval as evaluator

app = FastAPI(title="KALA-NETRA V3",
              description="Deterministic, air-gapped forensic correlation and crime "
                          "reconstruction engine",
              version="3.0.0", docs_url="/api/docs", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])
API = "/api/v1"
FRONTEND = os.path.join(C.ROOT, "frontend")


@app.on_event("startup")
def _startup():
    if not os.path.exists(C.GROUND_TRUTH):
        from . import generate_data
        generate_data.generate()
    pipeline.get_case()


def case():
    return pipeline.get_case()


# -------------------------------------------------------------------- core --
@app.get(API + "/case")
def get_case():
    c = case()
    return {"case_id": c["case_id"], "case_title": c["case_title"],
            "generated_at": c["generated_at"], "runtime_ms": c["runtime_ms"],
            "counts": c["counts"], "files": c["files"], "media": c["media"],
            "clock": {k: v for k, v in c["clock"].items() if k != "anchors"},
            "detectors": c["entity"]["detectors"],
            "highlights": c["narrative"]["highlights"],
            "hypotheses": c["hypotheses"]["hypotheses"],
            "ranked": c["hypotheses"]["ranked"],
            "config": {"link_threshold": C.LINK_THRESHOLD, "v_max_ms": C.V_MAX,
                       "mule_threshold": C.MULE_SCORE_MIN,
                       "causal_min_score": C.CAUSAL_MIN_SCORE,
                       "w_struct": C.W_STRUCT, "w_st": C.W_ST,
                       "anchor_residual_z": C.ANCHOR_RESIDUAL_Z}}


@app.get(API + "/files")
def get_files():
    return case()["files"]


@app.get(API + "/events")
def get_events(file_id: Optional[str] = None, event_type: Optional[str] = None,
               q: Optional[str] = None, limit: int = Query(400, le=2000), offset: int = 0):
    evs = case()["events"]
    if file_id:
        evs = [e for e in evs if e["file_id"] == file_id]
    if event_type:
        evs = [e for e in evs if e["event_type"] == event_type]
    if q:
        ql = q.lower()
        evs = [e for e in evs if ql in (e["narrative"] + e["actor_id"] + e["target_id"]
                                        + e["event_id"]).lower()]
    evs = sorted(evs, key=lambda e: e["corrected_timestamp_epoch"])
    page = evs[offset:offset + limit]
    keys = ("event_id", "file_id", "event_type", "actor_type", "actor_id", "target_type",
            "target_id", "lat", "lon", "r_e", "amount_inr", "raw_timestamp_utc",
            "corrected_timestamp_epoch", "byte_offset_start", "byte_offset_end",
            "leaf_sha256", "narrative", "anchor_key_type", "anchor_key")
    return {"total": len(evs), "offset": offset, "limit": limit,
            "event_types": sorted({e["event_type"] for e in case()["events"]}),
            "events": [{k: e[k] for k in keys} for e in page]}


@app.get(API + "/timeline")
def get_timeline():
    c = case()
    return {"steps": c["narrative"]["steps"], "highlights": c["narrative"]["highlights"],
            "citation_precision": c["narrative"]["citation_precision"],
            "hallucination_rate": c["narrative"]["hallucination_rate"],
            "generator": c["narrative"]["generator"],
            "storyline": c["causal"]["storyline"], "primary_root": c["causal"]["primary_root"]}


@app.get(API + "/clock")
def get_clock():
    c = case()
    return {**c["clock"], "files": [{k: f[k] for k in
                                     ("file_id", "filename", "label", "sigma_s",
                                      "estimated_clock_offset_sec", "is_clock_anchored",
                                      "anchor_count", "line_terminator")}
                                    for f in c["files"]]}


@app.get(API + "/entity")
def get_entity():
    e = case()["entity"]
    return {"links": e["links"], "clusters": e["clusters"], "detectors": e["detectors"],
            "near_misses": e["near_misses"]}


@app.get(API + "/graph")
def get_graph():
    return case()["graph"]


@app.get(API + "/kinematic")
def get_kinematic():
    return case()["kinematic"]


@app.get(API + "/finance")
def get_finance():
    return case()["finance"]


@app.get(API + "/causal")
def get_causal():
    c = case()["causal"]
    return {k: v for k, v in c.items() if k != "edges"} | {"edges": c["edges"]}


@app.get(API + "/hypotheses")
def get_hypotheses():
    return case()["hypotheses"]


@app.get(API + "/provenance/{event_id:path}")
def get_provenance(event_id: str):
    r = pipeline.provenance(case(), event_id)
    if "error" in r:
        raise HTTPException(404, r["error"])
    return r


@app.get(API + "/verify")
def get_verify():
    return pipeline.verify_all(case())


@app.get(API + "/metrics")
def get_metrics():
    return evaluator.evaluate(case())


class CFBody(BaseModel):
    excluded_files: list[str] = []
    excluded_events: list[str] = []


@app.post(API + "/counterfactual")
def post_counterfactual(body: CFBody):
    return pipeline.counterfactual(body.excluded_files, body.excluded_events)


class QBody(BaseModel):
    question: str
    use_llm: bool = True


@app.post(API + "/query")
def post_query(body: QBody):
    return copilot.query(body.question, case()["events"], use_llm=body.use_llm)


@app.post(API + "/reingest")
def post_reingest():
    c = pipeline.get_case(reload=True)
    return {"ok": True, "counts": c["counts"], "runtime_ms": c["runtime_ms"]}


@app.get(API + "/export-section63-pdf")
def export_pdf():
    c = case()
    path = report.build_pdf(c, metrics=evaluator.evaluate(c))
    return FileResponse(path, media_type="application/pdf",
                        filename="KALA_NETRA_BSA_Sec63_Dossier.pdf")


@app.get(API + "/raw/{file_id}")
def raw_file(file_id: str, start: int = 0, length: int = 2048):
    f = next((x for x in case()["files"] if x["file_id"] == file_id), None)
    if not f:
        raise HTTPException(404, "unknown exhibit")
    with open(os.path.join(C.DATA_DIR, f["filename"]), "rb") as fh:
        fh.seek(max(0, start))
        data = fh.read(min(length, 65536))
    return {"file_id": file_id, "filename": f["filename"], "start": start,
            "bytes": data.decode("utf-8", errors="replace")}


@app.get(API + "/frame/{name}")
def frame(name: str):
    p = os.path.join(C.DATA_DIR, os.path.basename(name))
    if not os.path.exists(p):
        raise HTTPException(404, "no such frame")
    return FileResponse(p)


@app.get("/health")
def health():
    return {"ok": True, "events": case()["counts"]["events"]}


if os.path.isdir(FRONTEND):
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
