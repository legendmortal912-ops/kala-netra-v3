#!/usr/bin/env python3
"""KALA-NETRA V3 — single-command launcher.

    python run.py

Installs any missing dependency, generates the benchmark evidence set on first
run, executes the full deterministic pipeline, prints the benchmark scorecard
and serves the console at http://127.0.0.1:8000
"""
from __future__ import annotations
import argparse, os, subprocess, sys, threading, time, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
REQUIRED = [("fastapi", "fastapi"), ("uvicorn", "uvicorn[standard]"), ("numpy", "numpy"),
            ("scipy", "scipy"), ("networkx", "networkx"), ("reportlab", "reportlab"),
            ("PIL", "pillow")]
C = {"d": "\033[2m", "c": "\033[96m", "g": "\033[92m", "y": "\033[93m",
     "r": "\033[91m", "b": "\033[1m", "0": "\033[0m"}
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    C = {k: "" for k in C}


def say(msg, k="0"):
    print(f'{C[k]}{msg}{C["0"]}', flush=True)


def ensure_deps(auto=True):
    missing = []
    for mod, pkg in REQUIRED:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return
    if not auto:
        say(f'missing dependencies: {" ".join(missing)}', "r")
        say("install them with:  pip install -r requirements.txt", "y")
        sys.exit(1)
    say(f'· installing {len(missing)} missing dependencies: {", ".join(missing)}', "y")
    cmd = [sys.executable, "-m", "pip", "install", "-q", *missing]
    if subprocess.call(cmd) != 0:
        subprocess.check_call([*cmd, "--break-system-packages"])
    say("· dependencies ready", "g")


def banner():
    say(r"""
   ██╗  ██╗ █████╗ ██╗      █████╗       ███╗   ██╗███████╗████████╗██████╗  █████╗
   ██║ ██╔╝██╔══██╗██║     ██╔══██╗      ████╗  ██║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗
   █████╔╝ ███████║██║     ███████║█████╗██╔██╗ ██║█████╗     ██║   ██████╔╝███████║
   ██╔═██╗ ██╔══██║██║     ██╔══██║╚════╝██║╚██╗██║██╔══╝     ██║   ██╔══██╗██╔══██║
   ██║  ██╗██║  ██║███████╗██║  ██║      ██║ ╚████║███████╗   ██║   ██║  ██║██║  ██║
   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝      ╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝""", "c")
    say("   V3  ·  deterministic, air-gapped forensic correlation & crime reconstruction\n", "d")


def main():
    ap = argparse.ArgumentParser(description="KALA-NETRA V3")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--regenerate", action="store_true", help="rebuild the benchmark evidence set")
    ap.add_argument("--eval-only", action="store_true", help="run the benchmark and exit")
    a = ap.parse_args()

    banner()
    ensure_deps(auto=not a.no_install)

    from backend import config as CFG
    from backend import generate_data, pipeline
    from backend import eval as evaluator

    os.makedirs(CFG.OUT_DIR, exist_ok=True)
    if a.regenerate or not os.path.exists(CFG.GROUND_TRUTH):
        say("· generating synthetic benchmark evidence set …", "y")
        gt = generate_data.generate()
        say(f'· wrote 6 exhibits + ground truth ({sum(gt["record_counts"].values())} records) '
            f'to data/', "g")

    t0 = time.time()
    say("· running deterministic pipeline …", "y")
    case = pipeline.run()
    say(f'· {case["counts"]["events"]} records correlated in {case["runtime_ms"]:.0f} ms '
        f'(SQLite written to out/kala_netra.sqlite)', "g")

    m = evaluator.evaluate(case)
    h = m["headline"]
    say("\n  BENCHMARK SCORECARD", "b")
    rows = [("clock offset RMSE_β", f'{h["RMSE_beta_s"]:.3f} s', "target ≤ 1.800 s"),
            ("entity resolution F1", f'{h["entity_F1"]:.3f}', "pairwise, transitive closure"),
            ("causal chain F1", f'{h["causal_F1"]:.3f}', "max-weight arborescence"),
            ("GPS alibi spoof recall", f'{h["spoof_recall"]:.0%}', "falsified digital alibi"),
            ("mule identification recall", f'{h["mule_recall"]:.0%}', "pass-through accounts"),
            ("provenance verification", f'{h["provenance_verification_rate_pct"]:.1f} %',
             "bytes re-read + Merkle-validated"),
            ("citation precision", f'{h["citation_precision"]:.0%}', "deterministic templates"),
            ("hallucination rate", f'{h["hallucination_rate"]:.0%}', "no LLM in evidential path")]
    for k, v, note in rows:
        say(f'    {k:<28}{C["g"]}{v:>10}{C["0"]}   {C["d"]}{note}{C["0"]}')

    if a.eval_only:
        return 0

    import uvicorn
    url = f"http://{a.host}:{a.port}"
    say(f'\n  console  →  {C["c"]}{C["b"]}{url}{C["0"]}')
    say(f'  api docs →  {url}/api/docs', "d")
    say("  press Ctrl+C to stop\n", "d")
    if not a.no_browser:
        threading.Timer(1.4, lambda: webbrowser.open(url)).start()
    uvicorn.run("backend.app:app", host=a.host, port=a.port, log_level="warning")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped.")
