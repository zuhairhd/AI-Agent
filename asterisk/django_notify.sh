#!/bin/bash
# =============================================================================
# hangup_notify.sh — called by Asterisk h-extension on caller disconnect
#
# Usage (from extensions.conf):
#   exten => h,1,System(/var/lib/asterisk/agi-bin/django_notify.sh ${SESSION_ID})
#
# If SESSION_ID is empty (call dropped before AGI started a session),
# the script exits silently — nothing to update.
# =============================================================================

SESSION_ID="$1"
DJANGO_URL="${DJANGO_API_BASE_URL:-http://127.0.0.1:8000}"
ASTERISK_SECRET="${ASTERISK_SECRET:-}"

if [ -z "${SESSION_ID}" ]; then
  logger -t asterisk-hangup "SESSION_ID empty — no backend update needed"
  exit 0
fi

ENDPOINT="${DJANGO_URL}/api/session/${SESSION_ID}/hangup/"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${ENDPOINT}" \
  -H "Content-Type: application/json" \
  -H "X-Asterisk-Secret: ${ASTERISK_SECRET}" \
  -d '{}' \
  --max-time 10)

logger -t asterisk-hangup \
  "session=${SESSION_ID} endpoint=${ENDPOINT} http=${HTTP_CODE}"

if [ "${HTTP_CODE}" != "200" ]; then
  logger -t asterisk-hangup \
    "WARNING: hangup notify returned HTTP ${HTTP_CODE} for session=${SESSION_ID}"
fi
