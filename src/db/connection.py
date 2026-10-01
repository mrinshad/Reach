"""
PostgreSQL Connection & Database Initialization Module.
"""

import os
import psycopg2

def _load_env_file():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_file = os.path.join(root_dir, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

_current_user = os.getenv("USER", "postgres")
DEFAULT_DB_URL = os.getenv("DATABASE_URL", f"postgresql://{_current_user}@localhost:5432/linkedin_scrapper")


def get_connection(db_url: str = DEFAULT_DB_URL):
    """Return a psycopg2 connection to PostgreSQL."""
    return psycopg2.connect(db_url)


# Alias for backward compatibility
get_db_connection = get_connection


def init_db(db_url: str = DEFAULT_DB_URL):
    """Create the posts and settings tables if they do not exist, matching schema.prisma."""
    from src.db.settings import seed_default_settings

    create_sql = """
    CREATE TABLE IF NOT EXISTS posts (
        id VARCHAR(64) PRIMARY KEY,
        post_url VARCHAR(512) UNIQUE,
        author_name VARCHAR(256) NOT NULL,
        author_headline TEXT,
        author_profile VARCHAR(512),
        posted_date_raw VARCHAR(64),
        full_text TEXT NOT NULL,
        contact_emails TEXT[] DEFAULT '{}',
        external_links TEXT[] DEFAULT '{}',
        min_experience REAL,
        max_experience REAL,
        raw_experience TEXT,
        seniority_level VARCHAR(64),
        is_fresher BOOLEAN DEFAULT FALSE,
        category VARCHAR(64) DEFAULT 'EMAIL_OUTREACH',
        status VARCHAR(64) DEFAULT 'DISCOVERED',
        generated_subject TEXT,
        generated_body TEXT,
        approved_at TIMESTAMP,
        sent_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category);
    CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
    CREATE INDEX IF NOT EXISTS idx_posts_exp ON posts(min_experience, max_experience);
    CREATE INDEX IF NOT EXISTS idx_posts_status_created ON posts(status, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC);

    CREATE TABLE IF NOT EXISTS settings (
        key VARCHAR(128) PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS activity_logs (
        id VARCHAR(64) PRIMARY KEY,
        task_type VARCHAR(64) NOT NULL,
        task_name VARCHAR(256) NOT NULL,
        short_name VARCHAR(128),
        parameters JSONB DEFAULT '{}',
        status VARCHAR(32) NOT NULL DEFAULT 'running',
        result_summary TEXT,
        crawl_stats JSONB DEFAULT '{}',
        logs TEXT[] DEFAULT '{}',
        total_items INT DEFAULT 0,
        completed_items INT DEFAULT 0,
        started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP WITH TIME ZONE,
        duration_seconds REAL DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at ON activity_logs(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_activity_logs_type ON activity_logs(task_type);
    CREATE INDEX IF NOT EXISTS idx_activity_logs_status ON activity_logs(status);
    """
    alter_sql = """
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_potential_spam BOOLEAN DEFAULT FALSE;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS potential_spam_reason TEXT;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS location VARCHAR(128);
    ALTER TABLE posts ALTER COLUMN post_url TYPE TEXT;
    CREATE INDEX IF NOT EXISTS idx_posts_location ON posts(location);
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            cur.execute(alter_sql)
        conn.commit()

    seed_default_settings(db_url)
    print("✓ PostgreSQL database initialized (tables: posts, settings, activity_logs).")
