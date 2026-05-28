---
name: substack-query
description: Query Substack posts, notes, and author data stored in the local PostgreSQL database. Read-only — no data modification.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
---

# Substack Database Query Skill

This skill queries Substack content (posts, notes, comments) that has been previously crawled and stored in a PostgreSQL database.

**This skill is strictly read-only. It never inserts, updates, or deletes any data.**

## When to use

Use this skill when the user wants to:
- Read or search Substack posts, notes, or comments from the database
- List Substack authors that have been crawled
- Find articles by keyword, author, type, or date range
- View the full text of a specific article or note
- Get statistics on crawled Substack content

Do **NOT** use this skill when the user wants to crawl/download new content from Substack (that is a different workflow).

## Commands

All commands use the same base invocation:

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py <command> [options]
```

### 1. List authors

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py authors
```

Returns all crawled Substack authors with username, display name, bio, and profile URL.

### 2. Query items

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py items [options]
```

Options:
- `--author USERNAME` — Filter by author username
- `--type TYPE` — Filter by type: `post`, `note`, `comment_restack`
- `--search KEYWORD` — Search in title and body text (case-insensitive)
- `--since YYYY-MM-DD` — Start date (inclusive)
- `--until YYYY-MM-DD` — End date (inclusive)
- `--limit N` — Max results (default: 20, max: 500)
- `--offset N` — Skip first N results (for pagination)
- `--id ID` — Fetch a single item by its database ID
- `--full` — Show complete body text instead of preview

### 3. View statistics

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py stats [--author USERNAME]
```

Returns total counts by type, date ranges, and author count.

## Output format

Each item is output in a stable structured format:

```
标题: <title>
来源: substack
类型: <post|note|comment_restack>
作者: <username>
发布时间: <datetime>
原始链接: <url>
副标题: <subtitle>        (if present)
关联文章: <related post>  (if present)
状态: <status>
图片路径: <paths>         (if present)
正文预览: <first 200 chars>  (default)
--- 正文 ---              (with --full flag)
<full body text>
```

Items are separated by `============` lines.

## Examples

User says: "查看数据库里有哪些Substack作者"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py authors`

User says: "搜索substack里关于AI的文章"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py items --search AI`

User says: "查看用户 elad 最近10篇帖子"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py items --author elad --type post --limit 10`

User says: "查看ID为42的内容全文"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py items --id 42 --full`

User says: "2025年1月到3月的所有笔记"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py items --type note --since 2025-01-01 --until 2025-03-31`

User says: "Substack数据库里有多少内容"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py stats`

User says: "看看用户 paulgraham 的统计数据"
→ Run: `{baseDir}/.venv/bin/python {baseDir}/query_db.py stats --author paulgraham`

## Setup

This skill shares the virtual environment with the Substack crawler. If the virtual environment does not exist:

```bash
python3 -m venv {baseDir}/.venv
{baseDir}/.venv/bin/pip install -r {baseDir}/requirements.txt
```

Database connection is configured via `{baseDir}/.env`.
