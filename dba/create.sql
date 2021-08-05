CREATE SCHEMA IF NOT EXISTS roadtrip;
DROP TABLE roadtrip.images;

CREATE TABLE IF NOT EXISTS roadtrip.images (
    attachment_id TEXT PRIMARY KEY, 
    email_id TEXT,
    photo_location TEXT,
    caption TEXT,
    filepath TEXT,
    date_taken timestamp,
    geom GEOMETRY(Point, 4326)
);