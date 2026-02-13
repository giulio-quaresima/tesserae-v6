#!/bin/bash
# Run from tesserae-v6 root. Pulls, builds, commits dist, pushes.
set -e
git pull origin neil-dev
cd client && npm run build && cd ..
git add dist/
git status --short dist/ | grep -q . && git commit -m "Build frontend" && git push origin neil-dev || echo "No dist changes"
