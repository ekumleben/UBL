-- Actions table: tracks what users did with recommendations.
-- Run in Supabase SQL Editor.

create table if not exists actions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) not null,
  digest_id uuid references digests(id),
  action_type text not null default 'email',
  action_description text not null default '',
  channel text default '',
  completed boolean,
  clicked_at timestamptz default now(),
  created_at timestamptz default now()
);

create index idx_actions_user on actions(user_id);
create index idx_actions_clicked on actions(clicked_at desc);

alter table actions enable row level security;

-- Phase 0 allow-all (will be replaced by migration_auth.sql)
create policy "Phase 0: allow all" on actions for all using (true) with check (true);
