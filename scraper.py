import requests
import re
import json
import os
import argparse
from datetime import datetime
from html.parser import HTMLParser

def get_user_id(username: str) -> str:
    """
    Scrape the user profile page to extract the user ID.
    """
    # Remove @ if present
    if username.startswith('@'):
        username = username[1:]
        
    url = f"https://substack.com/@{username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    # Extract window._preloads JSON data
    match = re.search(r"window\._preloads\s*=\s*JSON\.parse\(\"(.*?)\"\)", response.text)
    if not match:
        raise ValueError(f"Could not find window._preloads for user {username}")
        
    # The string is unicode escaped, so we need to decode it
    json_str = match.group(1).encode().decode("unicode_escape")
    data = json.loads(json_str)
    
    if "profile" not in data or "id" not in data["profile"]:
        raise ValueError(f"Could not find profile ID in preloads data for user {username}")
        
    return str(data["profile"]["id"])

def get_user_posts(user_id: str, max_items: int = 50):
    """
    Query the API to get the user's posts with pagination support.
    
    Args:
        user_id: The Substack user ID.
        max_items: Maximum number of items to fetch. Set to 0 or negative for unlimited.
    
    Returns:
        A list of all fetched items across pages.
    """
    base_url = f"https://substack.com/api/v1/reader/feed/profile/{user_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    all_items = []
    cursor = None
    page = 1
    
    while True:
        url = base_url
        if cursor:
            url = f"{base_url}?cursor={cursor}"
        
        print(f"  Fetching page {page}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        items = data.get("items", [])
        all_items.extend(items)
        
        print(f"  Got {len(items)} items on page {page}, total so far: {len(all_items)}")
        
        # Check if we have enough items
        if max_items > 0 and len(all_items) >= max_items:
            all_items = all_items[:max_items]
            break
        
        # Get nextCursor for pagination
        next_cursor = data.get("nextCursor")
        if not next_cursor:
            # No more pages
            break
        
        cursor = next_cursor
        page += 1
    
    return all_items

class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML content."""
    
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False
    
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._skip = True
        elif tag in ('br', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'):
            self._text.append('\n')
    
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._skip = False
        elif tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._text.append('\n')
    
    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)
    
    def get_text(self):
        return ''.join(self._text).strip()


def html_to_text(html_content: str) -> str:
    """Convert HTML to plain text."""
    extractor = HTMLTextExtractor()
    extractor.feed(html_content)
    # Collapse multiple blank lines into at most two
    text = extractor.get_text()
    lines = text.split('\n')
    result = []
    blank_count = 0
    for line in lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 2:
                result.append('')
        else:
            blank_count = 0
            result.append(line)
    return '\n'.join(result)


def sanitize_filename(name: str) -> str:
    """Remove or replace characters not suitable for filenames."""
    # Replace common problematic characters
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']:
        name = name.replace(ch, '_')
    # Collapse multiple underscores
    while '__' in name:
        name = name.replace('__', '_')
    return name.strip('_')[:100]


def parse_item_date(date_str: str) -> datetime:
    """Parse a date string from the API into a datetime object."""
    if date_str:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now()


def save_comment_item(item: dict, username: str, output_dir: str) -> str:
    """
    Save a comment/note item as a txt file.
    Returns the saved file path, or empty string if skipped.
    """
    comment = item.get("comment") or {}
    context = item.get("context") or {}
    
    body = comment.get("body", "")
    date_str = comment.get("date", "")
    comment_id = comment.get("id", "unknown")
    attachments = comment.get("attachments", [])
    context_type = context.get("type", "comment")
    
    # Get related post info if any
    post = item.get("post") or {}
    post_title = post.get("title", "")
    
    # Parse date
    item_dt = parse_item_date(date_str)
    year = item_dt.strftime("%Y")
    month = item_dt.strftime("%m")
    time_prefix = item_dt.strftime("%Y%m%d_%H%M%S")
    
    # Build filename
    # Use first 30 chars of body as part of filename for readability
    body_preview = body[:30].strip() if body else f"id_{comment_id}"
    safe_name = sanitize_filename(body_preview)
    filename = f"{time_prefix}_{context_type}_{safe_name}.txt"
    
    # Build directory path
    dir_path = os.path.join(output_dir, username, year, month)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, filename)
    
    # Build file content
    content_lines = [
        f"Type: {context_type}",
        f"Date: {item_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Comment ID: {comment_id}",
    ]
    
    if post_title:
        content_lines.append(f"Related Post: {post_title}")
    
    content_lines.append("")
    content_lines.append("=" * 60)
    content_lines.append("")
    content_lines.append(body)
    
    # Append attachment info
    if attachments:
        content_lines.append("")
        content_lines.append("-" * 60)
        content_lines.append(f"Attachments ({len(attachments)}):")
        for att in attachments:
            att_type = att.get("type", "unknown")
            if att_type == "image":
                content_lines.append(f"  [Image] {att.get('imageUrl', '')}")
            else:
                content_lines.append(f"  [{att_type}] {json.dumps(att)}")
    
    content = "\n".join(content_lines)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return file_path


def fetch_post_full_content(url: str) -> dict:
    """
    Fetch the full post content by visiting the article page.
    Extracts body_html and metadata from window._preloads.
    
    Returns a dict with keys: body_html, title, subtitle, post_date, canonical_url, etc.
    Returns empty dict on failure.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"    Warning: Failed to fetch {url}: {e}")
        return {}
    
    match = re.search(r"window\._preloads\s*=\s*JSON\.parse\(\"(.*?)\"\)", response.text)
    if not match:
        print(f"    Warning: Could not find _preloads in {url}")
        return {}
    
    try:
        json_str = match.group(1).encode().decode("unicode_escape")
        data = json.loads(json_str)
    except Exception as e:
        print(f"    Warning: Failed to parse _preloads from {url}: {e}")
        return {}
    
    return data.get("post", {}) or {}


def save_post_item(item: dict, username: str, output_dir: str) -> str:
    """
    Save a post item as a txt file with full article content.
    Fetches the full body from the post's canonical URL.
    Returns the saved file path, or empty string if skipped.
    """
    post = item.get("post") or {}
    title = post.get("title", "Untitled")
    post_date_str = post.get("post_date", "")
    subtitle = post.get("subtitle", "")
    slug = post.get("slug", "")
    canonical_url = post.get("canonical_url", "")
    
    # Parse post_date
    item_dt = parse_item_date(post_date_str)
    year = item_dt.strftime("%Y")
    month = item_dt.strftime("%m")
    time_prefix = item_dt.strftime("%Y%m%d_%H%M%S")
    
    # Build filename
    safe_title = sanitize_filename(title)
    filename = f"{time_prefix}_post_{safe_title}.txt"
    
    # Build directory path
    dir_path = os.path.join(output_dir, username, year, month)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, filename)
    
    # Fetch full post content from canonical URL
    body_text = ""
    if canonical_url:
        print(f"    Fetching full content: {canonical_url}")
        full_post = fetch_post_full_content(canonical_url)
        if full_post:
            body_html = full_post.get("body_html", "")
            if body_html:
                body_text = html_to_text(body_html)
            # Use richer metadata from full fetch if available
            if not subtitle:
                subtitle = full_post.get("subtitle", "")
    
    if not body_text:
        # Fallback to truncated body from feed
        truncated_body = post.get("truncated_body_text", "")
        body_text = f"(Preview only) {truncated_body}" if truncated_body else "(Content not available)"
    
    # Build file content (same format as note)
    content_lines = [
        f"Type: post",
        f"Title: {title}",
    ]
    if subtitle:
        content_lines.append(f"Subtitle: {subtitle}")
    content_lines.append(f"Date: {item_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if canonical_url:
        content_lines.append(f"URL: {canonical_url}")
    if slug:
        content_lines.append(f"Slug: {slug}")
    
    content_lines.append("")
    content_lines.append("=" * 60)
    content_lines.append("")
    content_lines.append(body_text)
    
    content = "\n".join(content_lines)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return file_path


def save_items_to_files(items: list, username: str, output_dir: str = "output"):
    """
    Save all items as txt files.
    Path structure: output/<username>/YYYY/MM/<datetime>_<type>_<name>.txt
    """
    saved_count = 0
    
    for item in items:
        item_type = item.get("type")
        
        if item_type == "comment":
            file_path = save_comment_item(item, username, output_dir)
        elif item_type == "post":
            file_path = save_post_item(item, username, output_dir)
        else:
            # Unknown type, save raw JSON
            context = item.get("context") or {}
            date_str = context.get("timestamp", "")
            item_dt = parse_item_date(date_str)
            time_prefix = item_dt.strftime("%Y%m%d_%H%M%S")
            year = item_dt.strftime("%Y")
            month = item_dt.strftime("%m")
            
            dir_path = os.path.join(output_dir, username, year, month)
            os.makedirs(dir_path, exist_ok=True)
            filename = f"{time_prefix}_{item_type or 'unknown'}.txt"
            file_path = os.path.join(dir_path, filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Type: {item_type}\n\n")
                f.write(json.dumps(item, indent=2, ensure_ascii=False))
        
        if file_path:
            saved_count += 1
            print(f"  Saved: {file_path}")
    
    return saved_count


def main():
    parser = argparse.ArgumentParser(
        description="Download Substack user posts and notes."
    )
    parser.add_argument(
        "username",
        help="Substack username (with or without @)"
    )
    parser.add_argument(
        "-n", "--max-items",
        type=int,
        default=50,
        help="Maximum number of items to fetch (default: 50, 0 for unlimited)"
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory (default: output)"
    )
    
    args = parser.parse_args()
    username = args.username.lstrip("@")
    max_items = args.max_items
    output_dir = args.output
    
    print(f"Fetching user ID for @{username}...")
    
    try:
        user_id = get_user_id(username)
        print(f"Found user ID: {user_id}")
        
        print(f"Fetching items (max {max_items if max_items > 0 else 'unlimited'})...")
        items = get_user_posts(user_id, max_items=max_items)
        
        print(f"\nTotal fetched: {len(items)} items.")
        
        # Count by type
        from collections import Counter
        type_counts = Counter(i.get("type") for i in items)
        for t, c in type_counts.items():
            print(f"  {t}: {c}")
        
        # Save all items to files
        print(f"\nSaving to {output_dir}/{username}/...")
        saved = save_items_to_files(items, username, output_dir=output_dir)
        print(f"\nDone! Saved {saved} items.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
