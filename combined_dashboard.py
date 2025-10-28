# streamlit_app.py  — Zen Monkey Capital CSV Dashboard (Streamlit-native)
import os
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

# ---------------- Setup ----------------
st.set_page_config(page_title="Zen Monkey Capital — CSV Dashboard", layout="wide")

RAW_BASE_DEFAULT = "https://raw.githubusercontent.com/mingchen112001-crypto/csv-dashboard/main/data"
RAW_BASE = os.getenv("RAW_BASE", RAW_BASE_DEFAULT)

SOURCES = [
    {"id": "bestcalloption",  "title": "Best Call Options",            "file": "best_option.csv"},
    #{"id": "coveredcall", "title": "Covered Call Income",     "file": "covered_call_income.csv"},
    #{"id": "bestput",     "title": "Best Put Option",         "file": "best_put.csv"},
    #{"id": "putincome",   "title": "Cash Secured Put Income", "file": "put_income.csv"},
    #{"id": "ivspike",     "title": "IV Spike Log",            "file": "iv_spike_log.csv"},
    {"id": "finalcandidates",     "title": "Final Candidates",            "file": "final_candidates.csv"},
    {"id": "opencsp",     "title": "Open CSPs",            "file": "open_csp.csv"},
    {"id": "dtecluster",     "title": "DTE Cluster",            "file": "DTE_cluster.csv"},
]

# ---------------- Helpers ----------------
def _parse_raw_base(raw_base: str):
    """Parse raw.githubusercontent base into (owner, repo, branch, base_path) or (None, None, None, "")."""
    try:
        from urllib.parse import urlparse
        p = urlparse(raw_base)
        parts = p.path.strip("/").split("/")
        if len(parts) < 4:
            return None, None, None, ""
        owner, repo, branch = parts[0], parts[1], parts[2]
        base_path = "/".join(parts[3:])
        return owner, repo, branch, base_path
    except Exception:
        return None, None, None, ""

@st.cache_data(ttl=300)
def fetch_last_modified_et_from_raw(url: str) -> str:
    """HEAD the raw file; convert Last-Modified/Date to ET. Cached for 5 minutes."""
    try:
        r = requests.head(url, timeout=10)
        stamp = r.headers.get("Last-Modified") or r.headers.get("Date")
        if not stamp:
            return "unknown"
        import email.utils as eut
        dt_utc = eut.parsedate_to_datetime(stamp)
        dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%Y-%m-%d %H:%M ET")
    except Exception:
        return "unknown"

@st.cache_data(ttl=120)
def load_csv(url: str) -> pd.DataFrame:
    """Load CSV from a raw GitHub URL to DataFrame. Cached for 2 minutes."""
    try:
        return pd.read_csv(url)
    except Exception as e:
        # fallback: GET then read
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return pd.read_csv(io.BytesIO(r.content))
        except Exception:
            raise RuntimeError(str(e))

# ---------------- UI ----------------
with st.sidebar:
    st.markdown("### Data Source")
    raw_base_in = st.text_input(
        "RAW_BASE (raw GitHub base URL)",
        value=RAW_BASE,
        help="Points to the folder that contains your CSVs. Example:\n"
             "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/data"
    )
    st.caption("You can change this without redeploying.")
RAW_BASE = raw_base_in or RAW_BASE_DEFAULT

now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET")
st.markdown(
    "<h2 style='margin:0'>🪙 Zen Monkey Capital — CSV Dashboard</h2>"
    "<div style='color:#C9A227;opacity:0.85;margin-bottom:8px'>Yield with control is music.</div>",
    unsafe_allow_html=True,
)
st.write(f"**Fetched (ET):** {now_et}")

tabs = st.tabs([s["title"] for s in SOURCES])

for src, tab in zip(SOURCES, tabs):
    with tab:
        url = RAW_BASE.rstrip("/") + "/" + src["file"]
        last_mod_et = fetch_last_modified_et_from_raw(url)

        st.markdown(
            f"**Source:** [{src['file']}]({url})"
            f"  |  **Last updated (ET):** {last_mod_et}"
            f"  |  **Fetched (ET):** {now_et}"
        )

        try:
            df = load_csv(url)
            if df.empty:
                st.info("No rows to display.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name=src["file"],
                    mime="text/csv",
                )
        except Exception as e:
            st.error(f"Error loading `{src['file']}` from {url}: {e}")

st.caption("© Zen Monkey Capital — Streamlit dashboard. Data pulled from raw GitHub URLs.")
