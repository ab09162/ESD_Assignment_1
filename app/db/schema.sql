CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE TABLE IF NOT EXISTS schema_version (
    version integer PRIMARY KEY,
    installed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rooms (
    id integer PRIMARY KEY,
    name varchar(80) NOT NULL UNIQUE,
    capacity integer NOT NULL CHECK (capacity > 0)
);
CREATE TABLE IF NOT EXISTS bookings (
    id uuid PRIMARY KEY,
    room_id integer NOT NULL REFERENCES rooms(id),
    start_time timestamptz NOT NULL,
    end_time timestamptz NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    cancelled_at timestamptz,
    CONSTRAINT valid_booking_duration CHECK (end_time > start_time),
    CONSTRAINT no_overlapping_bookings EXCLUDE USING gist (
        room_id WITH =,
        tstzrange(start_time, end_time, '[)') WITH &&
    ) WHERE (status = 'confirmed')
);
CREATE INDEX IF NOT EXISTS bookings_room_start_idx ON bookings (room_id, start_time, id);
CREATE INDEX IF NOT EXISTS bookings_start_idx ON bookings (start_time, id);
CREATE INDEX IF NOT EXISTS bookings_active_end_idx ON bookings (end_time) WHERE status = 'confirmed';
INSERT INTO rooms (id, name, capacity) VALUES
    (1, 'Library Study Room A', 4),
    (2, 'Library Study Room B', 6),
    (3, 'Engineering Group Room', 8)
ON CONFLICT (id) DO NOTHING;
INSERT INTO schema_version (version) VALUES (1) ON CONFLICT DO NOTHING;
