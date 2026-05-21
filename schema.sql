-- Substack data tables
-- Following the design principles from 抓取系统.md:
-- - Each source has its own tables
-- - Preserve raw_data JSONB for original API responses
-- - Keep status fields for crawl state tracking

-- Substack authors/profiles
CREATE TABLE IF NOT EXISTS substack_authors (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(50),
    display_name VARCHAR(500),
    bio TEXT,
    profile_url VARCHAR(1000),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Substack items (posts, notes, comments)
CREATE TABLE IF NOT EXISTS substack_items (
    id SERIAL PRIMARY KEY,
    author_username VARCHAR(255) NOT NULL REFERENCES substack_authors(username),
    item_type VARCHAR(50) NOT NULL,          -- 'post', 'note', 'comment_restack'
    external_id VARCHAR(255),                -- Substack's own ID for the item
    title VARCHAR(1000),
    subtitle VARCHAR(1000),
    slug VARCHAR(500),
    canonical_url VARCHAR(2000),
    post_date TIMESTAMP WITH TIME ZONE,
    body_text TEXT,                           -- Plain text content
    body_html TEXT,                           -- Original HTML content (for posts)
    attachments JSONB DEFAULT '[]'::JSONB,   -- Image URLs, etc.
    related_post_title VARCHAR(1000),         -- For comments: which post it relates to
    status VARCHAR(50) DEFAULT 'ready',      -- pending, processing, ready, failed
    raw_data JSONB,                           -- Original API response item
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(author_username, item_type, external_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_substack_items_author ON substack_items(author_username);
CREATE INDEX IF NOT EXISTS idx_substack_items_type ON substack_items(item_type);
CREATE INDEX IF NOT EXISTS idx_substack_items_post_date ON substack_items(post_date DESC);
CREATE INDEX IF NOT EXISTS idx_substack_items_status ON substack_items(status);
