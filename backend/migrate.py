import sqlite3
import os

db_paths = [
    "facebook_automation.db",
    "backend/facebook_automation.db"
]

for db_path in db_paths:
    if not os.path.exists(db_path):
        continue
    print(f"Migrating {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Update facebook_pages
    cur.execute("PRAGMA table_info(facebook_pages)")
    cols = [row[1] for row in cur.fetchall()]
    
    additions_page = [
        ("daily_posts_target", "INTEGER DEFAULT 1"),
        ("post_auto_publish", "BOOLEAN DEFAULT 0"),
        ("posting_schedule_times", "VARCHAR(255) DEFAULT '10:00,18:00'"),
        ("post_topics_prompt", "TEXT DEFAULT 'Product highlights, discounts, and tips'"),
        ("posts_created_today", "INTEGER DEFAULT 0")
    ]
    for col, col_def in additions_page:
        if col not in cols:
            print(f"Adding column {col} to facebook_pages")
            cur.execute(f"ALTER TABLE facebook_pages ADD COLUMN {col} {col_def}")
            
    # 2. Update posts
    cur.execute("PRAGMA table_info(posts)")
    cols_post = [row[1] for row in cur.fetchall()]
    
    additions_post = [
        ("is_ai_generated", "BOOLEAN DEFAULT 0"),
        ("status", "VARCHAR(50) DEFAULT 'published'"),
        ("scheduled_for", "DATETIME")
    ]
    for col, col_def in additions_post:
        if col not in cols_post:
            print(f"Adding column {col} to posts")
            cur.execute(f"ALTER TABLE posts ADD COLUMN {col} {col_def}")
            
    conn.commit()
    conn.close()
    print(f"Successfully migrated {db_path}!")

if __name__ == "__main__":
    print("Migration script executed.")
