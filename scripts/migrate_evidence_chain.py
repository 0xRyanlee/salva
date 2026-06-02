#!/usr/bin/env python3
"""
Migration script to fix evidence_chain_records table schema.

This script:
1. Adds a UNIQUE constraint on (run_id, entity_id)
2. Cleans up any existing duplicate records
3. Ensures future inserts won't fail due to duplicates
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "salva_runtime.db"


def migrate(db_path: str = None) -> None:
    path = db_path or DEFAULT_DB_PATH
    
    if not Path(path).exists():
        print(f"Database not found at {path}, skipping migration")
        return
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    try:
        # Check current schema
        cursor.execute("PRAGMA table_info(evidence_chain_records)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if "run_id" not in columns or "entity_id" not in columns:
            print("Table schema doesn't match expected format, skipping")
            return
        
        # Check if we have duplicates
        cursor.execute("""
            SELECT run_id, entity_id, COUNT(*) as cnt
            FROM evidence_chain_records
            GROUP BY run_id, entity_id
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"Found {len(duplicates)} duplicate (run_id, entity_id) pairs")
            # Keep only the first record for each (run_id, entity_id)
            for run_id, entity_id, cnt in duplicates:
                # Get the first chain_id to keep
                cursor.execute("""
                    SELECT chain_id FROM evidence_chain_records
                    WHERE run_id = ? AND entity_id = ?
                    LIMIT 1
                """, (run_id, entity_id))
                first_chain_id = cursor.fetchone()[0]
                
                # Delete duplicates except the first
                cursor.execute("""
                    DELETE FROM evidence_chain_records
                    WHERE run_id = ? AND entity_id = ? AND chain_id != ?
                """, (run_id, entity_id, first_chain_id))
            
            print("Duplicates cleaned up")
        
        # Add unique index on (run_id, entity_id) if it doesn't exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_evidence_chain_unique'
        """)
        
        if not cursor.fetchone():
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_chain_unique 
                ON evidence_chain_records(run_id, entity_id)
            """)
            print("Created unique index on (run_id, entity_id)")
        
        conn.commit()
        print("Migration completed successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    migrate(db_path)