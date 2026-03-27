#!/usr/bin/env bash
# tools/build_docs.sh — Regenerate module docs and build the Sphinx HTML site.
#
# Usage:
#   ./tools/build_docs.sh                  # full pipeline (generate modules + docs)
#   ./tools/build_docs.sh --docs-only      # skip module generation, just rebuild docs
#   ./tools/build_docs.sh --serve          # full pipeline + start local HTTP server
#   ./tools/build_docs.sh --docs-only --serve


set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/venv"
INSTALLED_MODULES="$VENV_DIR/lib/python3.11/site-packages/ansible_collections/pfrest/pfsense/plugins/modules"
DOCS_DIR="$REPO_ROOT/docs"
SCHEMA="$REPO_ROOT/schema.json"

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
DOCS_ONLY=false
SERVE=false
PORT=8282

for arg in "$@"; do
    case "$arg" in
        --docs-only) DOCS_ONLY=true ;;
        --serve)     SERVE=true ;;
        --port=*)    PORT="${arg#--port=}" ;;
        *)           echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# Activate venv if not already active
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    echo "Activating venv..."
    source "$VENV_DIR/bin/activate"
fi

# Generate modules from schema
if [[ "$DOCS_ONLY" == false ]]; then
    echo "==> Generating Ansible modules from schema..."
    python "$REPO_ROOT/tools/module_generator.py" "$SCHEMA"
    echo ""
fi

# Sync workspace modules → installed collection
echo "==> Syncing modules to installed collection..."
cp "$REPO_ROOT/plugins/modules/"*.py "$INSTALLED_MODULES/"
echo "    Copied $(ls "$REPO_ROOT/plugins/modules/"*.py | wc -l | tr -d ' ') modules."

# Clear __pycache__
echo "==> Clearing __pycache__..."
find "$VENV_DIR/lib/python3.11/site-packages/ansible_collections/pfrest" \
    -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT/plugins" \
    -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Generate RST with antsibull-docs
echo "==> Generating RST documentation with antsibull-docs..."
rm -rf "$DOCS_DIR/collections"
antsibull-docs \
    collection \
    --use-current \
    --dest-dir "$DOCS_DIR" \
    --cleanup everything \
    pfrest.pfsense

# Quick validation — count ERROR lines
ERRORS=$(antsibull-docs collection --use-current --dest-dir "$DOCS_DIR" --cleanup everything pfrest.pfsense 2>&1 | grep -c "ERROR" || true)
if [[ "$ERRORS" -gt 0 ]]; then
    echo "    ⚠  antsibull-docs reported $ERRORS error(s). Check output above."
else
    echo "    ✓  No validation errors."
fi

# Build HTML with Sphinx
echo "==> Building HTML with Sphinx..."
rm -rf "$DOCS_DIR/_build"
sphinx-build -b html "$DOCS_DIR" "$DOCS_DIR/_build/html" 2>&1 | tail -5
echo ""
echo "==> Documentation built successfully: $DOCS_DIR/_build/html"

# Serve locally (if requested)
if [[ "$SERVE" == true ]]; then
    # Kill any existing server on the port
    lsof -ti:"$PORT" | xargs kill 2>/dev/null || true
    sleep 0.5
    echo "==> Serving docs at http://localhost:$PORT  (Ctrl+C to stop)"
    cd "$DOCS_DIR/_build/html"
    python3 -m http.server "$PORT"
fi

