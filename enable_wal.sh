#!/bin/bash
# Force SQLite to WAL mode for the application database

DB_PATH="instance/mrktguru.db"

if [ -f "$DB_PATH" ]; then
    echo "Converting $DB_PATH to WAL mode..."
    sqlite3 "$DB_PATH" "PRAGMA journal_mode=WAL;"
    sqlite3 "$DB_PATH" "PRAGMA synchronous=NORMAL;"
    echo "WAL mode enabled. Current mode:"
    sqlite3 "$DB_PATH" "PRAGMA journal_mode;"
else
    echo "Database not found at $DB_PATH"
    exit 1
fi
