#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Installing dependencies"
python3 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q -r requirements.txt

echo "==> Generating PWA icons"
.venv/bin/python scripts/generate_icons.py

echo "==> Verifying PWA assets"
for f in static/manifest.json static/icon-192.png static/icon-512.png static/offline.html; do
  test -f "$f" || { echo "Missing $f"; exit 1; }
done

echo "==> PWA build complete"
echo "Run: .venv/bin/streamlit run app.py"
echo "Open: http://localhost:8501"
echo "Install: Use browser menu → Install app / Add to Home Screen"
