"""Kenneth R. French data library: daily factor returns.

Files are zipped CSVs with a free-text preamble, a header row beginning with a
comma, rows keyed by YYYYMMDD, and a copyright footer. Values are in percent
and are converted to decimal returns.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Dict, Optional

import pandas as pd

from .http import HttpClient

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

DATASETS: Dict[str, str] = {
    "ff3_daily": "F-F_Research_Data_Factors_daily_CSV.zip",
    "ff5_daily": "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "momentum_daily": "F-F_Momentum_Factor_daily_CSV.zip",
}

_DATE_ROW = re.compile(r"^\s*(\d{8})\s*,")


def parse_french_csv(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith(",") and re.search(r"[A-Za-z]", line):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("no header row found in French CSV")
    columns = [c.strip() for c in lines[header_idx].split(",")[1:]]
    rows = []
    for line in lines[header_idx + 1 :]:
        m = _DATE_ROW.match(line)
        if not m:
            if rows:  # first non-data line after the block ends the daily table
                break
            continue
        parts = [p.strip() for p in line.split(",")]
        rows.append([parts[0]] + parts[1 : 1 + len(columns)])
    df = pd.DataFrame(rows, columns=["date"] + columns)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df = df.set_index("date")
    for c in columns:
        v = pd.to_numeric(df[c], errors="coerce")
        v = v.mask(v <= -99.0)  # -99.99 / -999 mark missing values in the library
        df[c] = v / 100.0
    df.index.name = "date"
    return df


def parse_french_zip(data: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("zip holds no CSV")
        return parse_french_csv(z.read(names[0]).decode("latin1"))


def fetch_factors(name: str = "ff3_daily", http: Optional[HttpClient] = None) -> pd.DataFrame:
    if name not in DATASETS:
        raise KeyError(f"unknown dataset {name!r}; known: {sorted(DATASETS)}")
    http = http or HttpClient()
    resp = http.get(BASE + DATASETS[name], use_cache=http.cache_dir is not None)
    if not resp.ok:
        raise RuntimeError(f"French library {name}: HTTP {resp.status}")
    return parse_french_zip(resp.body)
