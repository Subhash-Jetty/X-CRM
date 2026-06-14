import psycopg2
import sys

conn_str = "postgresql://postgres.euntouwflhlzgegmmxgj:YxcL7pYFbGqbceA4@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

try:
    with psycopg2.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT error_message FROM communications WHERE status = 'failed' ORDER BY created_at DESC LIMIT 1;")
            row = cur.fetchone()
            if row:
                print(f"EXACT ERROR: {row[0]}")
            else:
                print("No failed communications found.")
except Exception as e:
    print(f"Failed to query DB: {e}")
