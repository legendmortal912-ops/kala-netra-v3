"""KALA-NETRA V3 - Section 8B: optional air-gapped natural-language query filter.

A local Ollama instance (default qwen2.5:3b at 127.0.0.1:11434) is asked to emit
a JSON Query Filter AST and NOTHING else. If Ollama is absent or slower than
2.0 s, a deterministic regex parser takes over, so the feature never fails.
"""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timedelta, timezone

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"
TIMEOUT_S = 2.0
SYSTEM = (
    "You convert an investigator question into a JSON query filter. Output ONLY JSON with keys "
    "actor_types, actor_ids, time_window_utc, event_types. Use [\"ALL\"] when unconstrained."
)
EVENT_KEYWORDS = {
    "sim swap": ["SIM_BIND"], "swap": ["SIM_BIND"], "clone": ["SIM_BIND"],
    "otp": ["OTP_SMS_INTERCEPT", "OTP_DISPATCH"], "phish": ["PHISHING_SMS_IN", "PHISHING_SMS_OUT"],
    "apk": ["APK_INSTALL"], "malware": ["APK_INSTALL"], "install": ["APK_INSTALL"],
    "permission": ["PERM_ACCESSIBILITY"], "accessibility": ["PERM_ACCESSIBILITY"],
    "withdraw": ["ATM_CASH_WDL"], "atm": ["ATM_CASH_WDL"], "cash": ["ATM_CASH_WDL"],
    "mule": ["UPI_MULE_HOP"], "hop": ["UPI_MULE_HOP"], "debit": ["UPI_DEBIT_TXN"],
    "transfer": ["UPI_DEBIT_TXN", "UPI_MULE_HOP", "UPI_CREDIT_TXN"],
    "upi": ["UPI_DEBIT_TXN", "UPI_MULE_HOP", "UPI_CREDIT_TXN"],
    "call": ["VOICE_CALL"], "sms": ["SMS_IN", "SMS_OUT"],
    "wifi": ["WIFI_ASSOC", "WIFI_DHCPACK", "WIFI_DISASSOC", "WIFI_DHCP_CLIENT"],
    "wi-fi": ["WIFI_ASSOC", "WIFI_DHCPACK", "WIFI_DHCP_CLIENT"],
    "tower": ["CELL_ATTACH", "IMSI_ATTACH"], "cell": ["CELL_ATTACH", "IMSI_ATTACH"],
    "gps": ["GPS_PING"], "location": ["GPS_PING"], "plate": ["CCTV_ANPR_SIGHTING"],
    "cctv": ["CCTV_ANPR_SIGHTING", "ATM_DISPENSER_TRIGGER"], "anpr": ["CCTV_ANPR_SIGHTING"],
}
TYPE_KEYWORDS = {"imei": "IMEI", "handset": "IMEI", "phone": "IMEI", "burner": "IMEI",
                 "imsi": "IMSI", "sim": "IMSI", "msisdn": "MSISDN", "number": "MSISDN",
                 "mac": "MAC_ADDR", "account": "BANK_ACCT", "upi": "UPI_VPA",
                 "vehicle": "VEHICLE_PLATE", "car": "VEHICLE_PLATE", "plate": "VEHICLE_PLATE"}
ID_RE = re.compile(r"\b(\d{15}|\+?\d{10,13}|[0-9A-F]{2}(?::[0-9A-F]{2}){5}|"
                   r"[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}|[\w.\-]+@[a-z]+)\b", re.I)
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
MIN_RE = re.compile(r"(\d+)\s*(minute|min|hour|hr)s?")


def regex_parse(q: str, events: list[dict]) -> dict:
    ql = q.lower()
    # A keyword used only to anchor a relative time window ("within 20 minutes OF the
    # sim swap") must not also become an event-type filter, otherwise the query
    # collapses to the anchor record itself.
    anchor_kw = None
    am = re.search(r"\b(?:of|from|after|before|around)\b(.*)$", ql)
    anchor_tail = am.group(1) if (am and MIN_RE.search(ql)) else ""
    hit_kws = [k for k in EVENT_KEYWORDS if k in ql]
    if anchor_tail:
        anchor_kw = {k for k in hit_kws if k in anchor_tail}
    else:
        anchor_kw = set()
    wants_all = bool(re.search(r"\ball\b\s+\w*\s*events?\b|\beverything\b", ql))
    etypes = sorted({t for k in hit_kws if k not in anchor_kw for t in EVENT_KEYWORDS[k]})
    if wants_all or not etypes:
        etypes = ["ALL"]
    atypes = sorted({v for k, v in TYPE_KEYWORDS.items() if re.search(rf"\b{k}\b", ql)}) or ["ALL"]
    ids = [m.group(0) for m in ID_RE.finditer(q)]
    known = {e["actor_id"] for e in events} | {e["target_id"] for e in events}
    ids = [i for i in ids if i in known]
    # relative window around a named anchor event ("within 20 minutes of the SIM swap")
    win = None
    mm = MIN_RE.search(ql)
    if mm:
        span = int(mm.group(1)) * (60 if mm.group(2).startswith(("m",)) else 3600)
        anchor = None
        for key, types in (("sim swap", "SIM_BIND"), ("swap", "SIM_BIND"),
                           ("otp", "OTP_SMS_INTERCEPT"), ("withdraw", "ATM_CASH_WDL"),
                           ("atm", "ATM_CASH_WDL"), ("phish", "PHISHING_SMS_IN")):
            if key in ql:
                anchor = next((e for e in events if e["event_type"] == types), None)
                if anchor:
                    break
        if anchor:
            c = anchor["corrected_timestamp_epoch"]
            win = [_iso(c - span), _iso(c + span)]
    if win is None:
        ts = TIME_RE.findall(q)
        if len(ts) >= 2:
            win = [_hhmm(ts[0]), _hhmm(ts[1])]
        elif len(ts) == 1:
            base = datetime.strptime(_hhmm(ts[0]), "%Y-%m-%dT%H:%M:%SZ")
            win = [(base - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   (base + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")]
    return {"actor_types": atypes, "actor_ids": ids,
            "time_window_utc": win or ["ALL", "ALL"], "event_types": etypes,
            "parser": "deterministic-regex"}


def _iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hhmm(t):
    h, m, s = int(t[0]), int(t[1]), int(t[2] or 0)
    return f"2026-11-18T{h:02d}:{m:02d}:{s:02d}Z"


def ollama_parse(q: str) -> dict | None:
    body = json.dumps({"model": OLLAMA_MODEL, "prompt": SYSTEM + "\n\nQUESTION: " + q,
                       "stream": False, "format": "json",
                       "options": {"temperature": 0}}).encode()
    try:
        req = urllib.request.Request(OLLAMA_URL, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            data = json.loads(r.read().decode())
        ast = json.loads(data.get("response", "{}"))
        if not isinstance(ast, dict):
            return None
        ast.setdefault("actor_types", ["ALL"]); ast.setdefault("actor_ids", [])
        ast.setdefault("event_types", ["ALL"]); ast.setdefault("time_window_utc", ["ALL", "ALL"])
        ast["parser"] = f"ollama:{OLLAMA_MODEL}"
        return ast
    except Exception:
        return None


def apply_filter(ast: dict, events: list[dict]) -> list[dict]:
    at = set(ast.get("actor_types") or ["ALL"])
    et = set(ast.get("event_types") or ["ALL"])
    ids = set(ast.get("actor_ids") or [])
    w = ast.get("time_window_utc") or ["ALL", "ALL"]
    lo = hi = None
    try:
        if w[0] != "ALL":
            lo = datetime.strptime(w[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        if w[1] != "ALL":
            hi = datetime.strptime(w[1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        lo = hi = None
    out = []
    for e in events:
        if "ALL" not in et and e["event_type"] not in et:
            continue
        if "ALL" not in at and e["actor_type"] not in at and e["target_type"] not in at:
            continue
        if ids and e["actor_id"] not in ids and e["target_id"] not in ids:
            continue
        t = e["corrected_timestamp_epoch"]
        if lo is not None and t < lo:
            continue
        if hi is not None and t > hi:
            continue
        out.append(e)
    return out


def query(q: str, events: list[dict], use_llm: bool = True) -> dict:
    ast = (ollama_parse(q) if use_llm else None) or regex_parse(q, events)
    hits = apply_filter(ast, events)
    hits.sort(key=lambda e: e["corrected_timestamp_epoch"])
    return {"question": q, "ast": ast, "match_count": len(hits),
            "events": [{"event_id": e["event_id"], "file_id": e["file_id"],
                        "t": e["corrected_timestamp_epoch"], "event_type": e["event_type"],
                        "actor_type": e["actor_type"], "actor_id": e["actor_id"],
                        "target_type": e["target_type"], "target_id": e["target_id"],
                        "narrative": e["narrative"],
                        "byte_offset_start": e["byte_offset_start"],
                        "byte_offset_end": e["byte_offset_end"],
                        "leaf_sha256": e["leaf_sha256"]} for e in hits[:400]]}
