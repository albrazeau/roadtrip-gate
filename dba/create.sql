CREATE SCHEMA IF NOT EXISTS roadtrip;
DROP TABLE IF EXISTS roadtrip.images;

CREATE TABLE IF NOT EXISTS roadtrip.images (
    attachment_id TEXT PRIMARY KEY, 
    email_id TEXT,
    photo_location TEXT,
    caption TEXT,
    filepath TEXT,
    date_taken timestamp,
    geom GEOMETRY(Point, 4326)
);


-- sql = f"""UPDATE roadtrip.images
-- SET date_taken = 
--     TO_TIMESTAMP('2021-07-04 00:00:00', 'YYYY:MM:DD HH24:MI:SS')::timestamp, 
--     geom = ST_SetSRID(ST_Point(-110.31791672482119, 44.62389804561182), 4326)
-- WHERE attachment_id = 'ANGjdJ8tXG1Yh45Sd8rRxYmZQ';"""

-- with closing(psycopg2.connect(DB_CONNECTION)) as conn:
--     with conn:
--         with conn.cursor() as curs:
--             curs.execute(sql)
--     conn.commit()