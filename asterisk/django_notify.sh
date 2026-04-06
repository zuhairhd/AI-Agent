#!/bin/bash
# ============================================================
# Asterisk AGI Script — Notify Django of new call recording
# Place this in /var/lib/asterisk/agi-bin/
# chmod +x django_notify.sh
# ============================================================

CALLER_NUMBER="$1"
AUDIO_FILE_PATH="$2"
DJANGO_URL="http://localhost:8000/api/call/"
ASTERISK_SECRET="your-shared-secret-here"

# Log to Asterisk
echo "VERBOSE \"Notifying Django: caller=${CALLER_NUMBER} file=${AUDIO_FILE_PATH}\" 1"

# Send to Django
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${DJANGO_URL}" \
  -H "Content-Type: application/json" \
  -H "X-Asterisk-Secret: ${ASTERISK_SECRET}" \
  -d "{\"caller_number\": \"${CALLER_NUMBER}\", \"audio_file_path\": \"${AUDIO_FILE_PATH}\"}" \
  --max-time 10)

echo "VERBOSE \"Django responded: HTTP ${RESPONSE}\" 1"

if [ "${RESPONSE}" != "202" ]; then
  echo "VERBOSE \"Warning: Django returned non-202 status: ${RESPONSE}\" 1"
fi
