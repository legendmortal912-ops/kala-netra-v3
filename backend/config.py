"""KALA-NETRA V3 — central deterministic configuration.

Every magic number used by the correlation engine lives here so that an
investigator (or a defence expert) can audit and re-run the pipeline with
different, explicitly stated assumptions.
"""
from __future__ import annotations
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "out")
DB_PATH = os.path.join(OUT_DIR, "kala_netra.sqlite")
GROUND_TRUTH = os.path.join(DATA_DIR, "ground_truth.json")

CASE_ID = "FIR-0442/2026 (CYBER-PS-NDLS)"
CASE_TITLE = "Coordinated SIM-Swap & Mule Cash-Out Heist"

# ---------------------------------------------------------------- sources ----
# index -> (file_id, filename, pretty label, sigma seconds, true offset beta)
SOURCES = [
    (0, "SRC_CDR_01",  "telecom_cdr_dump.csv",      "Telecom CDR Switch",   0.5,    0.0),
    (1, "SRC_UFDR_01", "suspect_burner_ufdr.json",  "Mobile Handset UFDR",  2.0,   45.0),
    (2, "SRC_WIFI_01", "cp_router_syslog.csv",      "Enterprise Wi-Fi AP",  1.0,  -12.0),
    (3, "SRC_BANK_01", "npci_upi_atm_switch.csv",   "NPCI / Bank Switch",   0.5,    0.0),
    (4, "SRC_CCTV_01", "nehru_place_cctv_anpr.csv", "ATM CCTV DVR + ANPR",  5.0, -360.0),
    (5, "SRC_GPS_01",  "personal_phone_loc.csv",    "Handset GPS Log",      2.0,   45.0),
]
REFERENCE_SOURCE = 0
SIGMA = {s[1]: s[4] for s in SOURCES}
FILE_LABEL = {s[1]: s[3] for s in SOURCES}
FILENAME = {s[1]: s[2] for s in SOURCES}
SOURCE_INDEX = {s[1]: s[0] for s in SOURCES}

# ------------------------------------------------------- clock-sync solver ---
ANCHOR_RESIDUAL_Z = 3.5          # standardized residual rejection threshold

# -------------------------------------------------- entity resolution --------
LINK_THRESHOLD = 0.65
W_STRUCT, W_ST = 0.40, 0.60   # calibrated on the benchmark (see README)
GAMMA_AA = 0.75
CLUSTER_RATE = 0.9               # reward rate for co-location across distinct sites
CONVOY_MIN_SITES = 3             # convoy rule: co-travel across >= 3 distinct sites
CONVOY_MIN_SCORE = 0.70          # ... and strong per-site co-occurrence
HUB_WEIGHT = {"MSISDN": 1.0, "UPI_VPA": 1.0, "BANK_ACCT": 1.0, "WIFI_BSSID": 0.8,
              "ATM_TERMINAL": 0.8, "APK_HASH": 1.0, "IP_ADDR": 0.6,
              "CELL_TOWER_CGI": 0.3}
ST_WINDOW_S = 900.0
LEN_D = 150.0
LEN_T = 300.0
DISTINCT_CLUSTER_M = 1000.0
BURNER_ST_MIN = 0.70
CANDIDATE_TYPES = {"IMEI", "IMSI", "MSISDN", "MAC_ADDR", "BANK_ACCT",
                   "UPI_VPA", "VEHICLE_PLATE"}
HUB_TYPES = {"CELL_TOWER_CGI", "WIFI_BSSID", "ATM_TERMINAL", "IP_ADDR", "APK_HASH"}
HOMOGLYPH = {"O": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "Q": "0"}
PLATE_RE = r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$"

# ----------------------------------------------------------- kinematics ------
EARTH_R = 6_371_000.0
V_MAX = 33.3                     # m/s  (120 km/h urban surface ceiling)
KAPPA_ROAD = 1.0                 # benefit of the doubt: straight-line travel
UNCERTAINTY_R = {"ATM_TERMINAL": 15.0, "CCTV_DVR": 15.0, "WIFI_BSSID": 45.0,
                 "GPS": 20.0, "CELL_TOWER_CGI": 500.0, "DEFAULT": 50.0}
PHYSICAL_LAYER = {"WIFI_ASSOC", "WIFI_DHCP", "CELL_ATTACH", "ATM_CASH_WDL",
                  "CCTV_ANPR_SIGHTING", "VOICE_CALL", "SMS_OUT", "SMS_IN"}
APP_LAYER = {"GPS_PING"}

# --------------------------------------------------------------- causal ------
CAUSAL_WINDOW_S = 7200.0
CAUSAL_MIN_SCORE = 0.25

# -------------------------------------------------------------- finance ------
MULE_HALF_LIFE = 600.0
MULE_SCORE_MIN = 0.80

# ------------------------------------------------------------ hypotheses -----
REDUNDANCY_WINDOW_S = 60.0

# ------------------------------------------------------------- multimedia ----
EXIF_MISMATCH_S = 5.0
EDITOR_FINGERPRINTS = ["Lavf", "FFmpeg", "ffmpeg", "Adobe Photoshop", "GIMP", "ExifTool"]
