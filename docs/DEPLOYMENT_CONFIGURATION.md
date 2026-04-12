# Voice AI Agent — Deployment Configuration Reference

This document is written for a **technician installing this system on a new Ubuntu 22 server**.
It lists every static, deployment-specific, and environment-specific value that must be reviewed and set before the system can operate correctly.

---

## Table of Contents

1. [Overview — where configuration lives](#1-overview)
2. [Pre-flight checklist](#2-pre-flight-checklist)
3. [Django `.env` file](#3-django-env-file)
4. [Asterisk configuration files](#4-asterisk-configuration-files)
5. [Systemd service files](#5-systemd-service-files)
6. [Nginx configuration](#6-nginx-configuration)
7. [Setup script (`setup.sh`)](#7-setup-script)
8. [Portal / Admin-managed values](#8-portal--admin-managed-values)
9. [Values intentionally kept in code](#9-values-intentionally-kept-in-code)
10. [Restart reference](#10-restart-reference)
11. [Security checklist](#11-security-checklist)

---

## 1. Overview

| Layer | Where | Who sets it |
|---|---|---|
| Environment / server-specific | `.env` file (root of project) | Installer / technician |
| Telephony / hardware | `asterisk/pjsip.conf`, `asterisk/extensions.conf` | Installer / Asterisk admin |
| Reverse proxy | `deploy/nginx.conf` | Installer |
| Process manager | `deploy/voice_ai_gunicorn.service` etc. | Installer |
| Business / operational | Django Admin → SiteConfig, Alert settings | System operator / admin user |
| Technical constants | Python source code | Developer only |

---

## 2. Pre-flight Checklist

Before running `setup.sh` on a new server, confirm:

- [ ] Ubuntu 22.04 LTS installed
- [ ] Server has a static IP address or a domain name
- [ ] Asterisk installed and Asterisk user (`asterisk`) exists
- [ ] OpenAI account with API key and vector store available
- [ ] SMTP credentials (e.g. Gmail app password) are ready
- [ ] A strong random secret key generated: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`
- [ ] A strong Asterisk bridge secret generated: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- [ ] The `.env` file fully filled in from `env.example`

---

## 3. Django `.env` File

**File path:** `/home/agent/voice_ai_agent/.env`  
**Requires service restart:** Yes — all services after any change.

Copy `env.example` to `.env` and set every value below.

### 3.1 Django Core

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Session signing, CSRF tokens — must be unique and secret | 60-char random string | **Yes — always** |
| `DJANGO_DEBUG` | Debug mode — must be `False` in production | `False` | Yes — set `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames/IPs Django accepts | `192.168.1.10,yourdomain.com` | **Yes — always** |

### 3.2 Deployment URLs

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `APP_BASE_URL` | Base URL embedded in email links and callback URLs | `http://192.168.1.10` or `https://yourdomain.com` | **Yes — always** |
| `PORTAL_BASE_URL` | Base URL of the Vue portal (used in alert email links) | `http://192.168.1.10` | **Yes — always** |
| `CORS_ALLOWED_ORIGINS` | Origins allowed to make API requests from a browser | `http://192.168.1.10` | **Yes — always** |
| `DJANGO_API_BASE_URL` | URL Asterisk AGI uses to reach Django — keep as localhost | `http://127.0.0.1:8000` | Only if ports change |

> **Note:** `APP_BASE_URL` has **no hardcoded default** in production settings.  
> If it is missing from `.env`, the application will start but email links will be broken and a warning will be logged.

### 3.3 PostgreSQL Database

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `DB_NAME` | Database name | `voice_ai_db` | Usually no |
| `DB_USER` | Database username | `voice_ai_user` | Usually no |
| `DB_PASSWORD` | Database password | strong random password | **Yes — always** |
| `DB_HOST` | Database host | `localhost` | Only if remote DB |
| `DB_PORT` | Database port | `5432` | Only if non-standard |

> The database password set here **must match** the password created during `setup.sh` step 3.

### 3.4 Redis / Celery

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `CELERY_BROKER_URL` | Celery task queue broker | `redis://localhost:6379/0` | Only if Redis is remote or password-protected |
| `CELERY_RESULT_BACKEND` | Celery result storage | `redis://localhost:6379/1` | Only if Redis is remote or password-protected |

> If Redis is exposed to the network, add authentication: `redis://:yourpassword@localhost:6379/0`

### 3.5 OpenAI

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `OPENAI_API_KEY` | OpenAI API authentication | `sk-...` | **Yes — always** |
| `OPENAI_VECTOR_STORE_ID` | ID of the knowledge base vector store | `vs_...` | Yes (see below) |

**How to get `OPENAI_VECTOR_STORE_ID` on a fresh install:**

1. Leave `OPENAI_VECTOR_STORE_ID` blank in `.env` on first run.
2. Upload a document via the Django admin.
3. Check Celery worker logs: `journalctl -u voice_ai_celery_worker -f`
4. Look for the line: `NEW VECTOR STORE CREATED: vs_xxxx`
5. Set that value in `.env` and restart all services.

### 3.6 Email (SMTP)

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `EMAIL_BACKEND` | Email sending backend | `django.core.mail.backends.smtp.EmailBackend` | Usually no |
| `EMAIL_HOST` | SMTP server hostname | `smtp.gmail.com` | Yes if not Gmail |
| `EMAIL_PORT` | SMTP port | `587` | Yes if not TLS/587 |
| `EMAIL_USE_TLS` | Use TLS | `True` | Usually no |
| `EMAIL_HOST_USER` | SMTP username / sender address | `alerts@yourcompany.com` | **Yes — always** |
| `EMAIL_HOST_PASSWORD` | SMTP password or app password | Gmail app password | **Yes — always** |
| `DEFAULT_FROM_EMAIL` | "From" name and address in sent emails | `"ACME Support <alerts@acme.com>"` | **Yes — always** |
| `PORTAL_NOTIFICATION_EMAILS` | Comma-separated emails that receive alert notifications | `admin@acme.com,ops@acme.com` | **Yes — always** |

**Gmail App Password steps:**

1. Google Account → Security → 2-Step Verification (must be enabled)
2. Security → App passwords → Select app: Mail → Select device: Other
3. Copy the generated 16-character password into `EMAIL_HOST_PASSWORD`

### 3.7 Asterisk Bridge

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `ASTERISK_SECRET` | Shared secret between Asterisk AGI and Django API | 64-char hex string | **Yes — always** |

> This secret must be set in **both** `.env` (for Django) **and** in `/etc/asterisk/asterisk.env` (for the AGI scripts and shell notify scripts to pick up).

### 3.8 Asterisk / Telephony Settings

| Variable | What it controls | Default | Change every install? |
|---|---|---|---|
| `HUMAN_TRANSFER_EXTENSION` | PJSIP endpoint name for human agent handoff | `agent200` | Only if endpoint name differs |
| `MAX_CONVERSATION_TURNS` | Max AI turns before forced handoff/hangup | `10` | Optional tuning |
| `TURN_RECORD_TIMEOUT` | Max recording time per turn (seconds) | `30` | Optional tuning |
| `TURN_SILENCE_TIMEOUT` | Silence that ends recording (seconds) | `5` | Optional tuning |
| `WELCOME_SOUND_NAME` | Base filename of welcome sound (no extension) | `welcome_future_smart` | If sound file renamed |
| `ASTERISK_RECORDINGS_DIR` | Absolute path to Asterisk monitor directory | `/var/spool/asterisk/monitor` | Only if custom path |
| `ASTERISK_SOUNDS_DIR` | Absolute path to Asterisk custom sounds directory | `/var/lib/asterisk/sounds/custom` | Only if custom path |

### 3.9 File System Paths

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `MEDIA_ROOT` | Where Django stores call audio | `/home/agent/voice_ai_agent/media/calls` | Yes if project path differs |
| `COMPANY_DOCS_ROOT` | Where Django reads knowledge-base documents | `/home/agent/voice_ai_agent/company_docs` | Yes if project path differs |
| `LOG_FILE` | Application log file path | `/var/log/voice_ai_agent/app.log` | Optional |

### 3.10 Branding

| Variable | What it controls | Example value | Change every install? |
|---|---|---|---|
| `COMPANY_NAME` | Company name used in AI responses and email subjects | `Acme Support` | **Yes — always** |
| `ALERT_CONFIDENCE_THRESHOLD` | Minimum AI confidence to raise an alert | `0.6` | Optional tuning |

---

## 4. Asterisk Configuration Files

These files live in the project's `asterisk/` directory and must be copied to `/etc/asterisk/` or included from there.

### 4.1 `asterisk/pjsip.conf`

**Install path:** `/etc/asterisk/pjsip.conf`  
**Requires Asterisk reload:** `asterisk -rx "pjsip reload"`

#### Values requiring change on every installation

| Section | Parameter | What it is | Example |
|---|---|---|---|
| `[ht813]` (auth) | `password=` | Password the HT813 ATA uses to register with Asterisk | Strong random password |
| `[agent200]` (auth) | `password=CHANGE_ME_AGENT200_PASSWORD` | Password the agent softphone uses to register | Strong random password |

> **Important:** The HT813 ATA must be configured with the **same password** as the `[ht813]` auth section here.  
> Configure HT813 at its web interface: FXO Port → SIP User ID / Authenticate ID / Password.

#### Values that may need adjustment per installation

| Section | Parameter | What it is | Notes |
|---|---|---|---|
| `[transport-udp]` | `bind=0.0.0.0:5060` | SIP listens on all interfaces | Change if SIP should bind to a specific IP only |
| `[agent200]` | `username=agent200` | Agent softphone SIP username | Change if using different extension naming |

### 4.2 `asterisk/extensions.conf`

**Install path:** `/etc/asterisk/extensions.conf`  
**Requires Asterisk reload:** `asterisk -rx "dialplan reload"`

#### Values to review on every installation

| Section | Variable | What it is | Notes |
|---|---|---|---|
| `[globals]` | `HUMAN_AGENT_ENDPOINT=agent200` | PJSIP endpoint name for human agent transfer | Must match `[agent200]` in `pjsip.conf` and `HUMAN_TRANSFER_EXTENSION` in `.env` |
| `[globals]` | `AGI_SCRIPT=` | Absolute path to the AGI script | Change if installed in non-standard location |
| `[globals]` | `HANGUP_SCRIPT=` | Absolute path to the hangup notify script | Change if installed in non-standard location |
| `[internal]` | `exten => 200,1` | Internal extension for agent 200 | Change if using different internal extension number |

### 4.3 Asterisk Environment File

Create `/etc/asterisk/asterisk.env` so that AGI scripts and shell scripts pick up secrets from the environment rather than hardcoded values:

```
# /etc/asterisk/asterisk.env
DJANGO_API_BASE_URL=http://127.0.0.1:8000
ASTERISK_SECRET=<same value as in Django .env>
MAX_CONVERSATION_TURNS=10
TURN_RECORD_TIMEOUT=30
TURN_SILENCE_TIMEOUT=5
ASTERISK_RECORDINGS_DIR=/var/spool/asterisk/monitor
WELCOME_SOUND_NAME=welcome_future_smart
```

Then load it from `/etc/asterisk/asterisk.conf` by adding:

```ini
[options]
execincludes = yes
```

And at the top of your dialplan (or in `asterisk.conf`) source the file before running AGI, or pass the env file to Asterisk's systemd service unit:

```ini
# In /etc/systemd/system/asterisk.service [Service] section:
EnvironmentFile=/etc/asterisk/asterisk.env
```

---

## 5. Systemd Service Files

### 5.1 `deploy/voice_ai_gunicorn.service`

**Install path:** `/etc/systemd/system/voice_ai_gunicorn.service`

| Line | What to set | Notes |
|---|---|---|
| `User=agent` | OS user that runs Gunicorn | Change if your project user is different |
| `Group=agent` | OS group | Change to match |
| `WorkingDirectory=` | Absolute path to the project root | Change if installed elsewhere |
| `--bind 127.0.0.1:8000` | Gunicorn listens on loopback only | **Do not change to 0.0.0.0** — Nginx is the public-facing reverse proxy |
| `--workers 3` | Number of worker processes | Tune: `(2 × CPU cores) + 1` |

After editing: `sudo systemctl daemon-reload && sudo systemctl restart voice_ai_gunicorn`

### 5.2 `deploy/celery_worker.service` and `celery_beat.service`

| Line | What to set | Notes |
|---|---|---|
| `User=ubuntu` | **Must be changed** to match your project user | Should match Gunicorn user |
| `WorkingDirectory=/opt/voice_ai_agent` | **Must be changed** to actual project path | |
| `--logfile=` | Log file path | Change if using different log path |

> Note: The `celery_worker.service` and `celery_beat.service` reference `/opt/voice_ai_agent` while the Gunicorn service uses `/home/agent/voice_ai_agent`. Reconcile these to use the same path on your installation.

### 5.3 `deploy/watchdog.service`

Review `User=`, `WorkingDirectory=`, and log file paths for consistency with the rest of your deployment.

---

## 6. Nginx Configuration

**File:** `deploy/nginx.conf`  
**Install path:** `/etc/nginx/sites-available/voice_ai_agent`

| Line | What to set | Notes |
|---|---|---|
| `server_name your-domain.com;` | **Must be changed** to your server's hostname or IP | |
| `alias /opt/voice_ai_agent/staticfiles/;` | **Must be changed** to match your project path | |
| `alias /media/calls/;` | **Must be changed** to match your `MEDIA_ROOT` | |
| `client_max_body_size 50M;` | Max upload size | Tune if your audio files are larger |
| `proxy_read_timeout 120s;` | Timeout for proxied requests | Increase if TTS takes longer |

After editing:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 7. Setup Script (`deploy/setup.sh`)

The setup script (`sudo bash deploy/setup.sh`) will:

1. Install system packages (Python, PostgreSQL, Redis, Nginx)
2. Create log and media directories
3. **Prompt you to enter a PostgreSQL password** — this will become `DB_PASSWORD` in `.env`
4. Create the virtualenv and install Python packages
5. Run Django migrations and collectstatic
6. Install and enable systemd services
7. Configure Nginx
8. Install the Asterisk AGI script

**Before running setup.sh:**

- Create and fill in your `.env` file (from `env.example`)
- Ensure your server's project path matches the paths in the service files

**Paths hardcoded in `setup.sh` that may need adjustment:**

| Variable | Value | Notes |
|---|---|---|
| `PROJECT_DIR` | `/opt/voice_ai_agent` | Change if project lives elsewhere |
| `LOG_DIR` | `/var/log/voice_ai_agent` | Standard; usually fine |
| `USER` | `ubuntu` | Change to your actual OS user |
| `/media/calls` | Media directory | Change to match `MEDIA_ROOT` |
| `/company_docs` | Docs directory | Change to match `COMPANY_DOCS_ROOT` |

---

## 8. Portal / Admin-Managed Values

The following values are **intentionally managed through the Django admin or portal** and must not be moved to code or `.env`. An operator can change these at runtime without restarting any service.

| Setting | Where in admin | What it controls |
|---|---|---|
| `SiteConfig.company_name` | Admin → Site Config | Company name used in AI responses and emails |
| `SiteConfig.contact_email` | Admin → Site Config | Contact email shown to callers (if applicable) |
| Alert notification recipients | Admin → Portal Notification Settings | Who receives alert emails per alert type |
| Alert severity thresholds | Admin → Alerts | Which call outcomes trigger alerts |
| Follow-up workflow settings | Admin → Follow-ups | How follow-up items are created and assigned |
| Knowledge base documents | Admin → RAG Sync | Company documents used by the AI |

---

## 9. Values Intentionally Kept in Code

The following values are hardcoded in source code because they are **technical constants or framework defaults**, not deployment-specific values.

| Location | Value | Why it stays in code |
|---|---|---|
| `apps/asterisk_bridge/views.py:120` | `'127.0.0.1', '::1', 'localhost'` | Localhost loopback addresses are technical constants |
| `apps/voice_calls/models.py` | Status enum values (`active`, `completed`, etc.) | Internal state machine constants |
| `asterisk/voice_agent.agi` | `POLL_INTERVAL = 0.3`, `POLL_TIMEOUT = 60` | Technical polling tuning, not deployment-specific |
| `asterisk/voice_agent.agi` | `MIN_RECORDING_BYTES = 1024` | Technical threshold, not installation-specific |
| `asterisk/voice_agent.agi` | Sound paths `custom/please_ask_ar` etc. | Relative to Asterisk sound path, consistent across installs |
| `tasks/process_turn.py` | Closing response template text | Fallback text — customisable per-language via SiteConfig |

### Prompts — classification

| Prompt | Location | Classification | Reason |
|---|---|---|---|
| Language menu (`custom/language_menu`) | Asterisk sounds dir | Technician-managed audio file | Must be provided as a WAV/ulaw/alaw file |
| Please wait prompts (`custom/please_wait_ar/en`) | Asterisk sounds dir | Technician-managed audio file | Must be provided as a WAV/ulaw/alaw file |
| Please ask prompts (`custom/please_ask_ar/en`) | Asterisk sounds dir | Technician-managed audio file | Must be provided as a WAV/ulaw/alaw file |
| Goodbye / sorry / nobody available | Asterisk built-in (`vm-goodbye` etc.) | Asterisk built-in | Standard Asterisk sounds |
| AI conversation response text | Generated at runtime by LLM | Runtime-generated | Cannot be pre-configured |
| Closing response template | `tasks/process_turn.py` | Code constant | Language-keyed fallback — consider moving to SiteConfig if localization needed |

---

## 10. Restart Reference

After changing values in `.env`:

```bash
# Reload environment and restart all application services
sudo systemctl restart voice_ai_gunicorn
sudo systemctl restart voice_ai_celery_worker
sudo systemctl restart voice_ai_celery_beat
sudo systemctl restart voice_ai_watchdog

# Verify all services are healthy
sudo systemctl status voice_ai_gunicorn voice_ai_celery_worker voice_ai_celery_beat

# Tail logs to confirm startup
sudo journalctl -u voice_ai_gunicorn -f
sudo journalctl -u voice_ai_celery_worker -f
```

After changing Asterisk files:

```bash
# Reload PJSIP (SIP endpoints, credentials)
asterisk -rx "pjsip reload"

# Reload dialplan only (no calls dropped)
asterisk -rx "dialplan reload"

# Full Asterisk restart (only if necessary)
sudo systemctl restart asterisk
```

After changing Nginx config:

```bash
sudo nginx -t          # validate config first
sudo systemctl reload nginx
```

After changing systemd service files:

```bash
sudo systemctl daemon-reload
sudo systemctl restart <service-name>
```

---

## 11. Security Checklist

Before going live, verify:

- [ ] `DJANGO_SECRET_KEY` is a unique, random 50+ character string
- [ ] `DJANGO_DEBUG=False` in `.env`
- [ ] `DJANGO_ALLOWED_HOSTS` contains only your server's hostname/IP (not `*`)
- [ ] `APP_BASE_URL` is set and has no trailing slash
- [ ] `ASTERISK_SECRET` is set to a random 32+ character hex string (same in `.env` and `/etc/asterisk/asterisk.env`)
- [ ] `DB_PASSWORD` is a strong, unique password
- [ ] `EMAIL_HOST_PASSWORD` is a Gmail App Password (not your account password)
- [ ] `asterisk/pjsip.conf` HT813 password has been changed from `W0rk@786` to a new random password
- [ ] `asterisk/pjsip.conf` agent200 password has been changed from `CHANGE_ME_AGENT200_PASSWORD`
- [ ] HT813 ATA web interface password matches the new `[ht813]` auth password in `pjsip.conf`
- [ ] Gunicorn binds to `127.0.0.1:8000` (loopback only) — confirmed in the service file
- [ ] Nginx is the only service listening on port 80/443 (`sudo ss -tlnp | grep ':80'`)
- [ ] No `.env` file is committed to git (check: `git status .env`)
- [ ] Log directory is writable by the service user: `ls -la /var/log/voice_ai_agent/`
- [ ] All systemd services are enabled and active: `systemctl is-active voice_ai_gunicorn voice_ai_celery_worker voice_ai_celery_beat`
