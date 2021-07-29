from PIL import Image
from PIL.ExifTags import TAGS
from PIL.ExifTags import GPSTAGS
import os
from glob import glob
import psycopg2
from contextlib import closing
from time import sleep

DB_CONNECTION = "host={} user={} password={} dbname={} port={}".format(
    os.environ["DBHOST"], os.environ["DBUSER"], os.environ["DBPASS"], os.environ["DBNAME"], os.environ["DBPORT"]
)


def get_geotagging(exif):
    if not exif:
        raise ValueError("No EXIF metadata found")

    geotagging = {}
    for (idx, tag) in TAGS.items():
        if tag == "GPSInfo":
            if idx not in exif:
                raise ValueError("No EXIF geotagging found")

            for (key, val) in GPSTAGS.items():
                if key in exif[idx]:
                    geotagging[val] = exif[idx][key]

    return geotagging


def get_labeled_exif(exif):
    labeled = {}
    for (key, val) in exif.items():
        labeled[TAGS.get(key)] = val

    return labeled


def get_exif(filename):
    image = Image.open(filename)
    image.verify()
    return image._getexif()


def get_decimal_from_dms(dms, ref):

    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0

    if ref in ["S", "W"]:
        degrees = -degrees
        minutes = -minutes
        seconds = -seconds

    return round(degrees + minutes + seconds, 5)


def get_coordinates(geotags):
    lat = get_decimal_from_dms(geotags["GPSLatitude"], geotags["GPSLatitudeRef"])
    lon = get_decimal_from_dms(geotags["GPSLongitude"], geotags["GPSLongitudeRef"])

    return (lat, lon)


def clean_img(filename, output_path):
    photo = Image.open(filename)
    data = list(photo.getdata())
    no_exif = Image.new(photo.mode, photo.size)
    no_exif.putdata(data)
    no_exif.save(output_path)
    return


def insert_pg(sql):
    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        with conn:
            with conn.cursor() as curs:
                curs.execute(sql)
        conn.commit()

def image_resize(img):

    image = Image.open(img)
    width, height = image.size

    if width > height:

        w = 300
        h = int(w*1.333)
        image = image.resize((w,h), Image.ANTIALIAS)

        return image, "Wide"

    if height > width:

        h = 300
        w = int(h*1.333)
        image = image.resize((w,h), Image.ANTIALIAS)

        return image, "Tall"


if __name__ == "__main__":

    sleep(5)

    raw_img_dir = "/data/raw"
    clean_dir = "/data/ready"

    images = list(set(glob(os.path.join(raw_img_dir, "*.JPG")) + glob(os.path.join(raw_img_dir, "*.jpg"))))

    for img in images:

        img, orientation = image_resize(img)

        exif = get_exif(img)
        metadata = get_labeled_exif(exif)

        geotags = get_geotagging(exif)
        lat, lon = get_coordinates(geotags)

        date_taken = metadata["DateTimeOriginal"]
        guid_num = (
            float(metadata["ApertureValue"])
            * float(metadata["BrightnessValue"])
            * float(metadata["ExposureTime"])
            * lat
            * lon
        )
        guid = f"{guid_num}_{date_taken}"

        clean_filename = f"clean_{os.path.basename(img)}"
        output_img_path = os.path.join(clean_dir, clean_filename)

        if not os.path.exists(output_img_path):

            clean_img(img, output_img_path)

            insert_sql = f"""
            INSERT INTO roadtrip.images VALUES (
                '{guid}',
                '{clean_filename}',
                TO_TIMESTAMP('{date_taken}', 'YYYY:MM:DD HH24:MI:SS')::timestamp,
                ST_SetSRID(ST_Point({lon}, {lat}), 4326),
                '{orientation}'
            );
            """


            insert_pg(insert_sql)
