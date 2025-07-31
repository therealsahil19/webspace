-- Initialize SpaceX Launch Tracker Database

-- Create database if it doesn't exist (handled by Docker environment variables)

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create launches table
CREATE TABLE IF NOT EXISTS launches (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) UNIQUE NOT NULL,
    mission_name VARCHAR(255) NOT NULL,
    launch_date TIMESTAMP WITH TIME ZONE,
    vehicle_type VARCHAR(100),
    payload_mass DECIMAL,
    orbit VARCHAR(100),
    success BOOLEAN,
    details TEXT,
    mission_patch_url TEXT,
    webcast_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create launch_sources table for tracking data origins
CREATE TABLE IF NOT EXISTS launch_sources (
    id SERIAL PRIMARY KEY,
    launch_id INTEGER REFERENCES launches(id) ON DELETE CASCADE,
    source_name VARCHAR(100) NOT NULL,
    source_url TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    data_quality_score DECIMAL CHECK (data_quality_score >= 0 AND data_quality_score <= 1)
);

-- Create data_conflicts table for tracking discrepancies
CREATE TABLE IF NOT EXISTS data_conflicts (
    id SERIAL PRIMARY KEY,
    launch_id INTEGER REFERENCES launches(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    source1_value TEXT,
    source2_value TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_launches_slug ON launches(slug);
CREATE INDEX IF NOT EXISTS idx_launches_launch_date ON launches(launch_date);
CREATE INDEX IF NOT EXISTS idx_launches_vehicle_type ON launches(vehicle_type);
CREATE INDEX IF NOT EXISTS idx_launch_sources_launch_id ON launch_sources(launch_id);
CREATE INDEX IF NOT EXISTS idx_data_conflicts_launch_id ON data_conflicts(launch_id);
CREATE INDEX IF NOT EXISTS idx_data_conflicts_resolved ON data_conflicts(resolved);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for launches table
DROP TRIGGER IF EXISTS update_launches_updated_at ON launches;
CREATE TRIGGER update_launches_updated_at
    BEFORE UPDATE ON launches
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();