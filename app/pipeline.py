from PIL import ImageFile, Image
ImageFile.LOAD_TRUNCATED_IMAGES = True
from PIL.ExifTags import TAGS
from PIL.ExifTags import GPSTAGS
import os
from glob import glob
import psycopg2
from contextlib import closing
from time import sleep
from headers import DB_CONNECTION_LOCAL, DB_CONNECTION_DOCKER

# local
# DB_CONNECTION = DB_CONNECTION_LOCAL

# docker
DB_CONNECTION = DB_CONNECTION_DOCKER

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


# def clean_img(filename, output_path):
#     photo = Image.open(filename)
#     data = list(photo.getdata())
#     no_exif = Image.new(photo.mode, photo.size)
#     no_exif.putdata(data)
#     no_exif.save(output_path)
#     return


def insert_pg(sql):
    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        with conn:
            with conn.cursor() as curs:
                curs.execute(sql)
        conn.commit()

def clean_and_resize(img):

    image = Image.open(img)
    width, height = image.size

    w, h = int(width/7), int(height/7)
    image = image.resize((w,h), Image.ANTIALIAS)

    data = list(image.getdata())

    no_exif = Image.new(image.mode, image.size)
    no_exif.putdata(data)

    newpath = img.replace("raw","ready").replace(img.split("/")[-1], "clean_"+img.split("/")[-1])

    no_exif.save(newpath)

    # return orientation, image
    return image


if __name__ == "__main__":
    
    while True:
    
    # print("Dude, suh!!!!")
        sleep(5)

# docker
        raw_img_dir = "/data/raw"
        clean_dir = "/data/ready"

# local
    # raw_img_dir = "/home/ubuntu/workbench/roadtrip-gate/data/raw"
    # clean_dir = "/home/ubuntu/workbench/roadtrip-gate/data/ready"

        images = list(set(glob(os.path.join(raw_img_dir, "*.JPG")) + glob(os.path.join(raw_img_dir, "*.jpg"))))

        for img in images:

            exif = get_exif(img)
            metadata = get_labeled_exif(exif)

            try:

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
                print(clean_dir, clean_filename)

                if not os.path.exists(output_img_path):

                    final_img = clean_and_resize(img)

                    orientation = 'P'

                    # clean_img(img, output_img_path)

                    insert_sql = f"""
                    INSERT INTO roadtrip.images VALUES (
                        '{guid}',
                        '{clean_filename}',
                        TO_TIMESTAMP('{date_taken}', 'YYYY:MM:DD HH24:MI:SS')::timestamp,
                        ST_SetSRID(ST_Point({lon}, {lat}), 4326),
                        '{orientation}'
                    )
                    ON CONFLICT (guid) DO UPDATE SET
                        file_name = EXCLUDED.file_name,
                        date_taken = EXCLUDED.date_taken,
                        geom = EXCLUDED.geom,
                        orientation = EXCLUDED.orientation
                    ;
                    """

                    insert_pg(insert_sql)
            
            except ValueError:
                pass
