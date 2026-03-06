# Deploying Tesserae V6 on Olivia

## Overview

Tesserae V6 uses Apache to serve two things separately:
- **Static frontend** (HTML/JS/CSS): Apache serves the built React app from a directory (on Marvin, `/var/www/tess-new`, which is a symlink to `/var/www/tesseraev6_flask/dist`)
- **API backend** (`/api/*` requests): Apache forwards these to Flask via mod_wsgi

The built frontend (`dist/`) is committed to the GitHub repo, so `git pull` delivers both backend code and frontend assets — no need to run `npm` or `vite` on the server.

## Initial Setup (one-time, for sysadmin)

These steps mirror the Marvin setup. Your sysadmin should handle the Apache/PostgreSQL/permissions pieces.

### 1. Clone the repo

```bash
sudo mkdir -p /var/www/tesseraev6_flask
sudo chown YOUR_USER:YOUR_GROUP /var/www/tesseraev6_flask
git clone https://github.com/tesserae/tesserae-v6.git /var/www/tesseraev6_flask
```

### 2. Create the Python virtual environment

```bash
cd /var/www/tesseraev6_flask
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Create the `.env` file

```bash
cat > /var/www/tesseraev6_flask/.env << 'EOF'
DATABASE_URL=postgresql://tesseraev6:YOUR_PASSWORD@localhost:5432/tesseraev6
SESSION_SECRET=YOUR_SECRET_KEY
ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD
PYTHONIOENCODING=utf-8
LANG=en_US.UTF-8
LC_ALL=en_US.UTF-8
DEPLOYMENT_ENV=olivia
EOF
```

### 4. Set up PostgreSQL

```bash
sudo -u postgres psql
CREATE DATABASE tesseraev6;
CREATE USER tesseraev6 WITH PASSWORD 'YOUR_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE tesseraev6 TO tesseraev6;
\q
```

### 5. Create the WSGI file

This file is not in the repo. Create `/var/www/tesseraev6_flask/tesseraev6_flask.wsgi`:

```python
import sys
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['LANG'] = 'en_US.UTF-8'
os.environ['LC_ALL'] = 'en_US.UTF-8'

sys.path.insert(0, '/var/www/tesseraev6_flask')
os.chdir('/var/www/tesseraev6_flask')

from dotenv import load_dotenv
load_dotenv('/var/www/tesseraev6_flask/.env')

from backend.app import app as application
```

### 6. Create the frontend symlink

```bash
sudo ln -s /var/www/tesseraev6_flask/dist /var/www/tess-new
```

This makes Apache serve the built frontend directly from the repo's `dist/` directory. When you `git pull`, the frontend updates automatically.

### 7. Apache configuration

Your sysadmin should create an Apache virtual host config (e.g., `/etc/apache2/sites-available/vhost-tess-new.conf`). The critical pieces in the HTTPS `<VirtualHost>` block are:

```apache
DocumentRoot /var/www/tess-new

# SPA routing — sends all non-file, non-API requests to index.html
<Directory /var/www/tess-new>
    Require all granted
    DirectoryIndex index.html
    RewriteEngine On
    RewriteCond %{REQUEST_URI} !^/api/
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule . /index.html [L]
</Directory>

# WSGI — forwards /api/* to Flask
WSGIDaemonProcess tesserae python-home=/var/www/tesseraev6_flask/venv python-path=/var/www/tesseraev6_flask user=tess-flask group=tessdev threads=5 socket-timeout=900 response-socket-timeout=900
WSGIScriptAlias /api /var/www/tesseraev6_flask/tesseraev6_flask.wsgi
<Directory /var/www/tesseraev6_flask>
    WSGIProcessGroup tesserae
    WSGIApplicationGroup %{GLOBAL}
    Require all granted
</Directory>
```

The `socket-timeout=900` and `response-socket-timeout=900` are important — fusion searches on large text pairs can take several minutes.

Enable and restart:
```bash
sudo a2enmod wsgi ssl rewrite
sudo a2ensite vhost-tess-new
sudo systemctl restart apache2
```

### 8. Copy data files

These large files are not in the git repo and must be copied from Marvin (or downloaded):

| Directory | Size | Contents |
|-----------|------|----------|
| `data/inverted_index/` | ~6 GB | `la_index.db`, `grc_index.db`, `en_index.db`, `syntax_latin.db` |
| `data/lemma_tables/` | ~5 MB | `latin_lemmas.json`, `greek_lemmas.json` |
| `backend/embeddings/` | ~2 GB | Pre-computed SPhilBERTa embeddings |
| `texts/` | ~308 MB | Corpus `.tess` files (la/, grc/, en/) |
| `cache/lemmas/` | varies | Per-file lemmatization caches |
| `cache/bigrams/` | ~565 MB | Bigram frequency indexes |

```bash
# From Marvin, rsync the data to Olivia:
rsync -avz /var/www/tesseraev6_flask/data/ olivia:/var/www/tesseraev6_flask/data/
rsync -avz /var/www/tesseraev6_flask/backend/embeddings/ olivia:/var/www/tesseraev6_flask/backend/embeddings/
rsync -avz /var/www/tesseraev6_flask/texts/ olivia:/var/www/tesseraev6_flask/texts/
rsync -avz /var/www/tesseraev6_flask/cache/ olivia:/var/www/tesseraev6_flask/cache/
```

### 9. Log directory

```bash
sudo mkdir -p /var/log/tesserae
sudo chown www-data:www-data /var/log/tesserae
```

(Or match whatever user/group your Apache uses for error logs.)

---

## Pulling Changes and Restarting (routine deployment)

This is what you'll do regularly when new code is pushed to GitHub.

```bash
# 1. Pull the latest code
cd /var/www/tesseraev6_flask
git pull origin main

# 2. If requirements.txt changed, update Python packages
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 3. Restart Apache to reload the Flask backend
sudo systemctl restart apache2
```

That's it. Because `dist/` is committed to the repo and `/var/www/tess-new` is a symlink to `dist/`, the `git pull` delivers both frontend and backend changes in one step. The Apache restart reloads the WSGI process so Flask picks up the new Python code.

**If only frontend changed** (files in `client/src/`, `dist/`): You still need the Apache restart, because Apache caches the served files.

**If only backend changed** (files in `backend/`): The Apache restart is required to reload the WSGI daemon process.

## Verifying the Deployment

After restarting, check:

```bash
# Apache is running
sudo systemctl status apache2

# No errors in the log
sudo tail -20 /var/log/tesserae/tesseraev6_ssl_error.log

# The site responds
curl -s https://YOUR_OLIVIA_HOSTNAME/ | head -5
curl -s https://YOUR_OLIVIA_HOSTNAME/api/corpus/texts?language=la | head -1
```
