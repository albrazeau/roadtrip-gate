CREATE SCHEMA IF NOT EXISTS roadtrip;

CREATE TABLE IF NOT EXISTS roadtrip.images (
    guid TEXT PRIMARY KEY,
    file_name TEXT UNIQUE,
    date_taken timestamp,
    geom GEOMETRY(Point, 4326),
    orientation TEXT
);