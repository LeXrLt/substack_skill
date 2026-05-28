"""
Substack database query tool (read-only).

Provides CLI access to query substack_authors and substack_items tables.
Strictly SELECT-only — no INSERT, UPDATE, or DELETE operations.

Usage:
    python query_db.py authors
    python query_db.py items [--author USERNAME] [--type TYPE] [--search KEYWORD]
                             [--since DATE] [--until DATE] [--limit N] [--offset N]
                             [--id ID] [--full]
    python query_db.py stats [--author USERNAME]
"""

import os
import sys
import json
import argparse
from datetime import datetime

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv


# Load environment variables from .env (same as crawler)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_db_connection():
    """Create a read-only database connection using .env config (readonly user)."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_READONLY_USER", "hub_readonly"),
        password=os.getenv("POSTGRES_READONLY_PASSWORD", "hub_password"),
        dbname=os.getenv("POSTGRES_DB", "financial_hub"),
    )
    conn.set_session(readonly=True, autocommit=True)
    return conn


# ---------------------------------------------------------------------------
# Output formatting — stable structure for AI Agent consumption
# ---------------------------------------------------------------------------

def format_author(row: dict) -> str:
    """Format a single author record."""
    lines = [
        f"作者: {row['username']}",
        f"显示名: {row.get('display_name') or ''}",
        f"简介: {row.get('bio') or ''}",
        f"主页: {row.get('profile_url') or ''}",
        f"备注: {row.get('notes') or ''}",
        f"创建时间: {row.get('created_at', '')}",
        f"更新时间: {row.get('updated_at', '')}",
    ]
    return "\n".join(lines)


def format_item(row: dict, full: bool = False) -> str:
    """
    Format a single item record in stable output structure.

    Fields follow 抓取系统.md §11:
        标题 / 来源 / 作者 / 发布时间 / 正文 / 图片路径 / 原始链接 / metadata
    """
    title = row.get("title") or "(无标题)"
    item_type = row.get("item_type") or "unknown"
    author = row.get("author_username") or ""
    post_date = row.get("post_date") or ""
    canonical_url = row.get("canonical_url") or ""
    related = row.get("related_post_title") or ""
    status = row.get("status") or ""

    lines = [
        f"标题: {title}",
        f"来源: substack",
        f"类型: {item_type}",
        f"作者: {author}",
        f"发布时间: {post_date}",
        f"原始链接: {canonical_url}",
    ]

    if row.get("subtitle"):
        lines.append(f"副标题: {row['subtitle']}")
    if related:
        lines.append(f"关联文章: {related}")
    lines.append(f"状态: {status}")

    # Attachments
    attachments = row.get("attachments") or []
    if isinstance(attachments, str):
        try:
            attachments = json.loads(attachments)
        except json.JSONDecodeError:
            attachments = []
    if attachments:
        paths = []
        for att in attachments:
            if att.get("local_path"):
                paths.append(att["local_path"])
            elif att.get("imageUrl"):
                paths.append(att["imageUrl"])
        if paths:
            lines.append(f"图片路径: {'; '.join(paths)}")

    # Body text
    body = row.get("body_text") or ""
    if full:
        lines.append("")
        lines.append("--- 正文 ---")
        lines.append(body if body else "(无正文)")
    else:
        preview = body[:200].replace("\n", " ") if body else "(无正文)"
        if len(body) > 200:
            preview += "..."
        lines.append(f"正文预览: {preview}")

    return "\n".join(lines)


ITEM_SEPARATOR = "\n" + "=" * 60 + "\n"


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def cmd_authors(conn, args):
    """List all authors."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM substack_authors ORDER BY username"
        )
        rows = cur.fetchall()

    if not rows:
        print("没有找到任何作者。")
        return

    print(f"共 {len(rows)} 位作者:\n")
    print(ITEM_SEPARATOR.join(format_author(r) for r in rows))


def cmd_items(conn, args):
    """Query items with optional filters."""
    conditions = []
    params = []

    if args.author:
        conditions.append("i.author_username = %s")
        params.append(args.author)

    if args.type:
        conditions.append("i.item_type = %s")
        params.append(args.type)

    if args.search:
        conditions.append("(i.body_text ILIKE %s OR i.title ILIKE %s)")
        pattern = f"%{args.search}%"
        params.extend([pattern, pattern])

    if args.since:
        conditions.append("i.post_date >= %s")
        params.append(args.since)

    if args.until:
        conditions.append("i.post_date <= %s")
        params.append(args.until)

    if args.id:
        conditions.append("i.id = %s")
        params.append(args.id)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    limit = min(args.limit, 500)
    offset = args.offset

    sql = f"""
        SELECT i.*
        FROM substack_items i
        {where}
        ORDER BY i.post_date DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        print("没有找到匹配的内容。")
        return

    # Count total
    count_sql = f"SELECT COUNT(*) FROM substack_items i {where}"
    with conn.cursor() as cur:
        cur.execute(count_sql, params[:-2])  # exclude LIMIT/OFFSET params
        total = cur.fetchone()[0]

    print(f"查询结果: {len(rows)} 条 (共 {total} 条匹配, "
          f"offset={offset}, limit={limit})\n")
    print(ITEM_SEPARATOR.join(format_item(r, full=args.full) for r in rows))


def cmd_stats(conn, args):
    """Show statistics overview."""
    author_filter = ""
    params = []
    if args.author:
        author_filter = "WHERE author_username = %s"
        params = [args.author]

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Total authors
        cur.execute("SELECT COUNT(*) AS cnt FROM substack_authors")
        author_count = cur.fetchone()["cnt"]

        # Items by type
        cur.execute(
            f"""
            SELECT item_type, COUNT(*) AS cnt,
                   MIN(post_date) AS earliest,
                   MAX(post_date) AS latest
            FROM substack_items
            {author_filter}
            GROUP BY item_type
            ORDER BY cnt DESC
            """,
            params,
        )
        type_rows = cur.fetchall()

        # Total items
        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM substack_items {author_filter}",
            params,
        )
        total_items = cur.fetchone()["cnt"]

    header = "统计概览"
    if args.author:
        header += f" (作者: {args.author})"

    lines = [
        header,
        f"作者总数: {author_count}",
        f"内容总数: {total_items}",
        "",
        "按类型统计:",
    ]
    for r in type_rows:
        lines.append(
            f"  {r['item_type']}: {r['cnt']} 条 "
            f"(最早: {r['earliest'] or 'N/A'}, 最新: {r['latest'] or 'N/A'})"
        )

    print("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Substack 数据库只读查询工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- authors ---
    subparsers.add_parser("authors", help="列出所有作者")

    # --- items ---
    p_items = subparsers.add_parser("items", help="查询内容条目")
    p_items.add_argument("--author", type=str, default=None, help="按作者用户名过滤")
    p_items.add_argument("--type", type=str, default=None,
                         help="按类型过滤 (post / note / comment_restack)")
    p_items.add_argument("--search", type=str, default=None, help="按关键词搜索正文和标题")
    p_items.add_argument("--since", type=str, default=None,
                         help="起始日期 (含), 格式 YYYY-MM-DD")
    p_items.add_argument("--until", type=str, default=None,
                         help="截止日期 (含), 格式 YYYY-MM-DD")
    p_items.add_argument("--limit", type=int, default=20, help="返回条数上限 (默认 20, 最大 500)")
    p_items.add_argument("--offset", type=int, default=0, help="跳过前 N 条 (分页用)")
    p_items.add_argument("--id", type=int, default=None, help="按数据库 ID 精确查询单条")
    p_items.add_argument("--full", action="store_true", help="显示完整正文 (默认只显示预览)")

    # --- stats ---
    p_stats = subparsers.add_parser("stats", help="查看统计信息")
    p_stats.add_argument("--author", type=str, default=None, help="按作者过滤统计")

    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.command == "authors":
            cmd_authors(conn, args)
        elif args.command == "items":
            cmd_items(conn, args)
        elif args.command == "stats":
            cmd_stats(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
