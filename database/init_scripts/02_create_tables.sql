-- Connect to chatbot_db
\c chatbot_db;

-- Users table (children profiles)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) UNIQUE NOT NULL,
    age_group VARCHAR(20),
    interests TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    session_id VARCHAR(100),
    message TEXT,
    response TEXT,
    context JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Museum objects table
CREATE TABLE IF NOT EXISTS museum_objects (
    id SERIAL PRIMARY KEY,
    object_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200),
    description TEXT,
    location VARCHAR(100),
    category VARCHAR(50),
    metadata JSONB,
    embedding VECTOR(1536)  -- If using pgvector
);

-- Learning progress table
CREATE TABLE IF NOT EXISTS learning_progress (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    object_id VARCHAR(50) REFERENCES museum_objects(object_id),
    interaction_type VARCHAR(50),
    duration INTEGER,
    quiz_score FLOAT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Connect to localization_db
\c localization_db;

-- Beacon locations table
CREATE TABLE IF NOT EXISTS beacons (
    id SERIAL PRIMARY KEY,
    beacon_uuid VARCHAR(100),
    major INTEGER,
    minor INTEGER,
    x FLOAT,
    y FLOAT,
    z FLOAT,
    location_name VARCHAR(100),
    floor INTEGER
);

-- User locations table
CREATE TABLE IF NOT EXISTS user_locations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50),
    x FLOAT,
    y FLOAT,
    z FLOAT,
    confidence FLOAT,
    zone VARCHAR(100),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_user_locations_user_id ON user_locations(user_id);
CREATE INDEX idx_user_locations_timestamp ON user_locations(timestamp);
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_learning_progress_user_id ON learning_progress(user_id);