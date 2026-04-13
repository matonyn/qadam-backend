-- Qadam app schema (mirrors SQLAlchemy models). Applied via Supabase MCP apply_migration.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  student_id TEXT NOT NULL,
  avatar TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  is_revoked BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE buildings (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  short_name TEXT NOT NULL,
  description TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  floors INTEGER,
  has_elevator BOOLEAN DEFAULT false,
  has_ramp BOOLEAN DEFAULT false,
  category TEXT,
  image_url TEXT
);

CREATE TABLE rooms (
  id TEXT PRIMARY KEY,
  building_id TEXT NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  floor INTEGER,
  type TEXT,
  capacity INTEGER,
  accessible BOOLEAN DEFAULT true
);

CREATE TABLE campus_events (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  title TEXT NOT NULL,
  description TEXT,
  location TEXT,
  building_id TEXT REFERENCES buildings(id) ON DELETE SET NULL,
  start_date TEXT,
  end_date TEXT,
  category TEXT,
  organizer TEXT,
  is_registration_required BOOLEAN DEFAULT false,
  registration_url TEXT,
  image_url TEXT
);

CREATE TABLE discounts (
  id TEXT PRIMARY KEY,
  vendor_name TEXT NOT NULL,
  vendor_logo TEXT,
  title TEXT NOT NULL,
  description TEXT,
  discount_percentage INTEGER DEFAULT 0,
  category TEXT,
  valid_until TEXT,
  code TEXT,
  terms TEXT,
  is_verified BOOLEAN DEFAULT true
);

CREATE TABLE study_rooms (
  id TEXT PRIMARY KEY,
  building_id TEXT NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  building_name TEXT,
  name TEXT NOT NULL,
  floor INTEGER,
  capacity INTEGER,
  amenities JSONB,
  is_available BOOLEAN DEFAULT true,
  current_occupancy INTEGER DEFAULT 0,
  noise_level TEXT,
  image_url TEXT
);

CREATE TABLE routes (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  start_lat DOUBLE PRECISION,
  start_lng DOUBLE PRECISION,
  start_name TEXT,
  end_lat DOUBLE PRECISION,
  end_lng DOUBLE PRECISION,
  end_name TEXT,
  distance INTEGER,
  duration INTEGER,
  is_accessible BOOLEAN,
  crowd_level TEXT,
  waypoints JSONB,
  instructions JSONB,
  preference TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE event_registrations (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  event_id TEXT NOT NULL REFERENCES campus_events(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_event_user UNIQUE (event_id, user_id)
);

CREATE TABLE reviews (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_name TEXT NOT NULL,
  rating INTEGER NOT NULL,
  comment TEXT,
  sentiment TEXT,
  helpful INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE review_helpful (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  review_id TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT uq_review_user_helpful UNIQUE (review_id, user_id)
);

CREATE TABLE review_reports (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  review_id TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE courses (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  credits INTEGER,
  grade TEXT,
  grade_points DOUBLE PRECISION,
  semester TEXT,
  instructor TEXT,
  schedule JSONB
);

CREATE TABLE academic_plans (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  total_credits_required INTEGER,
  credits_completed INTEGER,
  credits_in_progress INTEGER,
  gpa DOUBLE PRECISION,
  standing TEXT,
  expected_graduation TEXT,
  major TEXT,
  minor TEXT
);

CREATE TABLE planner_events (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  type TEXT,
  location TEXT,
  building_id TEXT,
  color TEXT,
  is_recurring BOOLEAN DEFAULT false,
  reminder_minutes INTEGER
);

CREATE TABLE study_room_bookings (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  room_id TEXT NOT NULL REFERENCES study_rooms(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  status TEXT DEFAULT 'confirmed',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_settings (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  notifications_settings JSONB,
  accessibility_settings JSONB,
  privacy_settings JSONB,
  language TEXT DEFAULT 'en',
  theme TEXT DEFAULT 'light'
);

CREATE TABLE notifications (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  message TEXT,
  type TEXT,
  date TIMESTAMPTZ NOT NULL DEFAULT now(),
  "read" BOOLEAN DEFAULT false,
  action JSONB
);

CREATE TABLE saved_routes (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  route_id TEXT NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  saved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_users_email ON users(email);
CREATE INDEX ix_refresh_tokens_token ON refresh_tokens(token);
