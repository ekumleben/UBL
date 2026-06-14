-- UBL Auth Migration: Phase 0 "allow all" → per-user RLS with Supabase Auth
-- Run this in the Supabase SQL Editor AFTER enabling Email auth
-- (Dashboard → Authentication → Providers → Email → enable, magic links on).
--
-- The pipeline (Python) must switch to the service_role key before this runs,
-- or it will lose write access. See SUPABASE_SERVICE_KEY in .env.example.

-- 1. Drop the Phase 0 allow-all policies
drop policy if exists "Phase 0: allow all" on users;
drop policy if exists "Phase 0: allow all" on articles;
drop policy if exists "Phase 0: allow all" on digests;
drop policy if exists "Phase 0: allow all" on reactions;
drop policy if exists "Phase 0: allow all" on conversations;
drop policy if exists "Phase 0: allow all" on actions;

-- 2. Make sure RLS is on everywhere (articles may have been missed in schema.sql)
alter table users enable row level security;
alter table articles enable row level security;
alter table digests enable row level security;
alter table reactions enable row level security;
alter table conversations enable row level security;
alter table actions enable row level security;

-- 3. users: each authenticated user can see/manage only their own row, matched by email
create policy "users: select own" on users for select
  to authenticated using (auth.jwt()->>'email' = email);
create policy "users: insert own" on users for insert
  to authenticated with check (auth.jwt()->>'email' = email);
create policy "users: update own" on users for update
  to authenticated using (auth.jwt()->>'email' = email);

-- 4. articles: readable by any signed-in user (news data, not sensitive).
--    Writes happen only via the pipeline's service_role key (bypasses RLS).
create policy "articles: read" on articles for select
  to authenticated using (true);

-- 5. digests: users see only their own
create policy "digests: select own" on digests for select
  to authenticated using (
    user_id in (select id from users where email = auth.jwt()->>'email')
  );

-- 6. actions: users insert and read only their own
create policy "actions: select own" on actions for select
  to authenticated using (
    user_id in (select id from users where email = auth.jwt()->>'email')
  );
create policy "actions: insert own" on actions for insert
  to authenticated with check (
    user_id in (select id from users where email = auth.jwt()->>'email')
  );

-- 7. reactions: same pattern
create policy "reactions: select own" on reactions for select
  to authenticated using (
    user_id in (select id from users where email = auth.jwt()->>'email')
  );
create policy "reactions: insert own" on reactions for insert
  to authenticated with check (
    user_id in (select id from users where email = auth.jwt()->>'email')
  );

-- 8. conversations: same pattern
create policy "conversations: select own" on conversations for select
  to authenticated using (
    user_id in (select id from users where email = auth.jwt()->>'email')
  );
create policy "conversations: insert own" on conversations for insert
  to authenticated with check (
    user_id in (select id from users where email = auth.jwt()->>'email')
  );
create policy "conversations: update own" on conversations for update
  to authenticated using (
    user_id in (select id from users where email = auth.jwt()->>'email')
  );
