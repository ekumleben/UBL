-- Unsubscribe support. Run in Supabase SQL Editor.

-- 1. Flag column
alter table users add column if not exists unsubscribed_at timestamptz;

-- 2. RPC callable by anon: flips the flag for a given user UUID and nothing else.
--    The UUID is unguessable, so it acts as a bearer token in the email link.
create or replace function unsubscribe_user(user_uuid uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  update users set unsubscribed_at = now() where id = user_uuid;
  return found;
end;
$$;

-- Allow anonymous (email link clickers) and signed-in users to call it
grant execute on function unsubscribe_user(uuid) to anon, authenticated;

-- 3. Resubscribe (console "turn briefings back on" later)
create or replace function resubscribe_user(user_uuid uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  update users set unsubscribed_at = null where id = user_uuid;
  return found;
end;
$$;

grant execute on function resubscribe_user(uuid) to anon, authenticated;
