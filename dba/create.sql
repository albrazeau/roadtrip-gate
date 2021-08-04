CREATE SCHEMA IF NOT EXISTS roadtrip;
DROP TABLE roadtrip.images;

CREATE TABLE IF NOT EXISTS roadtrip.images (
    guid TEXT PRIMARY KEY,
    email_id TEXT,
    file_name TEXT UNIQUE,
    date_taken timestamp,
    geom GEOMETRY(Point, 4326),
    caption TEXT
);