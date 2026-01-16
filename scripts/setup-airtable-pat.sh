#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v direnv >/dev/null 2>&1; then
  echo "direnv is not installed. Install it first:"
  echo "  brew install direnv"
  exit 1
fi

ENV_FILE="$ROOT_DIR/.env"
ENVRC_FILE="$ROOT_DIR/.envrc"

if [[ -f "$ENV_FILE" ]]; then
  echo ".env already exists. Move or delete it if you want to replace the PAT."
  exit 1
fi

read -r -s -p "Paste Airtable PAT (input hidden): " AIRTABLE_PAT
echo

if [[ -z "$AIRTABLE_PAT" ]]; then
  echo "No PAT provided. Aborting."
  exit 1
fi

if [[ "$AIRTABLE_PAT" != pat* ]]; then
  echo "Warning: PATs usually start with 'pat'. Continue anyway."
fi

umask 077
printf "AIRTABLE_API_KEY=%s\n" "$AIRTABLE_PAT" > "$ENV_FILE"

cat > "$ENVRC_FILE" <<'EOF'
dotenv .env
EOF

direnv allow "$ENVRC_FILE"

echo "Done. PAT stored in .env (gitignored)."
echo "You can now run: pixi run crm mirror doctor airtable"
