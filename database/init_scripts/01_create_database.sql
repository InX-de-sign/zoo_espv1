-- Create multiple databases for different services
CREATE DATABASE IF NOT EXISTS chatbot_db;
CREATE DATABASE IF NOT EXISTS localization_db;
CREATE DATABASE IF NOT EXISTS analytics_db;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE chatbot_db TO museum_user;
GRANT ALL PRIVILEGES ON DATABASE localization_db TO museum_user;
GRANT ALL PRIVILEGES ON DATABASE analytics_db TO museum_user;