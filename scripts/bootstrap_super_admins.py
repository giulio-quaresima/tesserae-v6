#!/usr/bin/env python3
"""
Bootstrap SUPER_ADMIN accounts and RBAC tables.

Usage:
  DATABASE_URL=postgresql://... python scripts/bootstrap_super_admins.py
"""
import os
import sys
import uuid
from datetime import datetime, timezone

try:
    import psycopg
except ImportError as e:
    raise SystemExit(f"psycopg is required to run this script: {e}")

try:
    from werkzeug.security import generate_password_hash
except ImportError as e:
    raise SystemExit(f"werkzeug is required to hash passwords: {e}")


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def ensure_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(255) PRIMARY KEY,
            email VARCHAR(255) UNIQUE,
            password_hash VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            profile_image_url TEXT,
            institution TEXT,
            orcid VARCHAR(19),
            orcid_name VARCHAR(255),
            must_reset_password BOOLEAN DEFAULT FALSE,
            share_to_public_default BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    cur.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)
    """)
    cur.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(255)
    """)
    cur.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(255)
    """)
    cur.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS must_reset_password BOOLEAN DEFAULT FALSE
    """)
    cur.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP
    """)
    cur.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            description TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id VARCHAR(255) NOT NULL,
            role_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_by VARCHAR(255),
            PRIMARY KEY (user_id, role_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            action VARCHAR(255) NOT NULL,
            performed_by VARCHAR(255),
            target_user_id VARCHAR(255),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(255)
        )
    """)


def ensure_roles(cur):
    roles = [
        ("USER", "Standard user"),
        ("ADMIN", "Administrator"),
        ("SUPER_ADMIN", "Super administrator"),
    ]
    for name, desc in roles:
        cur.execute(
            """
            INSERT INTO roles (name, description)
            VALUES (%s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            (name, desc),
        )


def get_role_id(cur, name):
    cur.execute("SELECT id FROM roles WHERE name = %s", (name,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Role not found: {name}")
    return row[0]


def count_super_admins(cur, role_id):
    cur.execute("SELECT COUNT(*) FROM user_roles WHERE role_id = %s", (role_id,))
    return cur.fetchone()[0]


def upsert_user(cur, email, password, first_name=None, last_name=None):
    cur.execute("SELECT id FROM users WHERE email = %s", (email.lower(),))
    row = cur.fetchone()
    password_hash = generate_password_hash(password)
    now = datetime.now(timezone.utc)

    if row:
        user_id = row[0]
        cur.execute(
            """
            UPDATE users
            SET password_hash = %s,
                first_name = COALESCE(%s, first_name),
                last_name = COALESCE(%s, last_name),
                updated_at = %s
            WHERE id = %s
            """,
            (password_hash, first_name, last_name, now, user_id),
        )
        return user_id, False

    user_id = uuid.uuid4().hex
    cur.execute(
        """
        INSERT INTO users (id, email, password_hash, first_name, last_name, must_reset_password, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, email.lower(), password_hash, first_name, last_name, True, now, now),
    )
    return user_id, True


def assign_role(cur, user_id, role_id, assigned_by="SYSTEM_BOOTSTRAP"):
    now = datetime.now(timezone.utc)
    cur.execute(
        """
        INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """,
        (user_id, role_id, now, assigned_by),
    )


def log_audit(cur, action, performed_by, target_user_id):
    now = datetime.now(timezone.utc)
    cur.execute(
        """
        INSERT INTO audit_logs (action, performed_by, target_user_id, timestamp)
        VALUES (%s, %s, %s, %s)
        """,
        (action, performed_by, target_user_id, now),
    )


def main():
    database_url = require_env("DATABASE_URL")

    admin1_email = require_env("BOOTSTRAP_SUPER_ADMIN_1_EMAIL")
    admin1_password = require_env("BOOTSTRAP_SUPER_ADMIN_1_PASSWORD")
    admin1_name = os.environ.get("BOOTSTRAP_SUPER_ADMIN_1_NAME", "")

    admin2_email = require_env("BOOTSTRAP_SUPER_ADMIN_2_EMAIL")
    admin2_password = require_env("BOOTSTRAP_SUPER_ADMIN_2_PASSWORD")
    admin2_name = os.environ.get("BOOTSTRAP_SUPER_ADMIN_2_NAME", "")

    admin1_first, _, admin1_last = admin1_name.partition(" ")
    admin2_first, _, admin2_last = admin2_name.partition(" ")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            ensure_tables(cur)
            ensure_roles(cur)

            super_admin_role_id = get_role_id(cur, "SUPER_ADMIN")
            if count_super_admins(cur, super_admin_role_id) > 0:
                print("SUPER_ADMIN already exists; bootstrap skipped.")
                return

            user1_id, _ = upsert_user(cur, admin1_email, admin1_password, admin1_first or None, admin1_last or None)
            user2_id, _ = upsert_user(cur, admin2_email, admin2_password, admin2_first or None, admin2_last or None)

            assign_role(cur, user1_id, super_admin_role_id)
            assign_role(cur, user2_id, super_admin_role_id)

            log_audit(cur, "SYSTEM_BOOTSTRAP_SUPER_ADMINS_CREATED", "SYSTEM", user1_id)
            log_audit(cur, "SYSTEM_BOOTSTRAP_SUPER_ADMINS_CREATED", "SYSTEM", user2_id)

            conn.commit()

    print("Bootstrap completed: created two SUPER_ADMIN accounts.")


if __name__ == "__main__":
    main()
