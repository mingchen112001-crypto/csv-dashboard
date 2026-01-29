# app.py
from flask import Flask, render_template_string
import os
import pandas as pd
import requests
import email.utils
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+

# -------------------------------------------------------------------
# SAFETY GUARD: Never start Flask inside Streamlit Cloud / Streamlit run
# Streamlit sets environment variables like STREAMLIT_SERVER_PORT.
# If we accidentally start Flask, it will block or conflict on port 5055.
# -------------------------------------------------------------------
IS_STREAMLIT_RUNTIME = bool(
    os.getenv("STREAMLIT_SERVER_PORT")
    or os.getenv("STREAMLIT_SERVER_HEADLESS")
    or os.getenv("STREAMLIT_RUNTIME")
)

app = Flask(__name__)

# ---- Configuration ----
RAW_BASE = os.getenv(
    "RAW_BASE",
    "https://raw.githubusercontent.com/mingchen112001-crypto/csv-dashboard/main/data"
)

SOURCES = [
    {"id": "finalcandidates",     "title": "Final Candidates",            "file": "final_candidates.csv"},
    {"id": "etffinalcandidates",     "title": "ETF Final Candidates",            "file": "etf_final_candidates.csv"},
    {"id": "toptrimcandidates",     "title": "Top Trim Candidates",            "file": "web_top_trim.csv"},
    {"id": "rollrecommendation",     "title": "Roll Recommendations",            "file": "roll_recommendations.csv"},
    {"id": "portfoliosummary",     "title": "Portfolio Summary",            "file": "web_portfolio_summary.csv"},
    {"id": "earlyprofit",     "title": "Early Profit",            "file": "web_early_profit.csv"},
    ]

def _parse_raw_base(raw_base: str):
    """
    Parse RAW_BASE like:
      https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<base_path...>
    Returns (owner, repo, branch, base_path) or (None, None, None, None) if not parseable.
    """
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

def fetch_last_modified_et_from_raw(url: str) -> str:
    """Fallback: HEAD the raw file; convert Last-Modified/Date to ET."""
    try:
        r = requests.head(url, timeout=10)
        stamp = r.headers.get("Last-Modified") or r.headers.get("Date")
        if not stamp:
            return "unknown"
        dt_utc = email.utils.parsedate_to_datetime(stamp)
        dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%Y-%m-%d %H:%M ET")
    except Exception:
        return "unknown"

def fetch_last_commit_time_et(owner: str, repo: str, branch: str, base_path: str, filename: str) -> str | None:
    """
    Use GitHub API to get the latest commit that touched base_path/filename.
    Returns ET string or None on failure/rate-limit.
    """
    try:
        path = f"{base_path}/{filename}".lstrip("/")
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"path": path, "sha": branch, "per_page": 1}
        headers = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        # Prefer committer date; fall back to author date
        commit = data[0].get("commit", {})
        iso = commit.get("committer", {}).get("date") or commit.get("author", {}).get("date")
        if not iso:
            return None
        # Parse ISO 8601 (e.g., 2025-08-24T14:20:31Z)
        dt_utc = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%Y-%m-%d %H:%M ET")
    except Exception:
        return None

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CSV Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <!-- Bootstrap + DataTables -->
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.datatables.net/1.10.21/css/jquery.dataTables.min.css">

  <style>
    body { padding-top: 16px; }
    .meta { font-size: 0.9rem; color: #555; margin-bottom: 8px; }
    .tab-pane { padding-top: 10px; }
    .nav-link small { font-weight: normal; }
  </style>
</head>
<body>
<div class="container-fluid">
  <h3 class="mb-3">CSV Dashboard</h3>

  <ul class="nav nav-tabs" id="tabs" role="tablist">
    {% for t in tables %}
      <li class="nav-item">
        <a class="nav-link {% if loop.first %}active{% endif %}" id="{{t.id}}-tab" data-toggle="tab" href="#{{t.id}}"
           role="tab" aria-controls="{{t.id}}" aria-selected="{{ 'true' if loop.first else 'false' }}">
           {{ t.title }}
           <small class="text-muted">({{ t.last_modified }})</small>
        </a>
      </li>
    {% endfor %}
  </ul>

  <div class="tab-content">
    {% for t in tables %}
      <div class="tab-pane fade {% if loop.first %}show active{% endif %}" id="{{t.id}}" role="tabpanel" aria-labelledby="{{t.id}}-tab">
        <div class="meta">
          <strong>Source:</strong> <a href="{{ t.url }}" target="_blank">{{ t.file }}</a>
          | <strong>Last updated (GitHub, ET):</strong> {{ t.last_modified }}
          | <strong>Fetched (ET):</strong> {{ t.fetched_at }}
        </div>
        {{ t.html | safe }}
      </div>
    {% endfor %}
  </div>
</div>

<!-- JS -->
<script src="https://code.jquery.com/jquery-3.5.1.js"></script>
<script src="https://cdn.datatables.net/1.10.21/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js"></script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>

<script>
  $(function () {
    // Initialize all tables
    $('table.dataframe').each(function() {
      $(this)
        .addClass('table table-striped datatable')
        .DataTable({ pageLength: 25 });
    });

    // Bootstrap tabs
    $('.nav-tabs a').on('click', function (e) {
      e.preventDefault();
      $(this).tab('show');
    });

    // Show first tab on load
    $('.nav-tabs a:first').tab('show');
  });
</script>
</body>
</html>
"""

@app.route("/")
def index():
    tables = []
    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET")

    owner, repo, branch, base_path = _parse_raw_base(RAW_BASE)

    for src in SOURCES:
        url = RAW_BASE.rstrip("/") + "/" + src["file"]

        # Prefer GitHub API commit time; fallback to Raw last-modified/date
        last_mod_et = None
        if owner and repo and branch is not None:
            last_mod_et = fetch_last_commit_time_et(owner, repo, branch, base_path, src["file"])
        if not last_mod_et:
            last_mod_et = fetch_last_modified_et_from_raw(url)

        # Load CSV -> HTML
        try:
            df = pd.read_csv(url)
            html = df.to_html(index=False, table_id=f"table_{src['id']}", classes="display")
        except Exception as e:
            html = f'<div class="alert alert-danger">Error loading <a href="{url}" target="_blank">{src["file"]}</a>: {e}</div>'

        tables.append({
            "id": src["id"],
            "title": src["title"],
            "file": src["file"],
            "url": url,
            "last_modified": last_mod_et,
            "fetched_at": now_et,
            "html": html
        })

    return render_template_string(HTML, tables=tables)

if __name__ == "__main__":
    # IMPORTANT:
    # This file contains BOTH a Flask app and a Streamlit app.
    # Streamlit Cloud / `streamlit run` executes this file, so we must NEVER
    # start Flask in that runtime (it will block and/or conflict on port 5055).
    #
    # To run the Flask dev server locally, explicitly set RUN_FLASK=1 AND ensure
    # you are NOT in a Streamlit runtime.
    if (not IS_STREAMLIT_RUNTIME) and (os.getenv("RUN_FLASK") == "1"):
        app.run(host="0.0.0.0", port=5055)

# Streamlit dashboard (converted from Flask)
# You can deploy this file directly on Streamlit Cloud.
# If your host expects a specific filename (e.g., streamlit_app.py), simply rename this file.

import os
import io
import pandas as pd
import requests
import email.utils
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

# ---------------- Configuration ----------------
st.set_page_config(page_title="Zen Monkey Capital — CSV Dashboard", layout="wide")
st.write("🚀 Streamlit app starting…")

RAW_BASE_DEFAULT = "https://raw.githubusercontent.com/mingchen112001-crypto/csv-dashboard/main/data"
RAW_BASE = os.getenv("RAW_BASE", RAW_BASE_DEFAULT)
## the list of CSV sources to display
SOURCES = [
    {"id": "finalcandidates",     "title": "Final Candidates",            "file": "final_candidates.csv"},
    {"id": "etffinalcandidates",     "title": "ETF Final Candidates",            "file": "etf_final_candidates.csv"},
    {"id": "toptrimcandidates",     "title": "Top Trim Candidates",            "file": "web_top_trim.csv"},
    {"id": "rollrecommendation",     "title": "Roll Recommendations",            "file": "roll_recommendations.csv"},
    {"id": "portfoliosummary",     "title": "Portfolio Summary",            "file": "web_portfolio_summary.csv"},
    {"id": "earlyprofit",     "title": "Early Profit",            "file": "web_early_profit.csv"},
    ]

# --------------- Helpers ----------------
def _parse_raw_base(raw_base: str):
    """
    Parse RAW_BASE like:
      https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<base_path...>
    Returns (owner, repo, branch, base_path) or (None, None, None, "") if not parseable.
    """
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
        dt_utc = email.utils.parsedate_to_datetime(stamp)
        dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%Y-%m-%d %H:%M ET")
    except Exception:
        return "unknown"

@st.cache_data(ttl=300)
def fetch_last_commit_time_et(owner: str, repo: str, branch: str, base_path: str, filename: str) -> str | None:
    """
    Use GitHub API to get the latest commit that touched base_path/filename.
    Returns ET string or None on failure/rate-limit.
    """
    try:
        path = f"{base_path}/{filename}".lstrip("/")
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"path": path, "sha": branch, "per_page": 1}
        headers = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        commit = data[0].get("commit", {})
        iso = commit.get("committer", {}).get("date") or commit.get("author", {}).get("date")
        if not iso:
            return None
        dt_utc = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%Y-%m-%d %H:%M ET")
    except Exception:
        return None

@st.cache_data(ttl=120)
def load_csv(url: str) -> pd.DataFrame:
    """Load CSV from a raw GitHub URL to DataFrame. Cached for 2 minutes."""
    try:
        # pandas can read directly from raw URLs
        return pd.read_csv(url)
    except Exception as e:
        # Try fallback: fetch then read_csv on bytes
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return pd.read_csv(io.BytesIO(r.content))
        except Exception:
            # Return empty DF with error message in Streamlit layer
            raise RuntimeError(str(e))

# ---------------- Sidebar Controls ----------------
with st.sidebar:
    st.markdown("### Data Source")
    raw_base_in = st.text_input(
        "RAW_BASE (raw GitHub base URL)",
        value=RAW_BASE,
        help="raw.githubusercontent URL that points to the base folder containing your CSV files."
    )
    st.caption("Example: https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path-to-data>")

RAW_BASE = raw_base_in or RAW_BASE_DEFAULT
owner, repo, branch, base_path = _parse_raw_base(RAW_BASE)
now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET")

# ---------------- Main Layout ----------------
st.title("Zen Monkey Capital — CSV Dashboard")
st.write(f"**Fetched (ET):** {now_et}")

tab_titles = [s["title"] for s in SOURCES]
tabs = st.tabs(tab_titles)

for src, tab in zip(SOURCES, tabs):
    with tab:
        url = RAW_BASE.rstrip("/") + "/" + src["file"]

        # Last updated metadata
        last_mod_et = None
        if owner and repo and branch is not None:
            last_mod_et = fetch_last_commit_time_et(owner, repo, branch, base_path, src["file"])
        if not last_mod_et:
            last_mod_et = fetch_last_modified_et_from_raw(url)

        st.markdown(
            f"**Source:** [{src['file']}]({url})  |  **Last updated (GitHub, ET):** {last_mod_et}  |  **Fetched (ET):** {now_et}"
        )

        # Load & render table
        try:
            df = load_csv(url)
            if df.empty:
                st.info("No rows to display.")
            else:
                # Improve default rendering
                st.dataframe(df, use_container_width=True, hide_index=True)
                # Optional CSV download
                csv_bytes = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download CSV",
                    data=csv_bytes,
                    file_name=src["file"],
                    mime="text/csv",
                    help="Save a copy of this table locally."
                )
        except Exception as e:
            st.error(f"Error loading `{src['file']}` from {url}: {e}")

# Footer
st.caption("© Zen Monkey Capital — Streamlit dashboard. Data pulled from raw GitHub URLs.")