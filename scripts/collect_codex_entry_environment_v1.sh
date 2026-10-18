#!/usr/bin/env bash
set -uo pipefail

repo=/home/bigdata/Desktop/arknights-auto-planner
out=${KIMIARK_ENTRY_DIAG_OUT:-/tmp/kimiark_entry_diag/server_terminal}
mkdir -p "$out"

cd "$repo"

{
  echo "user=$(id -un)"
  echo "uid=$(id -u)"
  echo "cwd=$PWD"
  echo "codex_path=$(command -v codex 2>/dev/null || echo NOT_FOUND)"
  echo "codex_resolved=$(readlink -f "$(command -v codex)" 2>/dev/null || echo UNKNOWN)"
  codex --version 2>&1
  echo "HOME=${HOME-}"
  echo "CODEX_HOME=${CODEX_HOME-}"
  echo "HTTP_PROXY=${HTTP_PROXY-}"
  echo "HTTPS_PROXY=${HTTPS_PROXY-}"
  echo "ALL_PROXY=${ALL_PROXY-}"
  echo "NO_PROXY=${NO_PROXY-}"
  echo "http_proxy=${http_proxy-}"
  echo "https_proxy=${https_proxy-}"
  echo "all_proxy=${all_proxy-}"
  echo "no_proxy=${no_proxy-}"
  echo "login_status"
  codex login status 2>&1
  echo "listeners"
  ss -ltnp | grep -E ':7890|:7891|:9090' || true
  echo "proxy_preflight"
  curl --proxy "${HTTPS_PROXY:-http://127.0.0.1:7890}" \
    --connect-timeout 4 --max-time 12 -sS -D - -o /dev/null \
    https://chatgpt.com/ 2>&1 | sed -E 's/(authorization|set-cookie):.*/\1: REDACTED/I'
  echo "doctor_default_json_path=$out/doctor_default.json"
  codex doctor --json > "$out/doctor_default.json" 2> "$out/doctor_default.stderr" || true
  echo "doctor_override_json_path=$out/doctor_override.json"
  codex -c 'model_provider="openai"' -m gpt-6.1-sol \
    -c 'model_reasoning_effort="high"' -c 'features.apps=false' \
    doctor --json > "$out/doctor_override.json" 2> "$out/doctor_override.stderr" || true
} | tee "$out/environment_report.txt"

python3 - <<'PY'
import json
import os
from pathlib import Path
out = Path(os.environ.get("KIMIARK_ENTRY_DIAG_OUT", "/tmp/kimiark_entry_diag/server_terminal"))
for name in ("doctor_default.json", "doctor_override.json"):
    path = out / name
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        print(f"{name}: INVALID_JSON {exc}")
        continue
    checks = payload.get("checks", {})
    for key in ("auth.credentials", "config.load", "network.env", "network.provider_reachability", "network.websocket_reachability"):
        value = checks.get(key)
        if value:
            print(f"{name}:{key}:{value.get('status')}:{value.get('summary')}")
PY
