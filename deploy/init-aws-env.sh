#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$ ]]; then
  echo "Usage: $0 your-public-hostname" >&2
  exit 2
fi

target="$(cd "$(dirname "$0")" && pwd)/aws.env"
if [[ -e "$target" ]]; then
  echo "Refusing to replace existing $target" >&2
  exit 1
fi

python3 - "$target" "$1" <<'PY'
import os
import secrets
import sys

path, domain = sys.argv[1:]
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
with os.fdopen(os.open(path, flags, 0o600), "w") as file:
    file.write(f"APP_DOMAIN={domain}\n")
    file.write(f"POSTGRES_PASSWORD={secrets.token_urlsafe(36)}\n")
    file.write(f"DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}\n")
    file.write("ASSET_BASE_URL=\n")
print(f"Created {path} with private credentials (mode 600).")
PY
