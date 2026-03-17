"""
Seed script to populate OAuth2 token tables with ~60M records for load testing.

Run inside the LMS container:
    cd /openedx/edx-platform && python /openedx/src/open-edx-plugins/src/ol_social_auth/seed_tokens.py

Uses MySQL exponential doubling (INSERT...SELECT) for speed.
Seeds a small batch via Python, then doubles rows in MySQL until target is reached.
"""

import os
import sys
import time
import uuid

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lms.envs.devstack")
os.environ.setdefault("SERVICE_VARIANT", "lms")
os.environ.setdefault("LMS_CFG", "/openedx/config/lms.env.yml")

sys.path.insert(0, "/openedx/edx-platform")
django.setup()

from django.db import connection  # noqa: E402
from django.utils import timezone  # noqa: E402
from oauth2_provider.models import Application  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()

TARGET = 6_000_000
SEED_BATCH = 100_000  # initial Python-generated rows


def count_tokens(cursor):
    cursor.execute("SELECT COUNT(*) FROM oauth2_provider_accesstoken")
    return cursor.fetchone()[0]


def seed():
    user_ids = list(User.objects.values_list("id", flat=True))
    app_ids = list(Application.objects.values_list("id", flat=True))

    if not user_ids or not app_ids:
        print("ERROR: Need at least 1 user and 1 application in the DB.")
        sys.exit(1)

    now = timezone.now()

    with connection.cursor() as cursor:
        # Clean existing tokens to start fresh
        print("Clearing existing tokens...")
        cursor.execute("UPDATE oauth2_provider_accesstoken SET source_refresh_token_id = NULL WHERE source_refresh_token_id IS NOT NULL")
        cursor.execute("DELETE FROM oauth2_provider_refreshtoken")
        cursor.execute("DELETE FROM oauth2_provider_accesstoken")
        cursor.execute("DELETE FROM oauth2_provider_grant")
        print("Cleared.")

        current = 0
        print(f"Target: {TARGET:,}")

        # Step 1: Seed initial batch via Python (all expired)
        needed = SEED_BATCH
        print(f"\nStep 1: Seeding {needed:,} initial expired access tokens via Python...")
        start = time.time()

        rows = []
        for i in range(needed):
            user_id = user_ids[i % len(user_ids)]
            app_id = app_ids[i % len(app_ids)]
            token = uuid.uuid4().hex
            # All expired: 6 to 186 days ago
            days = (i % 180) + 6
            expires = (now - __import__('datetime').timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            created = now.strftime("%Y-%m-%d %H:%M:%S")
            rows.append(f"({user_id},'{token}',{app_id},'{expires}','read write','{created}','{created}')")

            if len(rows) >= 10000:
                sql = ("INSERT INTO oauth2_provider_accesstoken "
                       "(user_id,token,application_id,expires,scope,created,updated) VALUES " + ",".join(rows))
                cursor.execute(sql)
                rows = []

        if rows:
            sql = ("INSERT INTO oauth2_provider_accesstoken "
                   "(user_id,token,application_id,expires,scope,created,updated) VALUES " + ",".join(rows))
            cursor.execute(sql)

        elapsed = time.time() - start
        current = count_tokens(cursor)
        print(f"  Done: {current:,} access tokens in {elapsed:.1f}s")

        # Step 2: Exponential doubling via INSERT...SELECT
        print(f"\nStep 2: Doubling rows via INSERT...SELECT until {TARGET:,}...")
        iteration = 0
        start = time.time()

        while current < TARGET:
            needed = TARGET - current
            # Limit each doubling batch to avoid overwhelming MySQL
            limit = min(current, needed, 5_000_000)
            iteration += 1

            print(f"  Iteration {iteration}: inserting {limit:,} rows (current: {current:,})...", flush=True)

            # INSERT...SELECT with UUID() for unique tokens — keep all expired
            sql = f"""
                INSERT INTO oauth2_provider_accesstoken
                    (user_id, token, application_id, expires, scope, created, updated)
                SELECT
                    user_id,
                    REPLACE(UUID(), '-', ''),
                    application_id,
                    DATE_SUB(expires, INTERVAL FLOOR(RAND() * 30) DAY),
                    scope,
                    NOW(),
                    NOW()
                FROM oauth2_provider_accesstoken
                ORDER BY RAND()
                LIMIT {limit}
            """
            cursor.execute(sql)

            current = count_tokens(cursor)
            elapsed = time.time() - start
            rate = current / elapsed if elapsed > 0 else 0
            print(f"           -> {current:,} total | {rate:,.0f} rows/s | elapsed: {elapsed/60:.1f} min", flush=True)

        # Step 3: Create matching refresh tokens for access tokens that don't have one
        print(f"\nStep 3: Creating refresh tokens for access tokens without one...")
        start3 = time.time()

        cursor.execute("""
            SELECT COUNT(*) FROM oauth2_provider_accesstoken a
            LEFT JOIN oauth2_provider_refreshtoken r ON r.access_token_id = a.id
            WHERE r.id IS NULL
        """)
        missing = cursor.fetchone()[0]
        print(f"  {missing:,} access tokens need refresh tokens")

        batch_num = 0
        while True:
            batch_num += 1
            sql = """
                INSERT INTO oauth2_provider_refreshtoken
                    (user_id, token, application_id, access_token_id, created, updated, revoked)
                SELECT
                    a.user_id,
                    REPLACE(UUID(), '-', ''),
                    a.application_id,
                    a.id,
                    NOW(),
                    NOW(),
                    NULL
                FROM oauth2_provider_accesstoken a
                LEFT JOIN oauth2_provider_refreshtoken r ON r.access_token_id = a.id
                WHERE r.id IS NULL
                LIMIT 1000000
            """
            cursor.execute(sql)
            affected = cursor.rowcount
            if affected == 0:
                break
            elapsed3 = time.time() - start3
            print(f"  Batch {batch_num}: inserted {affected:,} refresh tokens | elapsed: {elapsed3/60:.1f} min", flush=True)

        total_elapsed = time.time() - start
        cursor.execute("SELECT COUNT(*) FROM oauth2_provider_refreshtoken")
        refresh_count = cursor.fetchone()[0]
        print(f"\nDone! Access tokens: {current:,}, Refresh tokens: {refresh_count:,}")
        print(f"Total time: {total_elapsed/60:.1f} minutes")


if __name__ == "__main__":
    seed()
