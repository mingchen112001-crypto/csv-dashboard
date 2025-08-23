# app.py
from flask import Flask, render_template_string
import os
import pandas as pd
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # add at the top with imports

app = Flask(__name__)

# ---- Configuration ----
# Prefer environment variable; fallback to a sane default pattern.
# Example: https://raw.githubusercontent.com/<USER>/<REPO>/<BRANCH>/<FOLDER>/
RAW_BASE = os.getenv(
    "RAW_BASE",
    "https://raw.githubusercontent.com/mingchen112001-crypto/csv-dashboard/main/data"  # <-- change me
)

# Put your CSV files here (title + filename relative to RAW_BASE)
SOURCES = [
    {"id": "bestoption",  "title": "Best Options",            "file": "best_option.csv"},
    {"id": "coveredcall", "title": "Covered Call Income",     "file": "covered_call_income.csv"},
    {"id": "bestput",     "title": "Best Put Option",         "file": "best_put.csv"},
    {"id": "putincome",   "title": "Cash Secured Put Income", "file": "put_income.csv"},
    {"id": "ivspike",     "title": "IV Spike Log",            "file": "iv_spike_log.csv"},
]

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
  </style>
</head>
<body>
<div class="container-fluid">
  <h3 class="mb-3">CSV Dashboard</h3>

  <ul class="nav nav-tabs" id="tabs" role="tablist">
    {% for t in tables %}
      <li class="nav-item">
        <a class="nav-link {% if loop.first %}active{% endif %}" id="{{t.id}}-tab" data-toggle="tab" href="#{{t.id}}"
           role="tab" aria-controls="{{t.id}}" aria-selected="{{ 'true' if loop.first else 'false' }}">{{ t.title }}</a>
      </li>
    {% endfor %}
  </ul>

  <div class="tab-content">
    {% for t in tables %}
      <div class="tab-pane fade {% if loop.first %}show active{% endif %}" id="{{t.id}}" role="tabpanel" aria-labelledby="{{t.id}}-tab">
        <div class="meta">
          <strong>Source:</strong> <a href="{{ t.url }}" target="_blank">{{ t.file }}</a>
          {% if t.last_modified %} | <strong>Last updated (GitHub):</strong> {{ t.last_modified }}{% endif %}
          | <strong>Fetched (server time):</strong> {{ t.fetched_at }}
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
    // Initialize all tables via class hook
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
  });
</script>
</body>
</html>
"""

def fetch_last_modified(url: str) -> str | None:
    """Try to get Last-Modified from GitHub raw; return ISO string or None."""
    try:
        r = requests.head(url, timeout=15)
        if r.status_code == 200:
            lm = r.headers.get("Last-Modified")
            if lm:
                # Normalize to ISO (browser-friendly)
                try:
                    dt = datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S %Z")
                    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception:
                    return lm  # fallback to raw string
    except Exception:
        pass
    return None

@app.route("/")
def index():
    tables = []
    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S ET")

    for src in SOURCES:
        url = RAW_BASE.rstrip("/") + "/" + src["file"]
        last_mod = fetch_last_modified(url)

        # Load CSV to DataFrame -> HTML
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
            "last_modified": last_mod,
            "fetched_at": now_et,
            "html": html
        })

    return render_template_string(HTML, tables=tables)

if __name__ == "__main__":
    # Useful for local testing; on Render, gunicorn will import app:app and ignore this.
    app.run(host="0.0.0.0", port=5055)