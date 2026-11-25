"""KALA-NETRA V3 — deterministic synthetic benchmark generator.

Writes the 6 raw evidence files plus ground_truth.json for
"The Coordinated SIM-Swap & Mule Cash-Out Heist" (New Delhi, 18 Nov 2026).

Clock offsets are injected at WRITE time (raw = true - beta) so the
Laplacian solver downstream has to recover them from identity-free anchors.
"""
from __future__ import annotations
import json, os, random, struct, io
from datetime import datetime, timezone, timedelta

from . import config as C

RNG = random.Random(20261118)
DAY = datetime(2026, 11, 18, tzinfo=timezone.utc)
CRLF = "\r\n"


def T(hms: str, extra: float = 0.0) -> float:
    h, m, s = [int(x) for x in hms.split(":")]
    return (DAY + timedelta(hours=h, minutes=m, seconds=s)).timestamp() + extra


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------- geography --
SITES = {
    "LAJPAT":  (28.56770, 77.24330, "Lajpat Nagar Safe-House"),
    "KAROL":   (28.65190, 77.19090, "Karol Bagh"),
    "CP":      (28.63150, 77.21670, "Connaught Place Block A"),
    "CP_CAFE": (28.63180, 77.21700, "Connaught Place Cafe AP"),
    "NEHRU":   (28.54830, 77.25130, "Nehru Place ATM Plaza"),
    "MUMBAI":  (19.07600, 72.87770, "Mumbai (spoofed)"),
}
CGI = {"LAJPAT": "CGI_404_10_112_355", "KAROL": "CGI_404_10_112_387",
       "CP": "CGI_404_10_112_401", "NEHRU": "CGI_404_10_112_522"}
CAM = {"LAJPAT": "CAM_LJP_04", "KAROL": "CAM_KBG_11", "CP": "CAM_CP_02", "NEHRU": "CAM_NP_09"}

# ------------------------------------------------------------------ actors ---
IMEI_V       = "358911092233441"
IMSI_V       = "404101122334455"
IMSI_V_SWAP  = "404101122334499"
MSISDN_V     = "+919810011111"
ACCOUNT_V    = "SBIN0001234_9901"
IMEI_BURNER  = "352099118822771"
IMSI_BURNER  = "404109988776655"
MAC_BURNER   = "A4:5E:60:C8:11:22"
IMEI_PERSON  = "864500112233445"
MSISDN_SUSP  = "+919810044444"
PLATE_TRUE   = "DL8CAF5031"
PLATE_OCR    = "DL8CAF5O31"
MSISDN_HANDLER = "+919999000666"
BSSID_CAFE   = "00:1A:2B:3C:4D:5E"
MULES        = ["MULE_01@okaxis", "MULE_02@ybl", "MULE_03@ibl"]
CASHOUT      = "CASHOUT_99@paytm"
CARD         = "4591-XXXX-8821"
APK_HASH     = "a7f3c1e9b24d58006f1b2c3d4e5f6071"
DHCP_XID     = "0x4F2A910C"
ATM_TERMINAL = "ATM_NP_09"
ATM_TRIG     = "TRIG_NP09_7741"
RRN_OTP      = "632214998123"
PDU_OTP      = "pdu_9f8a7b6c"
PDU_PHISH    = "pdu_3c1d5e77"
FRAME_FILE   = "cctv_frame_ATM_NP_09_151112.jpg"

BETA = {fid: beta for (_i, fid, _fn, _lbl, _sg, beta) in C.SOURCES}


def raw(fid: str, true_epoch: float, jitter: float = 0.0) -> float:
    """Write-side inversion of t = tau + beta, plus optional sensor jitter."""
    return true_epoch - BETA[fid] + jitter


def j(fid: str) -> float:
    """Small, seeded, physically-plausible per-reading jitter."""
    sigma = C.SIGMA[fid]
    return round(RNG.gauss(0.0, min(0.35 * sigma, 0.6)), 3)


# =============================================================== row buffers =
cdr, ufdr, wifi, bank, cctv, gps = [], [], [], [], [], []
GT_CAUSAL: list[tuple[str, str]] = []
CORE: dict[str, str] = {}      # logical name -> event_id


def ev_id(fid: str, n: int) -> str:
    return f"{fid}#{n:05d}"


# ------------------------------------------------------------------- CDR -----
def add_cdr(true_t, etype, imei="", imsi="", msisdn="", peer="", site="", dur="",
            pdu="", rrn="", tag=None, azimuth=True):
    t = raw("SRC_CDR_01", true_t, j("SRC_CDR_01"))
    lat, lon, label = SITES[site] if site else ("", "", "")
    row = {
        "record_id": f"CDR{len(cdr)+1:05d}", "timestamp_utc": iso(t), "event_type": etype,
        "imei": imei, "imsi": imsi, "msisdn": msisdn, "peer_msisdn": peer,
        "cgi": CGI.get(site, ""), "azimuth_deg": (f"{RNG.choice([30,90,150,210,270,330])}" if azimuth else ""),
        "lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "duration_s": dur,
        "sms_pdu_hash": pdu, "rrn": rrn, "cell_label": label,
    }
    cdr.append(row)
    eid = ev_id("SRC_CDR_01", len(cdr) - 1)
    if tag:
        CORE[tag] = eid
    return eid


# ------------------------------------------------------------------ UFDR -----
def add_ufdr(true_t, etype, device, imei="", mac="", bssid="", peer="", apk="",
             pdu="", xid="", uptime="", site="", deleted=False, tag=None, body=""):
    t = raw("SRC_UFDR_01", true_t, j("SRC_UFDR_01"))
    lat, lon = (SITES[site][0], SITES[site][1]) if site else ("", "")
    o = {
        "event_raw_id": f"UFDR{len(ufdr)+1:05d}", "device_id": device,
        "timestamp_local_utc": iso(t), "event_type": etype, "imei": imei,
        "mac_addr": mac, "bssid": bssid, "peer_msisdn": peer, "apk_sha1": apk,
        "sms_pdu_hash": pdu, "dhcp_xid": xid, "uptime_ms": uptime,
        "lat": (f"{lat:.5f}" if lat != "" else ""), "lon": (f"{lon:.5f}" if lon != "" else ""),
        "artifact_source": "mmssms.db" if "SMS" in etype else ("package_usage.xml" if "APK" in etype or "PERM" in etype else "dhcp_client.log"),
        "is_deleted": 1 if deleted else 0, "note": body,
    }
    ufdr.append(o)
    eid = ev_id("SRC_UFDR_01", len(ufdr) - 1)
    if tag:
        CORE[tag] = eid
    return eid


# ------------------------------------------------------------------ WIFI -----
def add_wifi(true_t, etype, mac, bssid, site, ip="", xid="", rssi=None):
    t = raw("SRC_WIFI_01", true_t, j("SRC_WIFI_01"))
    lat, lon, label = SITES[site]
    wifi.append({
        "record_id": f"WIFI{len(wifi)+1:05d}", "timestamp_utc": iso(t), "event_type": etype,
        "mac_addr": mac, "bssid": bssid, "ap_label": label, "ip_addr": ip,
        "dhcp_xid": xid, "lat": f"{lat:.5f}", "lon": f"{lon:.5f}",
        "rssi_dbm": str(rssi if rssi is not None else RNG.randint(-78, -41)),
    })
    return ev_id("SRC_WIFI_01", len(wifi) - 1)


# ------------------------------------------------------------------ BANK -----
def add_bank(true_t, etype, actor, target, amount, rrn="", terminal="", trig="",
             site="", channel="UPI", tag=None):
    t = raw("SRC_BANK_01", true_t, j("SRC_BANK_01"))
    lat, lon = (SITES[site][0], SITES[site][1]) if site else ("", "")
    bank.append({
        "record_id": f"BNK{len(bank)+1:05d}", "timestamp_utc": iso(t), "event_type": etype,
        "actor_acct": actor, "target_acct": target, "amount_inr": f"{amount:.2f}",
        "rrn": rrn, "terminal_id": terminal, "atm_term_trig": trig,
        "lat": (f"{lat:.5f}" if lat != "" else ""), "lon": (f"{lon:.5f}" if lon != "" else ""),
        "channel": channel,
    })
    eid = ev_id("SRC_BANK_01", len(bank) - 1)
    if tag:
        CORE[tag] = eid
    return eid


# ------------------------------------------------------------------ CCTV -----
def add_cctv(true_t, plate, site, trig="", terminal="", frame="", conf=None, tag=None,
             etype="CCTV_ANPR_SIGHTING"):
    t = raw("SRC_CCTV_01", true_t, j("SRC_CCTV_01"))
    lat, lon, _ = SITES[site]
    cctv.append({
        "record_id": f"CCTV{len(cctv)+1:05d}", "timestamp_utc": iso(t), "event_type": etype,
        "plate_ocr": plate, "terminal_id": terminal, "atm_term_trig": trig,
        "camera_id": CAM[site], "lat": f"{lat:.5f}", "lon": f"{lon:.5f}",
        "frame_file": frame, "ocr_confidence": f"{conf if conf is not None else RNG.uniform(0.71,0.97):.3f}",
    })
    eid = ev_id("SRC_CCTV_01", len(cctv) - 1)
    if tag:
        CORE[tag] = eid
    return eid


# ------------------------------------------------------------------- GPS -----
def add_gps(true_t, imei, site, provider="fused", acc=None, handover="", tag=None):
    t = raw("SRC_GPS_01", true_t, j("SRC_GPS_01"))
    lat, lon, _ = SITES[site]
    gps.append({
        "record_id": f"GPS{len(gps)+1:05d}", "timestamp_utc": iso(t), "event_type": "GPS_PING",
        "imei": imei, "lat": f"{lat:.5f}", "lon": f"{lon:.5f}",
        "accuracy_m": f"{acc if acc is not None else RNG.uniform(8,22):.1f}",
        "provider": provider, "uptime_ms": handover, "handover_seq": handover,
    })
    eid = ev_id("SRC_GPS_01", len(gps) - 1)
    if tag:
        CORE[tag] = eid
    return eid


def pair_gps(true_t, site, seq):
    """Emit a GPS fix and the matching radio kernel-uptime snapshot from the
    SAME physical handset, giving an identity-free CELL_HANDOVER_SEQ anchor."""
    eid = add_gps(true_t, IMEI_PERSON, site, handover=seq)
    add_ufdr(true_t, "RADIO_UPTIME_SNAPSHOT", "PERSONAL_HANDSET", imei=IMEI_PERSON,
             uptime=seq, site=site, body="kernel boot-monotonic radio/location snapshot")
    return eid


# =========================================================== CORE TIMELINE ===
def build_core():
    global GT_CAUSAL
    # --- 13:28–13:52 pre-operation convoy: safe house -> Karol Bagh ----------
    add_cctv(T("13:28:00"), PLATE_TRUE, "LAJPAT", conf=0.94)
    add_cdr(T("13:30:00"), "CELL_ATTACH", imei=IMEI_PERSON, msisdn=MSISDN_SUSP, site="LAJPAT")
    add_cdr(T("13:30:14"), "CELL_ATTACH", imei=IMEI_BURNER, site="LAJPAT")
    add_cdr(T("13:30:16"), "IMSI_ATTACH", imei=IMEI_BURNER, imsi=IMSI_BURNER, site="LAJPAT")
    pair_gps(T("13:31:00"), "LAJPAT", "118422310")

    add_cctv(T("13:48:00"), PLATE_TRUE, "KAROL", conf=0.91)
    add_cdr(T("13:49:30"), "CELL_ATTACH", imei=IMEI_PERSON, msisdn=MSISDN_SUSP, site="KAROL")
    add_cdr(T("13:49:44"), "CELL_ATTACH", imei=IMEI_BURNER, site="KAROL")
    add_cdr(T("13:49:46"), "IMSI_ATTACH", imei=IMEI_BURNER, imsi=IMSI_BURNER, site="KAROL")
    pair_gps(T("13:52:00"), "KAROL", "119732110")

    # --- 14:08–14:10 reconnaissance & co-location at Connaught Place --------
    add_cctv(T("14:08:00"), PLATE_TRUE, "CP", conf=0.93)
    CORE["E_ATTACH_PERSON_CP"] = add_cdr(T("14:10:00"), "CELL_ATTACH", imei=IMEI_PERSON,
                                         msisdn=MSISDN_SUSP, site="CP")
    add_cdr(T("14:10:05"), "CELL_ATTACH", imei=IMEI_BURNER, site="CP")
    add_cdr(T("14:10:07"), "IMSI_ATTACH", imei=IMEI_BURNER, imsi=IMSI_BURNER, site="CP")
    add_wifi(T("14:10:20"), "WIFI_ASSOC", MAC_BURNER, BSSID_CAFE, "CP_CAFE", rssi=-46)
    add_wifi(T("14:10:25"), "WIFI_DHCPACK", MAC_BURNER, BSSID_CAFE, "CP_CAFE",
             ip="10.42.7.118", xid=DHCP_XID, rssi=-47)
    # device-side DHCP client log => identity-free DHCP_XID anchor + IMEI/MAC co-record
    add_ufdr(T("14:10:25"), "WIFI_DHCP_CLIENT", "BURNER_HANDSET", imei=IMEI_BURNER,
             mac=MAC_BURNER, bssid=BSSID_CAFE, xid=DHCP_XID, site="CP_CAFE",
             uptime="1184223100", body="DHCP client bound lease via XID " + DHCP_XID)

    for k, (hm, xid) in enumerate((("14:25:30", "0x7B31C40D"), ("14:40:55", "0x2E90AA51"))):
        add_wifi(T(hm), "WIFI_DHCPACK", MAC_BURNER, BSSID_CAFE, "CP_CAFE",
                 ip="10.42.7.118", xid=xid, rssi=-49)
        add_ufdr(T(hm), "WIFI_DHCP_CLIENT", "BURNER_HANDSET", imei=IMEI_BURNER,
                 mac=MAC_BURNER, bssid=BSSID_CAFE, xid=xid, site="CP_CAFE",
                 body="DHCP lease renewal via XID " + xid)

    # --- 14:15 falsified digital alibi --------------------------------------
    CORE["E_SPOOF_GPS"] = add_gps(T("14:15:00"), IMEI_PERSON, "MUMBAI",
                                  provider="gps", acc=4.0, handover="120022110")
    CORE["E_ATTACH_PERSON_CP2"] = add_cdr(T("14:20:00"), "CELL_ATTACH", imei=IMEI_PERSON,
                                          msisdn=MSISDN_SUSP, site="CP")

    # --- 14:22–14:23 phishing + malware -------------------------------------
    add_cdr(T("14:22:10"), "PHISHING_SMS_IN", imei=IMEI_BURNER, msisdn=MSISDN_V,
            peer=MSISDN_V, pdu=PDU_PHISH, site="CP", tag="E_PHISH")
    add_ufdr(T("14:22:10"), "PHISHING_SMS_OUT", "BURNER_HANDSET", imei=IMEI_BURNER,
             peer=MSISDN_V, pdu=PDU_PHISH, site="CP_CAFE",
             body="outbound SMS with URL hxxp://echallan-update[.]in/echallan_update.apk")
    add_ufdr(T("14:23:05"), "APK_INSTALL", "VICTIM_HANDSET", imei=IMEI_V, apk=APK_HASH,
             tag="E_APK", body="package echallan_update.apk installed from unknown source")
    add_ufdr(T("14:23:18"), "PERM_ACCESSIBILITY", "VICTIM_HANDSET", imei=IMEI_V, apk=APK_HASH,
             tag="E_PERM", body="BIND_ACCESSIBILITY_SERVICE and READ_SMS granted to echallan_update")

    # --- 14:30 SIM swap / clone ---------------------------------------------
    add_cdr(T("14:29:58"), "CELL_DETACH", imei=IMEI_V, imsi=IMSI_V, msisdn=MSISDN_V, site="CP")
    add_cdr(T("14:30:00"), "SIM_BIND", imei=IMEI_BURNER, imsi=IMSI_V_SWAP, msisdn=MSISDN_V,
            site="CP", tag="E_SWAP")

    # --- 14:34:12 OTP interception (RRN + PDU anchors) ----------------------
    add_cdr(T("14:34:12"), "OTP_SMS_INTERCEPT", imei=IMEI_BURNER, imsi=IMSI_V_SWAP,
            msisdn=MSISDN_V, pdu=PDU_OTP, rrn=RRN_OTP, site="CP", tag="E_OTP")
    add_ufdr(T("14:34:12"), "OTP_SMS_INTERCEPT", "BURNER_HANDSET", imei=IMEI_BURNER,
             pdu=PDU_OTP, site="CP_CAFE", uptime="1185658000",
             body="mmssms.db row: UPI registration OTP for A/C xx9901")
    add_bank(T("14:34:12"), "OTP_DISPATCH", "SBIN_OTP_GW", ACCOUNT_V, 0.0, rrn=RRN_OTP)

    # --- 14:35–14:37 layered UPI siphon -------------------------------------
    leg_ids = []
    for m, mule in enumerate(MULES):
        t1 = T("14:35:00") + m * 45
        a = add_bank(t1, "UPI_DEBIT_TXN", ACCOUNT_V, mule, 75000.0, rrn=f"6322149981{30+m*2:02d}")
        b = add_bank(t1 + 10, "UPI_DEBIT_TXN", ACCOUNT_V, mule, 75000.0, rrn=f"6322149981{31+m*2:02d}")
        leg_ids += [a, b]
        GT_CAUSAL += [(CORE["E_OTP"], a), (CORE["E_OTP"], b)]
        for k, dt in enumerate((15, 20, 25)):
            h = add_bank(t1 + 10 + dt, "UPI_MULE_HOP", mule, CASHOUT, 49333.34 if k == 0 else 49333.33,
                         rrn=f"7411{m}{k}2290031")
            GT_CAUSAL.append((b, h))
            if m == 2 and k == 2:
                CORE["E_LAST_HOP"] = h
    CORE["E_LEGS"] = leg_ids

    # --- 14:40 handler confirmation (shared low-degree hub) -----------------
    add_cdr(T("14:40:10"), "VOICE_CALL", imei=IMEI_BURNER, peer=MSISDN_HANDLER, site="CP", dur="41")
    add_cdr(T("14:41:05"), "VOICE_CALL", imei=IMEI_PERSON, msisdn=MSISDN_SUSP,
            peer=MSISDN_HANDLER, site="CP", dur="63")

    # --- 15:02–15:06 physical cash-out + split custody ----------------------
    add_cctv(T("15:02:00"), PLATE_TRUE, "NEHRU", terminal=ATM_TERMINAL, conf=0.88)
    add_cdr(T("15:04:50"), "CELL_ATTACH", imei=IMEI_BURNER, site="NEHRU")
    add_cdr(T("15:04:52"), "IMSI_ATTACH", imei=IMEI_BURNER, imsi=IMSI_BURNER, site="NEHRU")
    CORE["E_SPLIT_PERSON"] = add_cdr(T("15:04:30"), "CELL_ATTACH", imei=IMEI_PERSON,
                                     msisdn=MSISDN_SUSP, site="CP")
    add_cdr(T("15:06:00"), "CELL_ATTACH", imei=IMEI_PERSON, msisdn=MSISDN_SUSP, site="CP")
    add_bank(T("15:05:00"), "ATM_CASH_WDL", CASHOUT, CARD, 400000.0, terminal=ATM_TERMINAL,
             trig=ATM_TRIG, site="NEHRU", channel="ATM", tag="E_ATM")
    add_cctv(T("15:05:00"), "", "NEHRU", trig=ATM_TRIG, terminal=ATM_TERMINAL,
             conf=1.0, etype="ATM_DISPENSER_TRIGGER")
    add_cctv(T("15:05:12"), PLATE_OCR, "NEHRU", terminal=ATM_TERMINAL,
             frame=FRAME_FILE, conf=0.62, tag="E_ANPR")
    GT_CAUSAL += [(CORE["E_PHISH"], CORE["E_APK"]), (CORE["E_APK"], CORE["E_PERM"]),
                  (CORE["E_PERM"], CORE["E_SWAP"]), (CORE["E_SWAP"], CORE["E_OTP"]),
                  (CORE["E_LAST_HOP"], CORE["E_ATM"]), (CORE["E_ATM"], CORE["E_ANPR"])]


# ============================================================ NOISE INJECT ===
PLATE_ALIASES: dict[str, set] = {}


def bg_msisdn(i): return f"+9198{RNG.randint(10000000, 99999999)}"


def build_noise():
    global GT_CAUSAL
    bg_imei = [f"3{RNG.randint(10**13, 10**14 - 1)}" for _ in range(90)]
    bg_macs = [":".join(f"{RNG.randint(0,255):02X}" for _ in range(6)) for _ in range(120)]
    bg_vpa = [f"user{RNG.randint(1000,9999)}@{RNG.choice(['okaxis','ybl','ibl','paytm','okhdfcbank'])}"
              for _ in range(70)]
    bg_plates = [f"DL{RNG.randint(1,13)}C{RNG.choice('ABDEFGHJK')}{RNG.choice('ABDEFGHJK')}"
                 f"{RNG.randint(1000,9999)}" for _ in range(40)]
    handler_decoys = [bg_msisdn(0), bg_msisdn(1)]

    # 200 background subscriber CDR records, each anchored to a single site
    for i in range(200):
        site = RNG.choices(list(CGI.keys()), weights=[1, 1, 5, 2])[0]
        t = T("13:20:00") + RNG.uniform(0, 7200)
        imei = RNG.choice(bg_imei)
        etype = RNG.choices(["CELL_ATTACH", "VOICE_CALL", "SMS_OUT", "SMS_IN"],
                            weights=[5, 3, 1, 1])[0]
        peer = RNG.choice(handler_decoys) if (i % 97 == 0) else bg_msisdn(i)
        add_cdr(t, etype, imei=imei, msisdn=bg_msisdn(i), peer=(peer if etype != "CELL_ATTACH" else ""),
                site=site, dur=(str(RNG.randint(5, 400)) if etype == "VOICE_CALL" else ""),
                azimuth=(RNG.random() > 0.12))
    # 2 decoy callers to the handler number, so its degree is realistic (not 2)
    for p in handler_decoys:
        add_cdr(T("13:25:00") + RNG.uniform(0, 600), "VOICE_CALL", imei=RNG.choice(bg_imei),
                msisdn=p, peer=MSISDN_HANDLER, site="CP", dur="22")

    # 150 background Wi-Fi associations at the Connaught Place cafe AP
    for i in range(150):
        t = T("13:30:00") + RNG.uniform(0, 6600)
        mac = RNG.choice(bg_macs)
        add_wifi(t, RNG.choices(["WIFI_ASSOC", "WIFI_DHCPACK", "WIFI_DISASSOC"],
                                weights=[5, 2, 2])[0], mac, BSSID_CAFE, "CP_CAFE",
                 ip=f"10.42.7.{RNG.randint(20,250)}",
                 xid=(f"0x{RNG.randint(0x10000000,0xFFFFFFFF):08X}" if RNG.random() < 0.4 else ""))

    # 120 benign UPI transfers
    for i in range(120):
        t = T("13:20:00") + RNG.uniform(0, 7200)
        a, b = RNG.sample(bg_vpa, 2)
        add_bank(t, "UPI_CREDIT_TXN", a, b, round(RNG.uniform(60, 9000), 2),
                 rrn=f"{RNG.randint(10**11, 10**12 - 1)}")

    # background ANPR traffic (each plate seen at exactly one camera site)
    for i, p in enumerate(bg_plates):
        site = RNG.choice(list(CAM.keys()))
        t = T("13:20:00") + RNG.uniform(0, 7000)
        shown = p
        if RNG.random() < 0.25:   # OCR character substitution noise
            k = RNG.randrange(len(p))
            inv = {v: k2 for k2, v in C.HOMOGLYPH.items()}
            shown = p[:k] + inv.get(p[k], p[k]) + p[k + 1:]
        PLATE_ALIASES.setdefault(p, set()).add(shown)
        add_cctv(t, shown, site, terminal=(ATM_TERMINAL if site == "NEHRU" else ""))

    # benign ATM withdrawals at the same terminal (gives the hub realistic degree)
    for i in range(6):
        t = T("13:20:00") + RNG.uniform(0, 6000)
        trig = f"TRIG_NP09_{7100 + i * 37}"
        add_bank(t, "ATM_CASH_WDL", RNG.choice(bg_vpa), f"4{RNG.randint(10**3,10**4-1)}-XXXX-{RNG.randint(1000,9999)}",
                 round(RNG.randrange(500, 20000, 500), 2), terminal=ATM_TERMINAL,
                 trig=trig, site="NEHRU", channel="ATM")
        add_cctv(t, "", "NEHRU", trig=trig, terminal=ATM_TERMINAL, conf=1.0,
                 etype="ATM_DISPENSER_TRIGGER")
        bp = RNG.choice(bg_plates)
        PLATE_ALIASES.setdefault(bp, set()).add(bp)
        add_cctv(t + RNG.uniform(6, 16), bp, "NEHRU", terminal=ATM_TERMINAL)

    # UFDR filler: deleted call-log rows + package usage of the burner handset
    for i in range(14):
        add_ufdr(T("13:40:00") + RNG.uniform(0, 5000), "CALL_LOG_ENTRY", "BURNER_HANDSET",
                 imei=IMEI_BURNER, peer=bg_msisdn(i), deleted=(i % 2 == 0),
                 body="recovered from SQLite freelist page" if i % 2 == 0 else "active row")
    for i in range(8):
        add_ufdr(T("13:45:00") + RNG.uniform(0, 4800), "PACKAGE_USAGE", "BURNER_HANDSET",
                 imei=IMEI_BURNER, body=f"foreground usage of {RNG.choice(['com.android.chrome','com.whatsapp','mock.gps.pro','com.phonepe.app'])}")

    # background GPS pings for the personal handset (pre/post operation)
    for i, (hm, site, paired) in enumerate([("13:22:00", "LAJPAT", False), ("13:40:00", "KAROL", True),
                                            ("14:05:00", "CP", True), ("15:30:00", "CP", True),
                                            ("15:45:00", "CP", False)]):
        seq = str(117800000 + i * 97000)
        if paired:
            pair_gps(T(hm), site, seq)
        else:
            add_gps(T(hm), IMEI_PERSON, site, handover=seq)


# ========================================================== JPEG + EXIF ======
def _ascii_tag(tag, value):
    b = value.encode("ascii") + b"\x00"
    return tag, 2, len(b), b


def build_tampered_jpeg(path: str):
    orig = "2026:11:18 15:11:12"          # DVR wall-clock at capture (raw, skewed)
    modified = "2026:11:18 17:11:12"      # re-encode 2 hours later via FFmpeg
    sub_entries = [_ascii_tag(0x9003, orig), _ascii_tag(0x9004, orig)]
    ifd0_entries = [_ascii_tag(0x0131, "Lavf60.16.100"), _ascii_tag(0x0132, modified)]

    def pack_ifd(entries, base_off, extra_ptr=None):
        n = len(entries) + (1 if extra_ptr is not None else 0)
        data_off = base_off + 2 + 12 * n + 4
        head, blob = b"", b""
        for tag, typ, cnt, payload in entries:
            if len(payload) <= 4:
                val = payload + b"\x00" * (4 - len(payload))
            else:
                val = struct.pack("<I", data_off + len(blob))
                blob += payload
            head += struct.pack("<HHI4s", tag, typ, cnt, val)
        return head, blob, data_off

    # layout: TIFF hdr(8) | IFD0 | IFD0 data | ExifIFD | ExifIFD data
    h0, b0, d0 = pack_ifd(ifd0_entries, 8, extra_ptr=True)
    exif_ifd_off = d0 + len(b0)
    h0 += struct.pack("<HHI4s", 0x8769, 4, 1, struct.pack("<I", exif_ifd_off))
    hs, bs, ds = pack_ifd(sub_entries, exif_ifd_off)
    tiff = (b"II\x2a\x00" + struct.pack("<I", 8) +
            struct.pack("<H", len(ifd0_entries) + 1) + h0 + struct.pack("<I", 0) + b0 +
            struct.pack("<H", len(sub_entries)) + hs + struct.pack("<I", 0) + bs)
    app1 = b"\xFF\xE1" + struct.pack(">H", len(tiff) + 8) + b"Exif\x00\x00" + tiff

    body = None
    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (320, 180), (18, 20, 26))
        d = ImageDraw.Draw(im)
        d.rectangle([12, 12, 308, 168], outline=(90, 200, 255))
        d.text((24, 36), "ATM_NP_09  CAM_NP_09", fill=(220, 235, 255))
        d.text((24, 60), "2026-11-18 15:11:12 (DVR)", fill=(220, 235, 255))
        d.text((24, 96), "PLATE: DL8CAF5O31", fill=(255, 210, 120))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        raw_jpg = buf.getvalue()
        body = raw_jpg[2:]                      # strip SOI, keep the rest
    except Exception:
        body = b"\xFF\xD9"
    with open(path, "wb") as f:
        f.write(b"\xFF\xD8" + app1 + body)


# ============================================================= WRITE OUT =====
def write_csv(path, rows, cols, eol=CRLF):
    with open(path, "wb") as f:
        f.write((",".join(cols) + eol).encode("utf-8"))
        for r in rows:
            vals = []
            for c in cols:
                v = str(r.get(c, ""))
                vals.append(f'"{v}"' if ("," in v or '"' in v) else v)
            f.write((",".join(vals) + eol).encode("utf-8"))


def generate(data_dir: str | None = None) -> dict:
    data_dir = data_dir or C.DATA_DIR
    os.makedirs(data_dir, exist_ok=True)
    build_core()
    build_noise()

    cdr.sort(key=lambda r: r["timestamp_utc"]); wifi.sort(key=lambda r: r["timestamp_utc"])
    bank.sort(key=lambda r: r["timestamp_utc"]); cctv.sort(key=lambda r: r["timestamp_utc"])
    gps.sort(key=lambda r: r["timestamp_utc"]); ufdr.sort(key=lambda r: r["timestamp_local_utc"])

    # event ids are (file_id, record_index) based, so re-map after sorting
    remap = {}
    for buf, fid, key in ((cdr, "SRC_CDR_01", "record_id"), (wifi, "SRC_WIFI_01", "record_id"),
                          (bank, "SRC_BANK_01", "record_id"), (cctv, "SRC_CCTV_01", "record_id"),
                          (gps, "SRC_GPS_01", "record_id"), (ufdr, "SRC_UFDR_01", "event_raw_id")):
        for new_i, row in enumerate(buf):
            remap[(fid, row[key])] = ev_id(fid, new_i)

    def fix(old_eid):
        fid, idx = old_eid.split("#")
        buf, key = {"SRC_CDR_01": (cdr, "record_id"), "SRC_WIFI_01": (wifi, "record_id"),
                    "SRC_BANK_01": (bank, "record_id"), "SRC_CCTV_01": (cctv, "record_id"),
                    "SRC_GPS_01": (gps, "record_id"), "SRC_UFDR_01": (ufdr, "event_raw_id")}[fid]
        pref = {"SRC_CDR_01": "CDR", "SRC_WIFI_01": "WIFI", "SRC_BANK_01": "BNK",
                "SRC_CCTV_01": "CCTV", "SRC_GPS_01": "GPS", "SRC_UFDR_01": "UFDR"}[fid]
        n = int(idx) + 1
        rid = f"{pref}{n:05d}" if pref != "BNK" else f"BNK{n:05d}"
        return remap[(fid, rid)]

    core = {k: (fix(v) if isinstance(v, str) else [fix(x) for x in v]) for k, v in CORE.items()}
    gt_causal = [[fix(a), fix(b)] for a, b in GT_CAUSAL]

    write_csv(os.path.join(data_dir, "telecom_cdr_dump.csv"), cdr,
              ["record_id", "timestamp_utc", "event_type", "imei", "imsi", "msisdn",
               "peer_msisdn", "cgi", "azimuth_deg", "lat", "lon", "duration_s",
               "sms_pdu_hash", "rrn", "cell_label"])
    write_csv(os.path.join(data_dir, "cp_router_syslog.csv"), wifi,
              ["record_id", "timestamp_utc", "event_type", "mac_addr", "bssid", "ap_label",
               "ip_addr", "dhcp_xid", "lat", "lon", "rssi_dbm"])
    write_csv(os.path.join(data_dir, "npci_upi_atm_switch.csv"), bank,
              ["record_id", "timestamp_utc", "event_type", "actor_acct", "target_acct",
               "amount_inr", "rrn", "terminal_id", "atm_term_trig", "lat", "lon", "channel"])
    write_csv(os.path.join(data_dir, "nehru_place_cctv_anpr.csv"), cctv,
              ["record_id", "timestamp_utc", "event_type", "plate_ocr", "terminal_id",
               "atm_term_trig", "camera_id", "lat", "lon", "frame_file", "ocr_confidence"])
    write_csv(os.path.join(data_dir, "personal_phone_loc.csv"), gps,
              ["record_id", "timestamp_utc", "event_type", "imei", "lat", "lon",
               "accuracy_m", "provider", "uptime_ms", "handover_seq"], eol="\n")
    with open(os.path.join(data_dir, "suspect_burner_ufdr.json"), "wb") as f:
        f.write(b'{\n  "extraction_tool": "KALA-NETRA reference UFDR export v3",\n')
        f.write(b'  "devices": ["BURNER_HANDSET", "VICTIM_HANDSET"],\n  "events": [\n')
        for i, o in enumerate(ufdr):
            line = json.dumps(o, ensure_ascii=False, separators=(", ", ": "))
            f.write(b"    " + line.encode("utf-8") + (b",\n" if i < len(ufdr) - 1 else b"\n"))
        f.write(b"  ]\n}\n")
    build_tampered_jpeg(os.path.join(data_dir, FRAME_FILE))

    gt = {
        "case_id": C.CASE_ID, "case_title": C.CASE_TITLE,
        "clock_offsets_true": {fid: BETA[fid] for fid in BETA},
        "entity_clusters": [
            [["IMEI", IMEI_PERSON], ["IMEI", IMEI_BURNER], ["IMSI", IMSI_BURNER],
             ["IMSI", IMSI_V_SWAP], ["MAC_ADDR", MAC_BURNER],
             ["VEHICLE_PLATE", PLATE_TRUE], ["VEHICLE_PLATE", PLATE_OCR]],
            [["IMEI", IMEI_V], ["IMSI", IMSI_V]],
        ] + [[["VEHICLE_PLATE", x] for x in sorted(al)]
             for al in PLATE_ALIASES.values() if len(al) > 1],
        "causal_edges": gt_causal,
        "spoof_event_id": core["E_SPOOF_GPS"],
        "split_custody_event_id": core["E_SPLIT_PERSON"],
        "mule_accounts": MULES, "cashout_account": CASHOUT,
        "victim_account": ACCOUNT_V, "siphoned_total_inr": 450000.0,
        "cashout_total_inr": 444000.00,
        "core_event_ids": core,
        "record_counts": {"SRC_CDR_01": len(cdr), "SRC_UFDR_01": len(ufdr),
                          "SRC_WIFI_01": len(wifi), "SRC_BANK_01": len(bank),
                          "SRC_CCTV_01": len(cctv), "SRC_GPS_01": len(gps)},
        "tampered_frame": FRAME_FILE,
    }
    with open(os.path.join(data_dir, "ground_truth.json"), "w") as f:
        json.dump(gt, f, indent=2)
    return gt


if __name__ == "__main__":
    g = generate()
    print(json.dumps(g["record_counts"], indent=2))
    print("total records:", sum(g["record_counts"].values()))
