#!/usr/bin/env bash
# install_hooks.sh — configure git to use .githooks/ in this repo
#
# Usage:  bash scripts/install_hooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "Configuring git hooks path to .githooks/ …"
git config core.hooksPath .githooks

echo "Making hooks executable …"
chmod +x .githooks/pre-push

echo "Done. The pre-push coverage gate is now active."
echo "To uninstall: git config --unset core.hooksPath"
