#!/bin/bash
# Force SQLite to WAL mode for all application databases

DATABASES=(
    "instance/telegram_system.db"
    "mrktguru.db"
    "telegram_system.db"
)

for DB_PATH in "${DATABASES[@]}"; do
    if [ -f "$DB_PATH" ]; then
        echo "Converting $DB_PATH to WAL mode..."
        sqlite3 "$DB_PATH" "PRAGMA journal_mode=WAL;"
        sqlite3 "$DB_PATH" "PRAGMA synchronous=NORMAL;"
        echo "Current mode:"
        sqlite3 "$DB_PATH" "PRAGMA journal_mode;"
        echo "---"
    else
        echo "Database not found: $DB_PATH (skipping)"
    fi
done

echo "✅ All databases converted to WAL mode"
