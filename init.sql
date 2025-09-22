-- Initial database setup for auto-wordpress-post
-- This file is mounted to docker-entrypoint-initdb.d/ and runs on container startup

-- Create the application database if it doesn't exist
CREATE DATABASE writer;

-- Connect to the application database
\c writer;

-- Create extensions that might be useful
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone to Tokyo
SET timezone TO 'Asia/Tokyo';

-- Create a user for the application (optional, can use postgres user)
-- CREATE USER app_user WITH PASSWORD 'app_password';
-- GRANT ALL PRIVILEGES ON DATABASE writer TO app_user;