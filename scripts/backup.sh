#!/usr/bin/env bash
# ─────────────────────────────────────────────
# Nivesa — Database Backup Script
# Hemrek Capital
# ─────────────────────────────────────────────
# Usage:
#   ./scripts/backup.sh
#   ./scripts/backup.sh /custom/backup/dir
#
# Crontab (daily at 2 AM):
#   0 2 * * * /path/to/nivesa/scripts/backup.sh
# ─────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

DB_FILE="${PROJECT_DIR}/data/db/portfolio.db"
BACKUP_DIR="${1:-${PROJECT_DIR}/data/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/portfolio_${TIMESTAMP}.db"

# Retention: keep last N backups
KEEP_LAST=30

# ── Validate ──
if [ ! -f "$DB_FILE" ]; then
    echo "[ERROR] Database not found: $DB_FILE"
    exit 1
fi

# ── Create backup directory ──
mkdir -p "$BACKUP_DIR"

# ── Backup using SQLite online backup API ──
sqlite3 "$DB_FILE" ".backup '${BACKUP_FILE}'"

if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[OK] Backup created: ${BACKUP_FILE} (${SIZE})"
else
    echo "[ERROR] Backup failed"
    exit 1
fi

# ── Cleanup old backups ──
BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/portfolio_*.db 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$KEEP_LAST" ]; then
    REMOVE_COUNT=$((BACKUP_COUNT - KEEP_LAST))
    ls -1t "${BACKUP_DIR}"/portfolio_*.db | tail -n "$REMOVE_COUNT" | xargs rm -f
    echo "[OK] Cleaned up ${REMOVE_COUNT} old backup(s). Keeping last ${KEEP_LAST}."
fi

echo "[OK] Backup complete."
