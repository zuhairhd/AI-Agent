#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/agent/voice_ai_agent"
ASTERISK_SRC="$APP_DIR/asterisk"

ASTERISK_ETC="/etc/asterisk"
AGI_DST="/var/lib/asterisk/agi-bin/voice_agent.agi"

SUDO_PASSWORD="${DEPLOY_SUDO_PASSWORD:-}"

run_sudo() {
    if [ -z "$SUDO_PASSWORD" ]; then
        echo "DEPLOY_SUDO_PASSWORD is not set"
        exit 1
    fi
    printf '%s\n' "$SUDO_PASSWORD" | sudo -S "$@"
}

step() {
    echo "==> $1"
}

echo "==> Starting deploy on server"

cd "$APP_DIR"

step "Converting deploy and Asterisk files to Linux line endings"
sed -i 's/\r$//' "$APP_DIR/deploy_server.sh" || true
sed -i 's/\r$//' "$ASTERISK_SRC/voice_agent.agi" || true
sed -i 's/\r$//' "$ASTERISK_SRC/extensions.conf" || true
sed -i 's/\r$//' "$ASTERISK_SRC/pjsip.conf" || true
find "$APP_DIR/asterisk" -maxdepth 1 -type f \( -name "*.py" -o -name "*.sh" \) -exec sed -i 's/\r$//' {} \; 2>/dev/null || true

step "Verifying important files exist"
[ -f "$ASTERISK_SRC/voice_agent.agi" ] || { echo "Missing: $ASTERISK_SRC/voice_agent.agi"; exit 1; }
[ -f "$ASTERISK_SRC/extensions.conf" ] || { echo "Missing: $ASTERISK_SRC/extensions.conf"; exit 1; }
[ -f "$ASTERISK_SRC/pjsip.conf" ] || { echo "Missing: $ASTERISK_SRC/pjsip.conf"; exit 1; }

step "Running Django checks"
source venv/bin/activate
python manage.py check
python manage.py migrate

step "Warning if model changes are missing migrations"
python manage.py makemigrations --check --dry-run || true

step "Backing up live Asterisk files"
run_sudo cp "$ASTERISK_ETC/extensions.conf" "$ASTERISK_ETC/extensions.conf.bak.$(date +%F_%H-%M-%S)" || true
run_sudo cp "$ASTERISK_ETC/pjsip.conf" "$ASTERISK_ETC/pjsip.conf.bak.$(date +%F_%H-%M-%S)" || true
run_sudo cp "$AGI_DST" "${AGI_DST}.bak.$(date +%F_%H-%M-%S)" || true

step "Copying Asterisk files"
run_sudo cp "$ASTERISK_SRC/extensions.conf" "$ASTERISK_ETC/extensions.conf"
run_sudo cp "$ASTERISK_SRC/pjsip.conf" "$ASTERISK_ETC/pjsip.conf"
run_sudo cp "$ASTERISK_SRC/voice_agent.agi" "$AGI_DST"

step "Fixing AGI permissions"
run_sudo chmod 755 "$AGI_DST"

step "Restarting app services"
run_sudo systemctl restart voice_ai_gunicorn
run_sudo systemctl restart voice_ai_celery_worker

step "Reloading Asterisk"
run_sudo asterisk -rx "dialplan reload"
run_sudo asterisk -rx "pjsip reload"

step "Health check"
curl -s http://127.0.0.1:8000/api/health/ || true
echo

echo "==> Deploy completed successfully"
