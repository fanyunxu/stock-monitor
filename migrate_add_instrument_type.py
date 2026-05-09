#!/usr/bin/env python3
"""Add instrument_type column to etf_watch table"""

import psycopg2
import yaml

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

db_config = config['database']

# Connect to database
conn = psycopg2.connect(
    host=db_config['host'],
    port=db_config['port'],
    database=db_config['name'],
    user=db_config['user'],
    password=db_config['password']
)

try:
    cursor = conn.cursor()

    # Add instrument_type column if not exists
    cursor.execute("""
        ALTER TABLE etf_watch
        ADD COLUMN IF NOT EXISTS instrument_type VARCHAR(10) DEFAULT 'ETF';
    """)

    conn.commit()
    print("✓ Added instrument_type column to etf_watch table")

    # Verify
    cursor.execute("""
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'etf_watch' AND column_name = 'instrument_type';
    """)
    result = cursor.fetchone()
    if result:
        print(f"✓ Verified: {result[0]} ({result[1]}) default={result[2]}")
    else:
        print("✗ Column not found after migration")

    cursor.close()
except Exception as e:
    conn.rollback()
    print(f"✗ Migration failed: {e}")
finally:
    conn.close()
