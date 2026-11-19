-- Financial Model app: Supabase schema
-- Run this once in the Supabase SQL editor (Dashboard > SQL Editor > New query).
-- Every row is owned by a Supabase auth user (user_id = auth.users.id).

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Financial models (one per business / project)
-- ---------------------------------------------------------------------------
create table if not exists public.financial_models (
    id                   uuid primary key default gen_random_uuid(),
    user_id              uuid not null references auth.users (id) on delete cascade,
    name                 text not null,                 -- e.g. "Techno Lab"
    business_name        text not null default '',      -- e.g. "DemoBiz"
    business_description text not null default '',      -- saved once, reused by every AI "Generate" popup
    start_year           integer not null default extract(year from now())::int,
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now()
);
create index if not exists financial_models_user_idx on public.financial_models (user_id);

-- ---------------------------------------------------------------------------
-- Categories for Fixed Assets, Pre-Operating Capital, Operating Capital, COGS
-- ---------------------------------------------------------------------------
create table if not exists public.categories (
    id                 uuid primary key default gen_random_uuid(),
    user_id            uuid not null references auth.users (id) on delete cascade,
    model_id           uuid not null references public.financial_models (id) on delete cascade,
    section            text not null check (section in ('fixed_asset', 'pre_operating', 'operating', 'cogs')),
    name               text not null,
    sort_order         integer not null default 0,
    add_to_pl          boolean not null default false,  -- Pre-Operating / Operating: feed Profit & Loss
    add_to_be          boolean not null default false,  -- Pre-Operating / Operating: feed Break Even
    depreciation_years numeric not null default 0,      -- Fixed Assets: straight-line useful life
    pl_growth_pct      numeric not null default 0,      -- Operating: yearly growth used in P&L projections
    cogs_percent       numeric not null default 0,      -- COGS: % of sales price
    created_at         timestamptz not null default now()
);
create index if not exists categories_model_idx on public.categories (model_id, section);

-- ---------------------------------------------------------------------------
-- Sub-category line items inside a category ("View" page)
-- ---------------------------------------------------------------------------
create table if not exists public.category_items (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid not null references auth.users (id) on delete cascade,
    model_id     uuid not null references public.financial_models (id) on delete cascade,
    category_id  uuid not null references public.categories (id) on delete cascade,
    sub_category text not null default '',
    item         text not null default '',   -- asset / item / role
    measure_unit text not null default '',   -- Fixed Assets: unit (Cent, Nos...). Others: number of months
    qty          numeric not null default 1,
    unit_cost    numeric not null default 0, -- approx. cost (Fixed Assets) or monthly cost (others)
    amount       numeric not null default 0,
    remarks      text not null default '',
    created_at   timestamptz not null default now()
);
create index if not exists category_items_category_idx on public.category_items (category_id);
create index if not exists category_items_model_idx on public.category_items (model_id);

-- ---------------------------------------------------------------------------
-- Per-model page settings stored as JSON
-- keys: sales_forecast, profit_loss, cogs_pricing, break_even, cash_flow, working_capital
-- ---------------------------------------------------------------------------
create table if not exists public.model_settings (
    model_id   uuid not null references public.financial_models (id) on delete cascade,
    key        text not null,
    user_id    uuid not null references auth.users (id) on delete cascade,
    data       jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    primary key (model_id, key)
);

-- ---------------------------------------------------------------------------
-- Row level security: a signed-in user only sees their own rows.
-- (A service_role key bypasses RLS; the app still filters every query by user_id.)
-- ---------------------------------------------------------------------------
alter table public.financial_models enable row level security;
alter table public.categories       enable row level security;
alter table public.category_items   enable row level security;
alter table public.model_settings   enable row level security;

drop policy if exists "own financial_models" on public.financial_models;
create policy "own financial_models" on public.financial_models
    for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own categories" on public.categories;
create policy "own categories" on public.categories
    for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own category_items" on public.category_items;
create policy "own category_items" on public.category_items
    for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own model_settings" on public.model_settings;
create policy "own model_settings" on public.model_settings
    for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- keep updated_at fresh
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists financial_models_touch on public.financial_models;
create trigger financial_models_touch before update on public.financial_models
    for each row execute function public.touch_updated_at();

drop trigger if exists model_settings_touch on public.model_settings;
create trigger model_settings_touch before update on public.model_settings
    for each row execute function public.touch_updated_at();
