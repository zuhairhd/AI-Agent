#!/usr/bin/env bash
set -euo pipefail

CALLER_NUMBER="${1:-unknown}"
AUDIO_FILE_PATH="${2:-}"

if [ -z "$AUDIO_FILE_PATH" ]; then
  echo "ERROR: missing audio file path" >&2
  exit 1
fi

BASE_URL="http://127.0.0.1:8000"

SUBMIT_JSON=$(curl -s -X POST "${BASE_URL}/api/call/" \
  -H "Content-Type: application/json" \
  -d "{\"caller_number\":\"${CALLER_NUMBER}\",\"audio_file_path\":\"${AUDIO_FILE_PATH}\"}")

CALL_ID=$(echo "$SUBMIT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['call_id'])")

for i in $(seq 1 15); do
  STATUS_JSON=$(curl -s "${BASE_URL}/api/call-status/${CALL_ID}/")
  HAS_AUDIO=$(echo "$STATUS_JSON" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('has_audio', False)).lower())")

  if [ "$HAS_AUDIO" = "true" ]; then
    AUDIO_PATH=$(echo "$STATUS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['response_audio_path'])")
    cp "$AUDIO_PATH" /var/lib/asterisk/sounds/ai_reply.wav
    echo "READY"
    exit 0
  fi

  sleep 2
done

echo "TIMEOUT"
exit 2
