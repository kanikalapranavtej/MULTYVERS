PRAGMA foreign_keys = ON;

-- 1. USERS

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK(role IN ('student', 'organizer', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 2. CATEGORIES

CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL UNIQUE,
    description TEXT
);


-- 3. VENUES

CREATE TABLE IF NOT EXISTS venues (
    venue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_name TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK(capacity > 0)
);


-- 4. EVENTS

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,

    organizer_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    venue_id INTEGER NOT NULL,

    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    registration_deadline TEXT NOT NULL,

    capacity INTEGER NOT NULL CHECK(capacity > 0),

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN (
            'draft',
            'pending',
            'approved',
            'rejected',
            'cancelled'
        )),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK(ends_at > starts_at),

    FOREIGN KEY(organizer_id) REFERENCES users(user_id),
    FOREIGN KEY(category_id) REFERENCES categories(category_id),
    FOREIGN KEY(venue_id) REFERENCES venues(venue_id)
);


-- 5. REGISTRATIONS

CREATE TABLE IF NOT EXISTS registrations (
    registration_id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,

    status TEXT NOT NULL DEFAULT 'confirmed'
        CHECK(status IN ('confirmed', 'cancelled')),

    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(event_id) REFERENCES events(event_id),

    UNIQUE(user_id, event_id)
);


-- INDEXES

CREATE INDEX IF NOT EXISTS idx_events_status
ON events(status);

CREATE INDEX IF NOT EXISTS idx_events_category
ON events(category_id);

CREATE INDEX IF NOT EXISTS idx_registrations_event
ON registrations(event_id);

CREATE INDEX IF NOT EXISTS idx_registrations_user
ON registrations(user_id);