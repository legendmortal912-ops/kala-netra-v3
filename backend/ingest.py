"""KALA-NETRA V3 - Section 2: binary-mode ingestion, byte-offset provenance,
RFC 6962 domain-separated Merkle ledger and multimedia header integrity.

Every evidence file is opened strictly in binary mode ("rb") so that a CRLF
line terminator stays 2 bytes and every cited byte range can be re-read from
the raw file on disk and re-hashed by a defence expert.
"""
from __future__ import annotations
import csv, hashlib, io, json, os, re, struct
from datetime import datetime, timezone

from . import config as C

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
JSON_OBJ_RE = re.compile(rb'\{[^{}]*"event_raw_id"[^{}]*\}')


# --------------------------------------------------------------- utilities ---
def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def leaf_hash(slice_: bytes) -> str:
    return sha256(LEAF_PREFIX + slice_)


def merkle_levels(leaves: list[str]) -> list[list[str]]:
    if not leaves:
        return [[sha256(b"")]]
    levels = [leaves[:]]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        if len(cur) % 2 == 1:
            cur = cur + [cur[-1]]          # duplicate final node
        nxt = [sha256(NODE_PREFIX + bytes.fromhex(cur[k]) + bytes.fromhex(cur[k + 1]))
               for k in range(0, len(cur), 2)]
        levels.append(nxt)
    return levels


def merkle_root(leaves: list[str]) -> str:
    return merkle_levels(leaves)[-1][0]


def merkle_proof(leaves: list[str], index: int) -> list[dict]:
    """O(log2 N) sibling path needed to recompute the root."""
    levels, proof, idx = merkle_levels(leaves), [], index
    for l in range(len(levels) - 1):
        cur = levels[l]
        if len(cur) % 2 == 1:
            cur = cur + [cur[-1]]
        sib = idx + 1 if idx % 2 == 0 else idx - 1
        proof.append({"level": l, "position": "right" if idx % 2 == 0 else "left",
                      "hash": cur[sib]})
        idx //= 2
    return proof


def verify_proof(leaf: str, proof: list[dict], root: str) -> bool:
    h = leaf
    for step in proof:
        a, b = (h, step["hash"]) if step["position"] == "right" else (step["hash"], h)
        h = sha256(NODE_PREFIX + bytes.fromhex(a) + bytes.fromhex(b))
    return h == root


def parse_epoch(s: str) -> float:
    s = s.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() \
        if "+" not in s else datetime.fromisoformat(s).timestamp()


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------- binary record extraction --
def split_lines(raw: bytes, skip_header: bool = True):
    """Yield (record_index, start_byte, end_byte) for every \\n-terminated line.
    end_byte is exclusive and INCLUDES the \\r\\n terminator."""
    out, start, idx = [], 0, 0
    n = len(raw)
    pos = 0
    first = True
    while pos < n:
        nl = raw.find(b"\n", pos)
        if nl == -1:
            end = n
            pos = n
        else:
            end = nl + 1
            pos = end
        if start == end:
            break
        if first and skip_header:
            first = False
        else:
            if raw[start:end].strip():
                out.append((idx, start, end))
                idx += 1
        start = end
    return out


def csv_fields(raw: bytes, header: list[str], start: int, end: int) -> dict:
    text = raw[start:end].decode("utf-8", errors="replace").rstrip("\r\n")
    vals = next(csv.reader(io.StringIO(text)))
    return {header[i]: (vals[i] if i < len(vals) else "") for i in range(len(header))}


# =============================================================== EXIF ========
def read_exif(path: str) -> dict:
    with open(path, "rb") as f:
        raw = f.read()
    rep = {"file": os.path.basename(path), "size_bytes": len(raw),
           "sha256": sha256(raw), "flags": [], "tags": {}, "container": "UNKNOWN"}
    if raw[:3] == b"\xFF\xD8\xFF":
        rep["container"] = "JPEG"
    elif raw[:4] == b"\x89PNG":
        rep["container"] = "PNG"
    else:
        rep["flags"].append({"code": "CONTAINER_SIGNATURE_INVALID", "severity": "HIGH",
                             "detail": "magic bytes do not match JPEG/PNG"})
    i = raw.find(b"\xFF\xE1")
    if i >= 0 and raw[i + 4:i + 10] == b"Exif\x00\x00":
        seg_len = struct.unpack(">H", raw[i + 2:i + 4])[0]
        tiff = raw[i + 10:i + 2 + seg_len]
        rep["tags"] = _parse_tiff(tiff)
    want = {0x9003: "DateTimeOriginal", 0x9004: "DateTimeDigitized",
            0x0132: "ModifyDate", 0x0131: "Software"}
    tags = {want[k]: v for k, v in rep["tags"].items() if k in want}
    rep["exif"] = tags

    def ep(v):
        try:
            return datetime.strptime(v.strip("\x00 "), "%Y:%m:%d %H:%M:%S") \
                .replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            return None
    a, b = ep(tags.get("ModifyDate", "")), ep(tags.get("DateTimeOriginal", ""))
    if a and b and abs(a - b) > C.EXIF_MISMATCH_S:
        rep["flags"].append({"code": "EXIF_TIMESTAMP_MISMATCH", "severity": "HIGH",
                             "detail": f"ModifyDate - DateTimeOriginal = {abs(a-b):.0f} s "
                                       f"(> {C.EXIF_MISMATCH_S:.0f} s tolerance)"})
    ascii_blob = raw[:4096].decode("latin-1", errors="replace")
    hits = sorted({fp for fp in C.EDITOR_FINGERPRINTS
                   if fp in ascii_blob or fp in tags.get("Software", "")})
    if hits:
        rep["flags"].append({"code": "MEDIA_REENCODED_OR_EDITED", "severity": "HIGH",
                             "detail": "editing/transcoding fingerprint: " + ", ".join(hits)})
    return rep


def _parse_tiff(tiff: bytes) -> dict:
    if len(tiff) < 8:
        return {}
    endian = "<" if tiff[:2] == b"II" else ">"
    out, seen = {}, set()

    def walk(off):
        if off in seen or off + 2 > len(tiff):
            return
        seen.add(off)
        n = struct.unpack(endian + "H", tiff[off:off + 2])[0]
        for k in range(n):
            e = off + 2 + 12 * k
            if e + 12 > len(tiff):
                return
            tag, typ, cnt = struct.unpack(endian + "HHI", tiff[e:e + 8])
            vb = tiff[e + 8:e + 12]
            size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}.get(typ, 1) * cnt
            if size > 4:
                p = struct.unpack(endian + "I", vb)[0]
                vb = tiff[p:p + size]
            if typ == 2:
                out[tag] = vb.split(b"\x00")[0].decode("latin-1", errors="replace")
            elif typ == 4 and tag in (0x8769, 0xA005):
                walk(struct.unpack(endian + "I", vb[:4])[0])
    walk(struct.unpack(endian + "I", tiff[4:8])[0])
    return out


# ========================================================= RECORD PARSERS ====
def _acct_type(a: str) -> str:
    return "UPI_VPA" if "@" in a else "BANK_ACCT"


def _r(modality: str) -> float:
    return C.UNCERTAINTY_R.get(modality, C.UNCERTAINTY_R["DEFAULT"])


def _base(fid, idx, start, end, raw, ts, etype):
    sl = raw[start:end]
    return {
        "event_id": f"{fid}#{idx:05d}", "file_id": fid, "record_index": idx,
        "byte_offset_start": start, "byte_offset_end": end,
        "leaf_sha256": leaf_hash(sl), "raw_bytes_len": end - start,
        "raw_timestamp_utc": ts, "raw_epoch": parse_epoch(ts), "event_type": etype,
        "actor_type": "", "actor_id": "", "target_type": "", "target_id": "",
        "lat": None, "lon": None, "r_e": None, "amount_inr": None,
        "anchor_key_type": "", "anchor_key": "", "device_id": "",
        "co_record_ids": [], "extra": {}, "narrative": "",
    }


def parse_cdr(raw, fid):
    hdr = raw[:raw.find(b"\n")].decode().strip().split(",")
    evs = []
    for idx, s, e in split_lines(raw):
        f = csv_fields(raw, hdr, s, e)
        et = f["event_type"]
        ev = _base(fid, idx, s, e, raw, f["timestamp_utc"], et)
        ev["lat"], ev["lon"] = fnum(f["lat"]), fnum(f["lon"])
        ev["r_e"] = _r("CELL_TOWER_CGI")
        ev["extra"] = {k: f[k] for k in ("cgi", "azimuth_deg", "cell_label", "duration_s",
                                         "msisdn", "imsi", "imei", "peer_msisdn")}
        dev = [("IMEI", f["imei"]), ("IMSI", f["imsi"])]
        ev["co_record_ids"] = [[t, v] for t, v in dev if v]
        if et in ("CELL_ATTACH", "CELL_DETACH"):
            ev["actor_type"], ev["actor_id"] = "IMEI", f["imei"]
            ev["target_type"], ev["target_id"] = "CELL_TOWER_CGI", f["cgi"]
            ev["narrative"] = (f'handset IMEI {f["imei"]} '
                               f'{"attached to" if et=="CELL_ATTACH" else "detached from"} cell '
                               f'{f["cgi"]} ({f["cell_label"]}, azimuth '
                               f'{f["azimuth_deg"] or "NOT LOGGED"})')
        elif et == "IMSI_ATTACH":
            ev["actor_type"], ev["actor_id"] = "IMSI", f["imsi"]
            ev["target_type"], ev["target_id"] = "CELL_TOWER_CGI", f["cgi"]
            ev["narrative"] = (f'subscriber module IMSI {f["imsi"]} performed a location '
                               f'update on cell {f["cgi"]} ({f["cell_label"]})')
        elif et == "SIM_BIND":
            ev["actor_type"], ev["actor_id"] = "IMSI", f["imsi"]
            ev["target_type"], ev["target_id"] = "MSISDN", f["msisdn"]
            ev["narrative"] = (f'MSISDN {f["msisdn"]} was re-bound to IMSI {f["imsi"]} '
                               f'inside handset IMEI {f["imei"]} on cell {f["cgi"]}')
        elif et == "OTP_SMS_INTERCEPT":
            ev["actor_type"], ev["actor_id"] = "MSISDN", f["msisdn"]
            ev["target_type"], ev["target_id"] = "IMEI", f["imei"]
            ev["anchor_key_type"], ev["anchor_key"] = "SMS_PDU_HASH", f["sms_pdu_hash"]
            ev["extra"]["rrn"] = f["rrn"]
            ev["narrative"] = (f'the bank OTP SMS for MSISDN {f["msisdn"]} (RRN {f["rrn"]}, '
                               f'PDU {f["sms_pdu_hash"]}) was delivered to handset IMEI {f["imei"]}')
        elif et == "PHISHING_SMS_IN":
            ev["actor_type"], ev["actor_id"] = "IMEI", f["imei"]
            ev["target_type"], ev["target_id"] = "MSISDN", f["peer_msisdn"]
            ev["anchor_key_type"], ev["anchor_key"] = "SMS_PDU_HASH", f["sms_pdu_hash"]
            ev["narrative"] = (f'handset IMEI {f["imei"]} transmitted an SMS carrying an APK '
                               f'download URL to MSISDN {f["peer_msisdn"]} (PDU {f["sms_pdu_hash"]})')
        else:   # VOICE_CALL / SMS_OUT / SMS_IN
            ev["actor_type"], ev["actor_id"] = "IMEI", f["imei"]
            ev["target_type"], ev["target_id"] = "MSISDN", f["peer_msisdn"]
            verb = "placed a voice call to" if et == "VOICE_CALL" else "exchanged an SMS with"
            ev["narrative"] = (f'handset IMEI {f["imei"]} {verb} {f["peer_msisdn"]} '
                               f'from cell {f["cgi"]}'
                               + (f' (duration {f["duration_s"]} s)' if f["duration_s"] else ""))
        if et == "OTP_SMS_INTERCEPT" and f["rrn"]:
            ev["extra"]["rrn_anchor"] = f["rrn"]
        evs.append(ev)
        if f["rrn"] and et != "OTP_SMS_INTERCEPT":
            pass
    # the OTP record carries two anchors (PDU + RRN): emit the RRN as a shadow anchor
    for ev in evs:
        if ev["event_type"] == "OTP_SMS_INTERCEPT" and ev["extra"].get("rrn"):
            ev["anchor_key_2_type"], ev["anchor_key_2"] = "RRN", ev["extra"]["rrn"]
    return evs


def parse_ufdr(raw, fid):
    evs = []
    for idx, m in enumerate(JSON_OBJ_RE.finditer(raw)):
        s, e = m.start(), m.end()
        o = json.loads(raw[s:e].decode("utf-8", errors="replace"))
        et = o["event_type"]
        ev = _base(fid, idx, s, e, raw, o["timestamp_local_utc"], et)
        ev["device_id"] = o.get("device_id", "")
        ev["lat"], ev["lon"] = fnum(o.get("lat")), fnum(o.get("lon"))
        ev["r_e"] = _r("WIFI_BSSID") if ev["lat"] is not None else None
        ev["extra"] = {k: o.get(k, "") for k in ("artifact_source", "is_deleted", "note",
                                                 "apk_sha1", "uptime_ms", "peer_msisdn",
                                                 "mac_addr", "imei", "bssid")}
        ev["co_record_ids"] = [[t, v] for t, v in (("IMEI", o.get("imei", "")),
                                                   ("MAC_ADDR", o.get("mac_addr", "")))if v]
        ev["actor_type"], ev["actor_id"] = "IMEI", o.get("imei", "")
        if et == "WIFI_DHCP_CLIENT":
            ev["target_type"], ev["target_id"] = "WIFI_BSSID", o.get("bssid", "")
            ev["anchor_key_type"], ev["anchor_key"] = "DHCP_XID", o.get("dhcp_xid", "")
            ev["narrative"] = (f'handset IMEI {o.get("imei")} (NIC {o.get("mac_addr")}) obtained a '
                               f'DHCP lease from BSSID {o.get("bssid")} using transaction id '
                               f'{o.get("dhcp_xid")}')
        elif et == "RADIO_UPTIME_SNAPSHOT":
            ev["anchor_key_type"], ev["anchor_key"] = "CELL_HANDOVER_SEQ", str(o.get("uptime_ms", ""))
            ev["narrative"] = (f'handset IMEI {o.get("imei")} recorded radio/location kernel '
                               f'uptime counter {o.get("uptime_ms")}')
        elif et in ("APK_INSTALL", "PERM_ACCESSIBILITY"):
            ev["target_type"], ev["target_id"] = "APK_HASH", o.get("apk_sha1", "")
            ev["narrative"] = (f'{o.get("note")} on handset IMEI {o.get("imei")} '
                               f'(artifact {o.get("artifact_source")})')
        elif et == "OTP_SMS_INTERCEPT":
            ev["anchor_key_type"], ev["anchor_key"] = "SMS_PDU_HASH", o.get("sms_pdu_hash", "")
            ev["narrative"] = (f'handset IMEI {o.get("imei")} stored the intercepted OTP SMS '
                               f'(PDU {o.get("sms_pdu_hash")}) in {o.get("artifact_source")}')
        elif et == "PHISHING_SMS_OUT":
            ev["target_type"], ev["target_id"] = "MSISDN", o.get("peer_msisdn", "")
            ev["anchor_key_type"], ev["anchor_key"] = "SMS_PDU_HASH", o.get("sms_pdu_hash", "")
            ev["narrative"] = f'{o.get("note")} (recovered from {o.get("artifact_source")})'
        elif et == "CALL_LOG_ENTRY":
            ev["target_type"], ev["target_id"] = "MSISDN", o.get("peer_msisdn", "")
            ev["narrative"] = (f'call-log entry with {o.get("peer_msisdn")} '
                               f'[{"DELETED, " if o.get("is_deleted") else ""}{o.get("note")}]')
        else:
            ev["narrative"] = f'{et}: {o.get("note")}'
        evs.append(ev)
    return evs


def parse_wifi(raw, fid):
    hdr = raw[:raw.find(b"\n")].decode().strip().split(",")
    evs = []
    for idx, s, e in split_lines(raw):
        f = csv_fields(raw, hdr, s, e)
        ev = _base(fid, idx, s, e, raw, f["timestamp_utc"], f["event_type"])
        ev["lat"], ev["lon"], ev["r_e"] = fnum(f["lat"]), fnum(f["lon"]), _r("WIFI_BSSID")
        ev["actor_type"], ev["actor_id"] = "MAC_ADDR", f["mac_addr"]
        ev["target_type"], ev["target_id"] = "WIFI_BSSID", f["bssid"]
        ev["extra"] = {k: f[k] for k in ("ip_addr", "rssi_dbm", "ap_label", "dhcp_xid")}
        if f["dhcp_xid"]:
            ev["anchor_key_type"], ev["anchor_key"] = "DHCP_XID", f["dhcp_xid"]
        ev["narrative"] = (f'NIC {f["mac_addr"]} {f["event_type"]} on BSSID {f["bssid"]} '
                           f'({f["ap_label"]}, RSSI {f["rssi_dbm"]} dBm'
                           + (f', lease {f["ip_addr"]} via XID {f["dhcp_xid"]}' if f["dhcp_xid"] else "")
                           + ")")
        evs.append(ev)
    return evs


def parse_bank(raw, fid):
    hdr = raw[:raw.find(b"\n")].decode().strip().split(",")
    evs = []
    for idx, s, e in split_lines(raw):
        f = csv_fields(raw, hdr, s, e)
        et = f["event_type"]
        ev = _base(fid, idx, s, e, raw, f["timestamp_utc"], et)
        ev["lat"], ev["lon"] = fnum(f["lat"]), fnum(f["lon"])
        ev["amount_inr"] = fnum(f["amount_inr"])
        ev["actor_type"], ev["actor_id"] = _acct_type(f["actor_acct"]), f["actor_acct"]
        ev["extra"] = {k: f[k] for k in ("rrn", "terminal_id", "atm_term_trig", "channel",
                                         "target_acct", "actor_acct")}
        if et == "ATM_CASH_WDL":
            ev["target_type"], ev["target_id"] = "ATM_TERMINAL", f["terminal_id"]
            ev["r_e"] = _r("ATM_TERMINAL")
            ev["anchor_key_type"], ev["anchor_key"] = "ATM_TERM_TRIG", \
                f'{f["terminal_id"]}|{f["atm_term_trig"]}'
            ev["narrative"] = (f'INR {ev["amount_inr"]:,.2f} was dispensed to account '
                               f'{f["actor_acct"]} (card {f["target_acct"]}) at terminal '
                               f'{f["terminal_id"]}, dispenser trigger {f["atm_term_trig"]}')
        elif et == "OTP_DISPATCH":
            ev["target_type"], ev["target_id"] = _acct_type(f["target_acct"]), f["target_acct"]
            ev["anchor_key_type"], ev["anchor_key"] = "RRN", f["rrn"]
            ev["narrative"] = (f'the core banking switch dispatched a UPI registration OTP for '
                               f'account {f["target_acct"]} under RRN {f["rrn"]}')
        else:
            ev["target_type"], ev["target_id"] = _acct_type(f["target_acct"]), f["target_acct"]
            ev["narrative"] = (f'INR {ev["amount_inr"]:,.2f} moved from {f["actor_acct"]} to '
                               f'{f["target_acct"]} over {f["channel"]} (RRN {f["rrn"]})')
        evs.append(ev)
    return evs


def parse_cctv(raw, fid):
    hdr = raw[:raw.find(b"\n")].decode().strip().split(",")
    evs = []
    for idx, s, e in split_lines(raw):
        f = csv_fields(raw, hdr, s, e)
        ev = _base(fid, idx, s, e, raw, f["timestamp_utc"], f["event_type"])
        ev["lat"], ev["lon"], ev["r_e"] = fnum(f["lat"]), fnum(f["lon"]), _r("CCTV_DVR")
        if f["event_type"] == "ATM_DISPENSER_TRIGGER":
            ev["actor_type"], ev["actor_id"] = "ATM_TERMINAL", f["terminal_id"]
        else:
            ev["actor_type"], ev["actor_id"] = "VEHICLE_PLATE", f["plate_ocr"]
        if f["event_type"] == "ATM_DISPENSER_TRIGGER":
            ev["target_type"], ev["target_id"] = "CCTV_CAMERA", f["camera_id"]
        elif f["terminal_id"]:
            ev["target_type"], ev["target_id"] = "ATM_TERMINAL", f["terminal_id"]
        else:
            ev["target_type"], ev["target_id"] = "CCTV_CAMERA", f["camera_id"]
        ev["extra"] = {k: f[k] for k in ("camera_id", "frame_file", "ocr_confidence",
                                         "atm_term_trig", "terminal_id")}
        if f["atm_term_trig"]:
            ev["anchor_key_type"], ev["anchor_key"] = "ATM_TERM_TRIG", \
                f'{f["terminal_id"]}|{f["atm_term_trig"]}'
        if f["event_type"] == "ATM_DISPENSER_TRIGGER":
            ev["narrative"] = (f'the DVR overlay controller of camera {f["camera_id"]} recorded '
                               f'cash-dispenser trigger {f["atm_term_trig"]} at terminal '
                               f'{f["terminal_id"]}')
            evs.append(ev)
            continue
        ev["narrative"] = (f'camera {f["camera_id"]} read number plate {f["plate_ocr"]} '
                           f'(OCR confidence {f["ocr_confidence"]})'
                           + (f' at terminal {f["terminal_id"]}' if f["terminal_id"] else "")
                           + (f', frame {f["frame_file"]}' if f["frame_file"] else ""))
        evs.append(ev)
    return evs


def parse_gps(raw, fid):
    hdr = raw[:raw.find(b"\n")].decode().strip().split(",")
    evs = []
    for idx, s, e in split_lines(raw):
        f = csv_fields(raw, hdr, s, e)
        ev = _base(fid, idx, s, e, raw, f["timestamp_utc"], "GPS_PING")
        ev["lat"], ev["lon"] = fnum(f["lat"]), fnum(f["lon"])
        ev["r_e"] = max(_r("GPS"), fnum(f["accuracy_m"]) or 0.0)
        ev["actor_type"], ev["actor_id"] = "IMEI", f["imei"]
        ev["extra"] = {k: f[k] for k in ("accuracy_m", "provider", "uptime_ms", "handover_seq")}
        if f["handover_seq"]:
            ev["anchor_key_type"], ev["anchor_key"] = "CELL_HANDOVER_SEQ", f["handover_seq"]
        ev["narrative"] = (f'handset IMEI {f["imei"]} reported an application-layer location fix at '
                           f'{ev["lat"]:.5f} N, {ev["lon"]:.5f} E (provider {f["provider"]}, '
                           f'accuracy {f["accuracy_m"]} m)')
        evs.append(ev)
    return evs


PARSERS = {"SRC_CDR_01": parse_cdr, "SRC_UFDR_01": parse_ufdr, "SRC_WIFI_01": parse_wifi,
           "SRC_BANK_01": parse_bank, "SRC_CCTV_01": parse_cctv, "SRC_GPS_01": parse_gps}


# ================================================================ INGEST =====
def ingest_all(data_dir: str | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    data_dir = data_dir or C.DATA_DIR
    files, events = [], []
    for sidx, fid, fname, label, sigma, _beta in C.SOURCES:
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:                      # strictly binary
            raw = f.read()
        evs = PARSERS[fid](raw, fid)
        leaves = [e["leaf_sha256"] for e in evs]
        root = merkle_root(leaves)
        crlf = raw.count(b"\r\n")
        files.append({
            "file_id": fid, "source_index": sidx, "filename": fname, "label": label,
            "sigma_s": sigma, "path": path, "size_bytes": len(raw),
            "sha256_file": sha256(raw), "merkle_root": root, "record_count": len(evs),
            "line_terminator": "CRLF" if crlf else "LF", "crlf_count": crlf,
            "estimated_clock_offset_sec": 0.0, "is_clock_anchored": 0,
            "anchor_count": 0, "leaves": leaves,
        })
        events.extend(evs)

    media = []
    for ev in events:
        fr = (ev.get("extra") or {}).get("frame_file")
        if fr:
            p = os.path.join(data_dir, fr)
            if os.path.exists(p):
                rep = read_exif(p)
                rep["linked_event_id"] = ev["event_id"]
                media.append(rep)
                ev["extra"]["media_flags"] = [f["code"] for f in rep["flags"]]
    return files, events, media
