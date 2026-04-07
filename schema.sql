-- UBL Database Schema
-- Run this against your Supabase project via the SQL Editor in the dashboard.

-- Users
create table users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  district text,
  voter_registered boolean,
  preferences jsonb default '{}',
  preference_history jsonb default '[]',
  engagement_prefs jsonb default '{}',
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Ingested articles
create table articles (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  title text not null,
  url text unique,
  content text,
  published_at timestamptz,
  topics text[],
  relevance_tags jsonb default '{}',
  is_time_sensitive boolean default false,
  deadline timestamptz,
  relevance_score float default 0.0,
  summary text default '',
  created_at timestamptz default now()
);

-- Generated digests
create table digests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  week_of date not null,
  content jsonb not null,
  email_sent_at timestamptz,
  email_opened boolean default false,
  created_at timestamptz default now()
);

-- User reactions to digest items (preference learning)
create table reactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  digest_id uuid references digests(id),
  article_id uuid references articles(id),
  reaction text not null,
  comment text,
  created_at timestamptz default now()
);

-- Conversation history (web console follow-ups)
create table conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  messages jsonb not null default '[]',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Indexes
create index idx_articles_published_at on articles(published_at desc);
create index idx_articles_url on articles(url);
create index idx_digests_user_week on digests(user_id, week_of);

-- Row Level Security
alter table users enable row level security;
alter table digests enable row level security;
alter table reactions enable row level security;
alter table conversations enable row level security;
