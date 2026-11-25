<div align="center">

# KALA‑NETRA · V3

**Deterministic, air‑gapped forensic correlation & crime‑reconstruction engine**

Six heterogeneous evidence sources → one byte‑provable UTC timeline → resolved suspect profiles →
causal attack chain → money trail → court‑ready **BSA 2023 §63(4)(c)** certificate.

`FastAPI` · `NetworkX` · `NumPy` · `SciPy` · `SQLite` · `ReportLab` — **no model weights, no training data, no network calls**

</div>

---

## Run it

```bash
python run.py
```

That is the whole thing. The launcher installs any missing dependency, generates the benchmark
evidence set on first run, executes the full pipeline, prints the benchmark scorecard and opens the
console at **http://127.0.0.1:8000**.

Prefer an explicit install? `pip install -r requirements.txt && python run.py`

| command | what it does |
|---|---|
| `python run.py` | install → generate → correlate → benchmark → serve console |
| `python eval.py` | benchmark scorecard only, writes `out/benchmark_report.json` |
| `python run.py --regenerate` | rebuild the synthetic evidence set from scratch |
| `python run.py --eval-only` | pipeline + scorecard, no server |
| `python run.py --port 9000 --no-browser` | serve elsewhere, don't open a browser |

Requires Python 3.10+. Everything runs offline; the only network traffic is the optional one‑time
`pip install`.

---

## What the console shows

| view | contents |
|---|---|
| **Overview** | leading hypothesis, exhibit manifest with SHA‑256 + Merkle roots, every forensic alert, EXIF tamper findings and the seized frame |
| **Reconstruction** | the citation‑locked narrative — click any step to re‑read its exact bytes from disk and validate its Merkle inclusion proof |
| **Evidence ledger** | all 619 parsed records, searchable, each bound to a byte range |
| **Clock sync** | recovered offsets β, the identity‑free anchor set, residuals and z‑scores |
| **Entity network** | interactive graph of the resolved profiles with the full four‑signal score decomposition per link |
| **Kinematics** | impossible transitions, the falsified GPS alibi, split device custody, trajectory map |
| **Money flow** | siphon topology, pass‑through scoring, Edmonds‑Karp max‑flow attribution |
| **Hypotheses** | ordinal support per competing explanation over de‑duplicated evidentiary clusters |
| **Counterfactual** | switch an exhibit off and watch which links and causal edges are severed |
| **Query copilot** | natural language → JSON query AST (local Ollama if present, deterministic regex otherwise) |
| **Benchmark** | every metric, recomputed live |

---

## Benchmark scorecard

Reproduced on every run by `python eval.py` against `data/ground_truth.json`:

| metric | result | target |
|---|---|---|
| Clock‑offset estimation **RMSE β** | **0.749 s** | ≤ 1.8 s, despite a +360 s DVR skew and +45 s handset skew |
| Entity resolution **F1** (pairwise, transitive closure) | **1.000** | P 1.000 / R 1.000 |
| Causal attack‑chain edge **F1** | **1.000** | 21/21 ground‑truth edges |
| Falsified GPS alibi recall | **100 %** | 𝒦 = 122.3 on the Mumbai ping |
| Mule identification recall / precision | **100 % / 100 %** | all three mules score ≥ 0.82 |
| Max‑flow attribution | **₹4,44,000.00** | exact match to ground truth |
| Cryptographic provenance verification | **100.0 %** | 619/619 byte ranges re‑read and Merkle‑validated |
| Citation precision · hallucination rate | **100 % · 0 %** | no generative model in the evidential path |

---

## Architecture

```
run.py                 one-command launcher (deps → data → pipeline → benchmark → server)
eval.py                benchmark wrapper
backend/
  config.py            every threshold and constant in one auditable place
  generate_data.py     synthetic benchmark generator + ground truth
  ingest.py            §2  binary ingestion, byte offsets, RFC 6962 Merkle, EXIF integrity
  clocksync.py         §3  non-circular weighted-Laplacian clock solver
  entity.py            §4  training-free multi-modal entity resolution
  kinematic.py         §5  kinematic plausibility & alibi-spoof classification
  causal.py            §6A rule-based causal chain + max-weight spanning arborescence
  finance.py           §6B mule-flow, pass-through velocity, Edmonds-Karp attribution
  hypothesis.py        §7  redundancy-clustered ordinal hypothesis comparator
  narrative.py         §8A deterministic citation-locked narrative
  copilot.py           §8B air-gapped NL → JSON query AST (Ollama, regex fallback)
  report.py            §8C ReportLab dossier + BSA §63(4)(c) SCHEDULE
  pipeline.py          orchestration, SQLite persistence, verification, counterfactual
  eval.py              §9A benchmark suite
  app.py               FastAPI surface + static console
frontend/              zero-build single-page console (no CDN, no bundler)
data/                  6 exhibits + tampered JPEG + causal_rules.json + ground_truth.json
out/                   kala_netra.sqlite, benchmark_report.json, generated PDF
```

### The scenario

*The Coordinated SIM‑Swap & Mule Cash‑Out Heist* — Connaught Place and Nehru Place, New Delhi,
18 November 2026, 13:20–16:00 UTC. 619 records across six exhibits with deliberately injected
clock skew, OCR homoglyph corruption, 200 background subscribers, 150 background Wi‑Fi
associations, 120 benign UPI transfers, deleted SQLite call‑log rows, a mock‑location alibi and a
re‑encoded CCTV frame with a two‑hour EXIF shift.

### Why it is defensible in court

1. **Byte‑bound provenance.** Every exhibit is opened with `open(path, "rb")`, so a CRLF terminator
   stays two bytes and every citation in the dossier can be re‑read from the raw file. Leaves are
   hashed with a `0x00` domain prefix and internal nodes with `0x01` (RFC 6962), blocking
   second‑preimage substitution.
2. **Non‑circular synchronisation.** Clocks are reconciled *before* entity resolution, using only
   identity‑free infrastructure anchors — SMS PDU hash, NPCI RRN, ATM dispenser trigger counter,
   DHCP transaction id, kernel radio uptime. No attribution decision can leak into the timeline.
   Anchors with a standardised residual above 3.5 are dropped and the system re‑solved.
3. **Interpretable fusion.** Entity resolution is four explicit scores — deterministic co‑record
   device binding, OCR homoglyph‑canonicalised string match, meta‑path Adamic‑Adar over shared
   low‑degree hubs, and uncertainty‑buffered spatio‑temporal co‑occurrence. Every accepted link
   exposes its full decomposition, including which hubs and which co‑locations produced it.
4. **No probability of guilt.** The comparator reports ordinal support on a published scale over
   de‑duplicated evidentiary clusters, so one fact logged by two systems is never counted twice.
5. **No generative model in the evidential path.** The narrative is Python template interpolation
   over verified database columns. The optional local LLM only converts a question into a query
   filter, never into a finding, and a regex parser takes over whenever it is absent or slow.

### Calibrated parameters

Two constants are calibrated on this benchmark rather than taken from the specification, and both
are recorded in `backend/config.py` where a reviewer can change them and re‑run:

* `W_STRUCT / W_ST = 0.40 / 0.60` — pure co‑travel evidence (a vehicle plate and a handset) carries
  no shared‑hub signal at all, so the structural term cannot be allowed to dominate.
* `CONVOY_MIN_SITES = 3` with `CONVOY_MIN_SCORE = 0.70` — co‑location across three or more
  distinct sites, separated by at least 1 km, is treated as independently sufficient. Raw
  Jaro‑Winkler is likewise restricted to the vehicle‑plate namespace, because edit similarity
  between account handles or IMEIs is meaningless and produces false links.

---

## Deployment roadmap

* **Phase 1 — FSL / Cyber Police Station triage kit (TRL‑6).** Zero‑internet bundle
  (PyInstaller + local SQLite + offline basemap) on standard Windows forensic workstations;
  ingests case folders from write‑blocked USB evidence drives and emits the §63(4)(c) draft in
  under 30 seconds.
* **Phase 2 — State Cyber Coordination Centre appliance (6–12 months, TRL‑7).** Air‑gapped Docker
  appliance inside State Police data centres with role‑based access (IO / FSL examiner /
  supervisory SP) and HSM signing of the Merkle audit ledger; streaming parsers for Cellebrite
  `.ufdr`, Oxygen exports and multi‑operator tower dumps.
* **Phase 3 — National integration (12–24 months, TRL‑8).** Secure REST adapters into I4C/NCRP for
  cross‑state mule topologies, and signed §63(4)(c) schedules pushed into ICJS/CCTNS e‑filing.

---

## API

Interactive docs at `/api/docs`.

```
GET  /api/v1/case                     case summary, exhibits, alerts, hypotheses
GET  /api/v1/events                   parsed records (file_id, event_type, q, limit, offset)
GET  /api/v1/timeline                 citation-locked narrative steps
GET  /api/v1/clock                    offsets β, anchor set, residuals
GET  /api/v1/entity | /graph          links with score decomposition, clusters, detectors
GET  /api/v1/kinematic | /finance | /causal | /hypotheses
GET  /api/v1/provenance/{event_id}    raw bytes + re-hash + Merkle inclusion proof
GET  /api/v1/verify                   re-verify every cited byte range
GET  /api/v1/metrics                  full benchmark report
POST /api/v1/counterfactual           {"excluded_files": ["SRC_CCTV_01"]}
POST /api/v1/query                    {"question": "...", "use_llm": true}
GET  /api/v1/export-section63-pdf     court-ready dossier
```
