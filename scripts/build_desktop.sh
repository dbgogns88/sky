#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
APP_NAME="Sky Order Converter"

echo "==> Installing desktop dependencies"
python3 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q -r requirements.txt -r requirements-desktop.txt

echo "==> Building ${APP_NAME}.app (this may take a few minutes)"
.venv/bin/pyinstaller sky_order_converter.spec --noconfirm

echo ""
echo "==> Desktop build complete"
echo "App location: ${ROOT}/dist/${APP_NAME}.app"
echo ""
echo "To run without building:"
echo "  .venv/bin/python desktop.py"
