"""
Substack crawler main execution flow.

Steps:
1. Connect to the database (config from .env).
2. Initialize schema (create tables if needed).
3. Query crawl targets filtered by source_type='substack'.
4. For each enabled target, run a crawl cycle:
   a. notify_crawl_start
   b. Fetch items from Substack (real crawl)
   c. Save items to database
   d. notify_crawl_end
5. Print final target state.
"""

import os
import re
import time
import json
import argparse
import hashlib
from datetime import datetime
from urllib.parse import urlparse

import requests
import psycopg2
from dotenv import load_dotenv
from financial_hub_postgres import FinancialHubClient

from scraper import get_user_id, get_user_posts, fetch_post_full_content, html_to_text, _session


# Load environment variables
load_dotenv()

COMPONENT_NAME = "substack_crawler"


def get_db_connection():
    """Create a database connection using .env config."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "hub_user"),
        password=os.getenv("POSTGRES_PASSWORD", "hub_password"),
        dbname=os.getenv("POSTGRES_DB", "financial_hub"),
    )


def init_schema(conn):
    """Execute schema.sql to ensure tables exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Schema initialized.")


def ensure_author(conn, username: str, user_id: str):
    """Insert or update substack_authors record."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO substack_authors (username, user_id, profile_url)
            VALUES (%s, %s, %s)
            ON CONFLICT (username) DO UPDATE
            SET user_id = EXCLUDED.user_id, updated_at = NOW()
            """,
            (username, user_id, f"https://substack.com/@{username}"),
        )
    conn.commit()


def download_attachments(attachments: list, file_path: str, username: str) -> list:
    """
    Download attachment files to file_path directory.
    Returns updated attachments list with local_path added.
    """
    if not attachments or not file_path:
        return attachments

    # Create download directory: file_path/username/attachments/
    download_dir = os.path.join(file_path, username, "attachments")
    os.makedirs(download_dir, exist_ok=True)

    updated = []
    for att in attachments:
        att_copy = dict(att)
        att_type = att.get("type", "unknown")

        # Get the URL to download
        url = None
        if att_type == "image":
            url = att.get("imageUrl", "")
        elif "url" in att:
            url = att["url"]

        if url:
            try:
                # Generate filename from URL hash + extension
                parsed = urlparse(url)
                ext = os.path.splitext(parsed.path)[1] or ".jpg"
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                filename = f"{url_hash}{ext}"
                local_file = os.path.join(download_dir, filename)

                # Download if not already exists
                if not os.path.exists(local_file):
                    resp = _session.get(url, timeout=30)
                    resp.raise_for_status()
                    with open(local_file, "wb") as f:
                        f.write(resp.content)

                att_copy["local_path"] = os.path.abspath(local_file)
            except Exception as e:
                att_copy["download_error"] = str(e)

        updated.append(att_copy)
    return updated


def save_item_to_db(conn, username: str, item: dict, file_path: str = None) -> bool:
    """
    Save a single feed item to the substack_items table.
    Downloads attachments to file_path if provided.
    Returns True if a new row was inserted, False if it already existed.
    """
    item_type = item.get("type", "unknown")

    if item_type == "post":
        post = item.get("post") or {}
        external_id = str(post.get("id", ""))
        title = post.get("title", "")
        subtitle = post.get("subtitle", "")
        slug = post.get("slug", "")
        canonical_url = post.get("canonical_url", "")
        post_date_str = post.get("post_date", "")

        # Fetch full article content
        body_text = ""
        body_html = ""
        if canonical_url:
            full_post = fetch_post_full_content(canonical_url)
            if full_post:
                body_html = full_post.get("body_html", "") or ""
                if body_html:
                    body_text = html_to_text(body_html)

        if not body_text:
            body_text = post.get("truncated_body_text", "") or ""

        post_date = None
        if post_date_str:
            try:
                post_date = datetime.fromisoformat(post_date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        attachments = []

        # Extract image attachments from body_html
        if body_html:
            img_urls = re.findall(r'<img[^>]+src="([^"]+)"', body_html)
            for img_url in img_urls:
                if "substack" in img_url or "substackcdn" in img_url:
                    attachments.append({"type": "image", "imageUrl": img_url})

    elif item_type == "comment":
        comment = item.get("comment") or {}
        context = item.get("context") or {}
        external_id = str(comment.get("id", ""))
        title = None
        subtitle = None
        slug = None
        canonical_url = None
        body_text = comment.get("body", "")
        body_html = None
        attachments = comment.get("attachments", [])
        post_date_str = comment.get("date", "")
        item_type = context.get("type", "note")  # note, comment_restack, etc.

        related_post = item.get("post") or {}
        related_post_title = related_post.get("title", "")

        post_date = None
        if post_date_str:
            try:
                post_date = datetime.fromisoformat(post_date_str.replace("Z", "+00:00"))
            except ValueError:
                pass
    else:
        # Unknown type - save raw
        external_id = str(hash(json.dumps(item, sort_keys=True)))[:20]
        title = None
        subtitle = None
        slug = None
        canonical_url = None
        body_text = json.dumps(item, indent=2, ensure_ascii=False)
        body_html = None
        attachments = []
        post_date = None
        related_post_title = None

    # For post type, related_post_title is not applicable
    if item_type == "post":
        related_post_title = None

    # Download attachments if file_path is provided
    if file_path and attachments:
        attachments = download_attachments(attachments, file_path, username)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO substack_items (
                author_username, item_type, external_id, title, subtitle,
                slug, canonical_url, post_date, body_text, body_html,
                attachments, related_post_title, status, raw_data
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s::jsonb, %s, %s, %s::jsonb
            )
            ON CONFLICT (author_username, item_type, external_id) DO NOTHING
            RETURNING id
            """,
            (
                username,
                item_type,
                external_id,
                title,
                subtitle,
                slug,
                canonical_url,
                post_date,
                body_text,
                body_html,
                json.dumps(attachments, ensure_ascii=False),
                related_post_title,
                "ready",
                json.dumps(item, ensure_ascii=False),
            ),
        )
        inserted = cur.fetchone() is not None

    conn.commit()
    return inserted


def crawl_target(conn, client: FinancialHubClient, target, max_items: int = 50, file_path: str = None):
    """Execute one full crawl cycle for a single Substack target."""
    print(f"\n{'─' * 50}")
    print(f"Target: [{target.id}] {target.target_name} ({target.target_identifier})")
    print(f"{'─' * 50}")

    username = target.target_identifier

    # ── Step 1: Before crawl ──
    print("[1/4] notify_crawl_start ...")
    run = client.notify_crawl_start(
        target_id=target.id,
        component_name=COMPONENT_NAME,
        metadata={"trigger": "manual", "max_items": max_items},
    )
    print(f"      crawl_run id={run.id}, status=running")

    # ── Step 2: Crawl ──
    start_time = time.time()
    try:
        print("[2/4] Fetching user ID ...")
        user_id = get_user_id(username)
        print(f"      user_id={user_id}")

        # Ensure author exists in DB
        ensure_author(conn, username, user_id)

        print(f"[3/4] Fetching items (max {max_items}) ...")
        items = get_user_posts(user_id, max_items=max_items)
        print(f"      Got {len(items)} items from API")

        # ── Step 3: Save to DB ──
        print("[4/4] Saving items to database ...")
        items_new = 0
        items_failed = 0
        for i, item in enumerate(items, 1):
            try:
                inserted = save_item_to_db(conn, username, item, file_path=file_path)
                if inserted:
                    items_new += 1
                    item_type = item.get("type", "unknown")
                    print(f"      [{i}/{len(items)}] New: {item_type}")
                else:
                    print(f"      [{i}/{len(items)}] Skipped (exists)")
            except Exception as e:
                items_failed += 1
                print(f"      [{i}/{len(items)}] Failed: {e}")

        duration_ms = int((time.time() - start_time) * 1000)

        # ── Step 4: After crawl ──
        client.notify_crawl_end(
            run_id=run.id,
            target_id=target.id,
            component_name=COMPONENT_NAME,
            success=True,
            items_found=len(items),
            items_new=items_new,
            items_failed=items_failed,
            duration_ms=duration_ms,
        )
        print(f"\n  ✓ Success: found={len(items)}, new={items_new}, "
              f"failed={items_failed}, duration={duration_ms}ms")

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        client.notify_crawl_end(
            run_id=run.id,
            target_id=target.id,
            component_name=COMPONENT_NAME,
            success=False,
            error_message=str(e),
            duration_ms=duration_ms,
        )
        print(f"\n  ✗ Failed: {e} (duration={duration_ms}ms)")


def main():
    parser = argparse.ArgumentParser(description="Substack crawler - fetch and store content.")
    parser.add_argument(
        "-n", "--max-items",
        type=int,
        default=50,
        help="Maximum number of items to fetch per target (default: 50, 0 for unlimited)"
    )
    parser.add_argument(
        "-f", "--file-path",
        type=str,
        default=None,
        help="Directory path to download attachments (images, etc.)"
    )
    args = parser.parse_args()

    max_items = args.max_items
    file_path = args.file_path

    # Resolve file_path to absolute
    if file_path:
        file_path = os.path.abspath(file_path)
        os.makedirs(file_path, exist_ok=True)
        print(f"Attachments will be saved to: {file_path}")

    conn = get_db_connection()
    try:
        # Initialize schema
        init_schema(conn)

        client = FinancialHubClient(conn)

        # ── Discover targets ──
        print("=== Discovering Substack Targets ===")
        targets = client.get_crawl_targets(source_type="substack", enabled=True)

        if not targets:
            print("No enabled substack targets found. Exiting.")
            return

        for t in targets:
            print(f"  [{t.id}] {t.target_name} ({t.target_identifier})")

        # ── Crawl each target ──
        for target in targets:
            crawl_target(conn, client, target, max_items=max_items, file_path=file_path)

        # ── Final state ──
        print(f"\n{'=' * 50}")
        print("=== Final Target States ===")
        print(f"{'=' * 50}")
        for target in targets:
            t = client.get_crawl_target_by_id(target.id)
            if t:
                print(f"\n  [{t.id}] {t.target_name}")
                print(f"    last_crawl_status: {t.last_crawl_status}")
                print(f"    last_crawl_at:     {t.last_crawl_at}")
                print(f"    last_error:        {t.last_error}")
                print(f"    total_items:       {t.total_items}")

    finally:
        conn.close()
        print("\nDone.")


if __name__ == "__main__":
    main()
