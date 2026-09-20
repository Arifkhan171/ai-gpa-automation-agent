#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# AcadTrack — Module 8 Frontend Setup Script
# Run from inside the gpa-agentic-system/ root directory
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         AcadTrack Frontend — Module 8 Setup                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Node version
NODE_VERSION=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1)
if [ -z "$NODE_VERSION" ] || [ "$NODE_VERSION" -lt 18 ]; then
  echo "❌  Node.js 18+ is required. Current: $(node -v 2>/dev/null || echo 'not found')"
  exit 1
fi
echo "✅  Node.js $(node -v) detected"

# Move into frontend
cd "$(dirname "$0")/frontend"
echo "📂  Working in: $(pwd)"
echo ""

# Install dependencies
echo "📦  Installing dependencies (this takes ~60 seconds)…"
npm install --legacy-peer-deps
echo ""

# Done
echo "✅  All packages installed."
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Start the dev server:                                       ║"
echo "║    cd frontend && npm run dev                                ║"
echo "║                                                              ║"
echo "║  Then open:  http://localhost:3000                           ║"
echo "║                                                              ║"
echo "║  Test credentials:                                           ║"
echo "║    coordinator / Coord@123  →  /dashboard/upload            ║"
echo "║    <roll_no>   / Student@123  →  /portal                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
