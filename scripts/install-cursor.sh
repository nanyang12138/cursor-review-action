#!/usr/bin/env bash
set -euo pipefail

if command -v agent >/dev/null 2>&1; then
  agent --version
  exit 0
fi

curl https://cursor.com/install -fsS | bash
echo "$HOME/.local/bin" >> "$GITHUB_PATH"

export PATH="$HOME/.local/bin:$PATH"
agent --version
