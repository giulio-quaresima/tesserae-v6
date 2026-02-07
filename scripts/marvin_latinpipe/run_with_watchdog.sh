#!/bin/bash
# Watchdog wrapper for build_latinpipe_syntax.py
# Monitors progress and auto-restarts if stalled for 3 minutes
#
# Usage: nohup bash run_with_watchdog.sh > watchdog_log.txt 2>&1 &

CORPUS_DIR="/var/www/tesseraev6_flask/texts/la/"
MODEL_PATH="$HOME/latinpipe_indexing/evalatin2024-latinpipe/latinpipe-evalatin24-240520/model.weights.h5"
REPO_PATH="$HOME/latinpipe_indexing/evalatin2024-latinpipe/"
WORK_DIR="$HOME/latinpipe_indexing"
DB_FILE="$WORK_DIR/syntax_latin.db"
STALL_TIMEOUT=180  # 3 minutes without progress = restart

cd "$WORK_DIR"
source "$WORK_DIR/latinpipe_env/bin/activate"

get_text_count() {
    python3 -c "
import sqlite3
c = sqlite3.connect('$DB_FILE')
print(c.execute('SELECT COUNT(*) FROM texts').fetchone()[0])
c.close()
" 2>/dev/null || echo "0"
}

kill_all() {
    pkill -f build_latinpipe_syntax.py 2>/dev/null
    pkill -f latinpipe_evalatin24_server 2>/dev/null
    sleep 5
    pkill -9 -f latinpipe_evalatin24_server 2>/dev/null
    sleep 2
}

echo "=== WATCHDOG STARTED at $(date) ==="
echo "Stall timeout: ${STALL_TIMEOUT}s"

while true; do
    CURRENT_COUNT=$(get_text_count)
    echo ""
    echo "[$(date)] Starting build script. Texts so far: $CURRENT_COUNT / 1429"

    kill_all

    python -u build_latinpipe_syntax.py \
        --corpus-dir "$CORPUS_DIR" \
        --local \
        --model-path "$MODEL_PATH" \
        --repo-path "$REPO_PATH" \
        > build_log.txt 2>&1 &
    BUILD_PID=$!

    echo "[$(date)] Build script started (PID: $BUILD_PID)"

    LAST_COUNT=$CURRENT_COUNT
    LAST_PROGRESS_TIME=$(date +%s)

    while kill -0 $BUILD_PID 2>/dev/null; do
        sleep 30

        NEW_COUNT=$(get_text_count)
        NOW=$(date +%s)

        if [ "$NEW_COUNT" != "$LAST_COUNT" ]; then
            LAST_COUNT=$NEW_COUNT
            LAST_PROGRESS_TIME=$NOW
            echo "[$(date)] Progress: $NEW_COUNT texts done"
        fi

        STALL_DURATION=$((NOW - LAST_PROGRESS_TIME))

        if [ $STALL_DURATION -ge $STALL_TIMEOUT ]; then
            echo "[$(date)] STALLED for ${STALL_DURATION}s! Killing and restarting..."
            kill_all
            sleep 3
            break
        fi

        if [ "$NEW_COUNT" -ge 1429 ]; then
            echo "[$(date)] ALL 1429 TEXTS COMPLETE!"
            echo "=== WATCHDOG FINISHED at $(date) ==="
            exit 0
        fi
    done

    FINAL_COUNT=$(get_text_count)
    if [ "$FINAL_COUNT" -ge 1429 ]; then
        echo "[$(date)] ALL 1429 TEXTS COMPLETE!"
        echo "=== WATCHDOG FINISHED at $(date) ==="
        exit 0
    fi

    echo "[$(date)] Restarting in 10 seconds... ($FINAL_COUNT texts done so far)"
    sleep 10
done
