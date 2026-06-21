-- Migration: Add timezone column to teams table
-- Run this if you already have an existing database

-- Add timezone column with default UTC
ALTER TABLE teams ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) NOT NULL DEFAULT 'UTC';

-- You can update existing teams to their correct timezone, for example:
-- UPDATE teams SET timezone = 'America/New_York' WHERE id = 1;
-- UPDATE teams SET timezone = 'Asia/Dubai' WHERE id = 2;

-- Common timezone examples:
-- 'America/New_York'     -- US Eastern Time
-- 'America/Chicago'      -- US Central Time
-- 'America/Los_Angeles'  -- US Pacific Time
-- 'Europe/London'        -- UK Time
-- 'Europe/Paris'         -- Central European Time
-- 'Asia/Dubai'           -- UAE Time
-- 'Asia/Riyadh'          -- Saudi Arabia Time
-- 'Asia/Tokyo'           -- Japan Time
-- 'Australia/Sydney'     -- Australian Eastern Time

-- See full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
