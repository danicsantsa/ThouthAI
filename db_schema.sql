-- ===========================================================
-- Datenbank-Schema für das Workspace-Tracking-System
-- In Supabase: Projekt öffnen -> "SQL Editor" -> dieses Skript einfügen -> Run
-- ===========================================================

-- ---------- KERN-ENTITÄTEN ----------

-- Ein Profil pro Test-Person (du, deine Freunde)
create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    device_name text,
    created_at timestamptz default now()
);

-- Ein "Tracking-Lauf": alles, was zwischen Start und Ende eines Skript-Durchlaufs
-- passiert, gehört zu genau einer recording_session. Das erlaubt später,
-- z.B. "Montagvormittag" von "Dienstagabend" sauber zu trennen und zu vergleichen,
-- auch geräteübergreifend (device_name).
create table if not exists recording_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    device_name text,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    notes text
);

-- Zentraler Katalog aller bekannten Apps (statt App-Namen als freien Text
-- überall zu wiederholen). Eine Zeile pro einzigartiger App.
create table if not exists applications (
    id bigserial primary key,
    wm_class text unique not null,
    anzeige_name text,
    vorgeschlagene_kategorie text  -- Standard-Einordnung, kann pro Nutzer überschrieben werden
);

-- Pro Nutzer individuell: welche App zählt für DIESE Person als Arbeit?
-- Ersetzt die groben JSON-Listen von vorher durch echte, abfragbare Zeilen.
create table if not exists user_app_kategorie (
    user_id uuid references users(id) on delete cascade,
    application_id bigint references applications(id) on delete cascade,
    kategorie text not null,  -- 'Arbeit', 'Nicht-Arbeit', 'Unbekannt'
    primary key (user_id, application_id)
);

-- Benannte Aufgaben, an denen gerade gearbeitet wird
-- ("look at the name of the task he's working on" aus eurem Gespräch)
create table if not exists tasks (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    name text not null,
    started_at timestamptz,
    ended_at timestamptz,
    status text default 'offen'  -- 'offen', 'erledigt', 'abgebrochen'
);

-- Umgebungssensor-Daten (Temperatur, Lärm, etc.) -- bisher komplett gefehlt
create table if not exists environment_readings (
    id bigserial primary key,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    user_id uuid references users(id) on delete cascade,
    timestamp timestamptz not null,
    temperatur_celsius numeric,
    laerm_dezibel numeric,
    luftfeuchtigkeit_prozent numeric,
    helligkeit_lux numeric,
    sonstige jsonb  -- Platz für weitere/zukünftige Sensoren
);

-- Platz für die späteren Modell-Ergebnisse (Fokus-/Produktivitäts-Schätzung)
create table if not exists focus_scores (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    zeitfenster_start timestamptz not null,
    zeitfenster_ende timestamptz not null,
    fokus_score numeric,          -- z.B. 0-100
    produktivitaet_score numeric, -- z.B. 0-100
    quelle text                   -- 'heuristik' oder 'modell', zur Nachvollziehbarkeit
);

-- ---------- ROHDATEN AUS DEN TRACKING-SKRIPTEN ----------
-- Jede dieser Tabellen hängt jetzt zusätzlich an einer recording_session,
-- nicht nur lose am Nutzer.

create table if not exists activity_log (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    t_ms bigint not null default 0,
    timestamp timestamptz not null,
    app_name text,
    wm_class_instance text,
    fenster_titel text,
    kategorie text,
    pid integer,
    window_id bigint,
    workspace integer,
    fenster_breite integer,
    fenster_hoehe integer,
    fenster_x integer,
    fenster_y integer,
    maximiert boolean,
    monitor integer,
    frame_type integer,
    window_type integer,
    leerlauf_sekunden numeric,
    status text,
    wechsel_letzte_5min integer,
    interaktionen_letzte_5min integer,
    task_id bigint references tasks(id)  -- optional: welcher Aufgabe zugeordnet
);

create table if not exists activity_sessions (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    app_name text,
    kategorie text,
    start_zeit timestamptz not null,
    end_zeit timestamptz not null,
    dauer_sekunden numeric
);

create table if not exists inactivity_periods (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    start_zeit timestamptz not null,
    end_zeit timestamptz not null,
    dauer_sekunden numeric,
    app_dabei text,
    kategorie_dabei text
);

create table if not exists touch_events (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    t_ms bigint not null default 0,
    hand text,
    body_part text,
    event text
);

create table if not exists object_detections (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    t_ms bigint not null default 0,
    object_index integer,
    category_name text,
    score numeric,
    bbox_x numeric,
    bbox_y numeric,
    bbox_width numeric,
    bbox_height numeric,
    horizontal_pos text,
    relative_size numeric,
    hand_nearby boolean
);

create table if not exists pose_data (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    t_ms bigint not null default 0,
    landmarks jsonb
);

create table if not exists face_data (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    t_ms bigint not null default 0,
    blendshapes jsonb
);

create table if not exists hand_data (
    id bigserial primary key,
    user_id uuid references users(id) on delete cascade,
    recording_session_id uuid references recording_sessions(id) on delete cascade,
    t_ms bigint not null default 0,
    hand_index integer,
    handedness text,
    landmarks jsonb
);

-- ---------- INDIZES ----------
-- Migration für bereits angelegte Supabase-Projekte.
alter table users add column if not exists device_name text;
alter table users drop constraint if exists users_name_key;
alter table activity_log add column if not exists t_ms bigint not null default 0;
alter table touch_events add column if not exists t_ms bigint not null default 0;
alter table object_detections add column if not exists t_ms bigint not null default 0;
alter table pose_data add column if not exists t_ms bigint not null default 0;
alter table face_data add column if not exists t_ms bigint not null default 0;
alter table hand_data add column if not exists t_ms bigint not null default 0;

-- ---------- CLEANUP: alte timestamp_ms-Spalten entfernen ----------
do $$
begin
    if exists (select 1 from information_schema.columns where table_name = 'touch_events' and column_name = 'timestamp_ms') then
        update touch_events set t_ms = timestamp_ms where t_ms = 0 and timestamp_ms is not null;
    end if;
    if exists (select 1 from information_schema.columns where table_name = 'object_detections' and column_name = 'timestamp_ms') then
        update object_detections set t_ms = timestamp_ms where t_ms = 0 and timestamp_ms is not null;
    end if;
    if exists (select 1 from information_schema.columns where table_name = 'pose_data' and column_name = 'timestamp_ms') then
        update pose_data set t_ms = timestamp_ms where t_ms = 0 and timestamp_ms is not null;
    end if;
    if exists (select 1 from information_schema.columns where table_name = 'face_data' and column_name = 'timestamp_ms') then
        update face_data set t_ms = timestamp_ms where t_ms = 0 and timestamp_ms is not null;
    end if;
    if exists (select 1 from information_schema.columns where table_name = 'hand_data' and column_name = 'timestamp_ms') then
        update hand_data set t_ms = timestamp_ms where t_ms = 0 and timestamp_ms is not null;
    end if;
end $$;

alter table touch_events drop column if exists timestamp_ms;
alter table object_detections drop column if exists timestamp_ms;
alter table pose_data drop column if exists timestamp_ms;
alter table face_data drop column if exists timestamp_ms;
alter table hand_data drop column if exists timestamp_ms;

create unique index if not exists uq_users_device_name
    on users (device_name) where device_name is not null;
create index if not exists idx_activity_log_user_session_time
    on activity_log (user_id, recording_session_id, t_ms);
create index if not exists idx_activity_log_session on activity_log (recording_session_id, timestamp);
create index if not exists idx_sessions_session on activity_sessions (recording_session_id, start_zeit);
create index if not exists idx_inactivity_session on inactivity_periods (recording_session_id, start_zeit);
create index if not exists idx_touch_session on touch_events (recording_session_id, t_ms);
create index if not exists idx_objects_session on object_detections (recording_session_id, t_ms);
create index if not exists idx_pose_session on pose_data (recording_session_id, t_ms);
create index if not exists idx_face_session on face_data (recording_session_id, t_ms);
create index if not exists idx_hand_session on hand_data (recording_session_id, t_ms);
create index if not exists idx_environment_session on environment_readings (recording_session_id, timestamp);
create index if not exists idx_recording_sessions_user on recording_sessions (user_id, started_at);
