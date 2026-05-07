---
name: substack-scraper
description: Download posts and notes from a Substack user's profile. Supports pagination and saves content as text files.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
---

# Substack Scraper Skill

This skill downloads posts and notes from a Substack user's profile page.

## When to use

Use this skill when the user wants to:
- Download/scrape/fetch posts from a Substack user
- Save Substack content locally as text files
- Get recent notes or articles from a Substack profile

## How to use

Run the following command from the skill directory `{baseDir}`:

```bash
{baseDir}/.venv/bin/python {baseDir}/scraper.py <username> -n <count>
```

### Parameters

- `<username>` (required): The Substack username (e.g. `takashiyasui`, with or without `@`)
- `-n <count>` (optional): Maximum number of items to fetch (default: 50, use 0 for unlimited)
- `-o <dir>` (optional): Output directory (default: `output`)

### Examples

User says: "下载substack用户yamashida最近的100条帖子"
→ Extract username=`yamashida`, count=`100`
→ Run: `{baseDir}/.venv/bin/python {baseDir}/scraper.py yamashida -n 100`

User says: "Fetch the last 20 posts from @takashiyasui on Substack"
→ Extract username=`takashiyasui`, count=`20`
→ Run: `{baseDir}/.venv/bin/python {baseDir}/scraper.py takashiyasui -n 20`

User says: "下载substack用户a16z的所有帖子"
→ Extract username=`a16z`, count=`0` (unlimited)
→ Run: `{baseDir}/.venv/bin/python {baseDir}/scraper.py a16z -n 0`

## Output

Files are saved to `{baseDir}/output/<username>/<year>/<month>/<datetime>_<type>_<title>.txt`

Each file contains:
- Metadata header (type, date, URL, etc.)
- Full text content (for notes/comments)
- Preview text (for posts; full post content to be processed separately)
- Attachment links (images, etc.) if present

## Setup

If the virtual environment does not exist, create it first:

```bash
python3 -m venv {baseDir}/.venv
{baseDir}/.venv/bin/pip install -r {baseDir}/requirements.txt
```
