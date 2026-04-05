#!/bin/bash
# ============================================================
# Voice AI Agent — Ubuntu Server Setup Script
# Run as: sudo bash deploy/setup.sh
# ============================================================
set -e

PROJECT_DIR=/opt/voice_ai_agent
VENV_DIR=$PROJECT_DIR/venv
LOG_DIR=/var/log/voice_ai_agent
USER=ubuntu

echo "=== [1/8] Installing system packages ==="
apt-get update -q
apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib redis-server nginx curl

echo "=== [2/8] Creating log directory ==="
mkdir -p $LOG_DIR
chown $USER:$USER $LOG_DIR
mkdir -p /media/calls
chown $USER:www-data /media/calls
mkdir -p /company_docs
chown $USER:$USER /company_docs

echo "=== [3/8] Setting up PostgreSQL ==="
sudo -u postgres psql -c "CREATE USER voice_ai_user WITH PASSWORD 'change_this_password';" || true
sudo -u postgres psql -c "CREATE DATABASE voice_ai_db OWNER voice_ai_user;" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE voice_ai_db TO voice_ai_user;" || true

echo "=== [4/8] Setting up Python virtualenv ==="
python3 -m venv $VENV_DIR
$VENV_DIR/bin/pip install --upgrade pip
$VENV_DIR/bin/pip install -r $PROJECT_DIR/requirements.txt

echo "=== [5/8] Django setup ==="
cd $PROJECT_DIR
$VENV_DIR/bin/python manage.py collectstatic --noinput --settings=config.settings.production
$VENV_DIR/bin/python manage.py migrate --settings=config.settings.production

echo "=== [6/8] Installing systemd services ==="
cp deploy/gunicorn.service   /etc/systemd/system/voice_ai_gunicorn.service
cp deploy/celery_worker.service /etc/systemd/system/voice_ai_celery_worker.service
cp deploy/celery_beat.service   /etc/systemd/system/voice_ai_celery_beat.service
cp deploy/watchdog.service      /etc/systemd/system/voice_ai_watchdog.service

systemctl daemon-reload
systemctl enable voice_ai_gunicorn voice_ai_celery_worker voice_ai_celery_beat voice_ai_watchdog
systemctl start  voice_ai_gunicorn voice_ai_celery_worker voice_ai_celery_beat voice_ai_watchdog

echo "=== [7/8] Nginx setup ==="
cp deploy/nginx.conf /etc/nginx/sites-available/voice_ai_agent
ln -sf /etc/nginx/sites-available/voice_ai_agent /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo "=== [8/8] AGI script setup ==="
cp asterisk/django_notify.sh /var/lib/asterisk/agi-bin/django_notify.sh
chmod +x /var/lib/asterisk/agi-bin/django_notify.sh
chown asterisk:asterisk /var/lib/asterisk/agi-bin/django_notify.sh

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Copy .env.example to .env and fill in all values"
echo "  2. Update deploy/nginx.conf with your domain"
echo "  3. Add your Asterisk dialplan from asterisk/extensions.conf"
echo "  4. Create a Django superuser: $VENV_DIR/bin/python manage.py createsuperuser"
