from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from PIL import ImageFile, Image
ImageFile.LOAD_TRUNCATED_IMAGES = True
from PIL.ExifTags import TAGS
from PIL.ExifTags import GPSTAGS

from contextlib import closing
import pickle
import os.path
import base64
import re
import psycopg2
import random
import pandas as pd
from glob import glob
import logging

from headers import GEOPY_USRNAME, VALID_EMAILS, DB_CONNECTION_DOCKER, DB_CONNECTION_LOCAL
# from headers import GEOPY_USRNAME, VALID_EMAILS
from geopy.geocoders import Nominatim
from datetime import datetime
from time import sleep

from functools import partial

print = partial(print, flush=True)

# local
# DB_CONNECTION = DB_CONNECTION_LOCAL
# RAW_PATH = '/home/ubuntu/workbench/roadtrip-gate/data/raw'
# READY_PATH = '/home/ubuntu/workbench/roadtrip-gate/data/ready'

# docker
DB_CONNECTION = DB_CONNECTION_DOCKER
RAW_PATH = '/data/raw'
READY_PATH = '/data/ready'

DEFAULT_GEO = ('39.009734', '-97.555620')

logging.basicConfig(filename='/app/gotmail.log', level=logging.WARNING)

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


def insertImg(sql):
    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        with conn:
            with conn.cursor() as curs:
                curs.execute(sql)
        conn.commit()

def resize_and_save(old_filepath, new_filepath):

    image = Image.open(old_filepath)
    width, height = image.size

    w, h = int(width/7), int(height/7)
    image = image.resize((w,h), Image.ANTIALIAS)

    data = list(image.getdata())

    no_exif = Image.new(image.mode, image.size)
    no_exif.putdata(data)

    no_exif.save(new_filepath)


def extractEmail(text:str):
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    if match:
        return match.group(0)

# def imageFromBytes(byte_string: str, path, img_name):

#     pathway = os.path.join(path, img_name)

#     attachment = base64.urlsafe_b64decode(
#                 byte_string
#                 )

#     if not os.path.exists(pathway):
#         with open(pathway, "wb") as f:
#             f.write(attachment)
#             return None
    
#     return "Error translating image from bytes."

def add_geolocation(city_and_state: str) -> tuple:

    geolocator = Nominatim(user_agent=GEOPY_USRNAME)
    location = geolocator.geocode(city_and_state)

    if location:
        return (location.latitude, location.longitude)
        
    else:
        return None

def imgExists(img_id):

    check_img = f"""
                SELECT * FROM roadtrip.images WHERE attachment_id = '{img_id}';
                """

    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        with conn:
            exists = pd.read_sql(check_img, conn)

            if len(exists) >= 1:
                return True

    return False

def getImgData(img_path):

    check_img = f"""
                SELECT * FROM roadtrip.images WHERE filepath = '{img_path}';
                """

    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        with conn:
            df = pd.read_sql(check_img, conn)
            return df

    return False

def connectGmail(token = 'token.pickle'):
    
    print('Establishing connection to GMAIL.')

    # Define the SCOPES. If modifying it, delete the token.pickle file.
    SCOPES = ['https://mail.google.com/',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.readonly']

    if os.path.exists('token.pickle'):

        # Read the token from the file and store it in the variable creds
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    service = build('gmail', 'v1', credentials=creds)

    return service

def fetchEmailData(gmail_connection):

    # request a list of all the messages
    result = gmail_connection.users().messages().list(userId='me').execute()

    # can also pass maxResults to get any number of emails. Like this:
    # result = service.users().messages().list(maxResults=200, userId='me').execute()
    messages = result.get('messages')

    # object to hold valid image submission
    image_dictionary = {}

    # iterate through all the messages
    for msg in messages:

        msg_content = gmail_connection.users().messages().get(userId='me', id=msg['id']).execute()
        photo_information = {}
        n = 1

        if msg_content['snippet'] and 'date' in msg_content['snippet'].lower():
            date = msg_content['snippet'].lower().split('date:')[1].split(';')[0]
            photo_information['Date'] = datetime.strptime(date, '%d/%m/%Y')


        # parse message object to pull subject data and validate sender in payload HEADERS
        for element in msg_content['payload']['headers']:
            if element['name'] == 'Subject':
                if ';' in element['value']:
                    location, caption = element['value'].split(";")
                else:
                    location, caption = element['value'], element['value']
                photo_information['Location'] = location
                photo_information['Caption'] = caption

            if element['name'] == 'From' and extractEmail(element['value']) in VALID_EMAILS:
                photo_information['Valid'] = True

        # parse message oject for attachments in payload PARTS
        for part in msg_content['payload']['parts']:
            if 'attachmentId' in part['body'].keys():

                if msg['id'] in image_dictionary.keys():
                    image_dictionary[msg['id']]['Attachments'].append(part['body']['attachmentId'])
                else:
                    photo_information['Attachments'] = []
                    photo_information['Attachments'].append(part['body']['attachmentId'])
                    image_dictionary[msg['id']] = photo_information
            if 'filename' in part['body'].keys():
                print(part['body']['filename'])
    
    return image_dictionary



def insertImg(attachment_ID, email_id, photo_location, caption, filepath, date_taken, lat, lon):
    
    sql = f"""
    INSERT INTO roadtrip.images VALUES (
        '{attachment_ID}',
        '{email_id}',
        '{photo_location}',
        '{caption}',
        '{filepath}',
        TO_TIMESTAMP('{date_taken}', 'YYYY:MM:DD HH24:MI:SS')::timestamp,
        ST_SetSRID(ST_Point({lon}, {lat}), 4326)
    )
    """

    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        with conn:
            with conn.cursor() as curs:
                curs.execute(sql)
        conn.commit()

def loadRawImages(image_dictionary, service):

    for message_key, message_value in image_dictionary.items():
        n = 1

        for img_id in message_value['Attachments']:

            attachment_ID = img_id[:25]

            if not imgExists(attachment_ID):

                print('Processing Image- loading to raw folder.')

                attachmentObj = service.users().messages().attachments().get(
                        userId='me', 
                        messageId=message_key,
                        id=img_id
                        ).execute()

                img_name = re.sub("[^a-zA-Z]+", "", attachment_ID) + '.JPG'

                filepath = os.path.join(RAW_PATH, img_name)

                attachmentImg = base64.urlsafe_b64decode(
                    attachmentObj['data']
                    )
                if not os.path.exists(filepath):
                    with open(filepath, "wb") as f:
                        f.write(attachmentImg)

                # establish variables to be fed into sql insertion func
                email_id = message_key
                photo_location = message_value.get('Location', None)
                caption = message_value.get('Caption', None)
                filepath = filepath
                date_taken = message_value.get('Date', datetime.now())

                if "'" in caption and caption.count("'")%2:
                    idx = caption.index("'")
                    caption = caption[:idx] + "'" + caption[idx:]

                if "'" in photo_location and photo_location.count("'")%2:
                    idx = photo_location.index("'")
                    photo_location = photo_location[:idx] + "'" + photo_location[idx:]

                try:
                    exif = get_exif(filepath)
                    metadata = get_labeled_exif(exif)
                    geotags = get_geotagging(exif)
                    lat, lon = get_coordinates(geotags)
                    date_taken = metadata["DateTimeOriginal"]
                
                except:
                    lat, lon = add_geolocation(photo_location)

                if not lat and not lon:
                    lon, lat = DEFAULT_GEO
                    insertImg(attachment_ID, email_id, photo_location, caption, filepath.replace("raw", "nogeodata"), date_taken, lat, lon)
                    resize_and_save(filepath, filepath.replace("raw", "nogeodata"))

                if lat and lon:
                    insertImg(attachment_ID, email_id, photo_location, caption, filepath.replace("raw", "ready"), date_taken, lat, lon)
                    resize_and_save(filepath, filepath.replace("raw", "ready"))

# def processRawImages():

#     raw_images = list(set(glob(os.path.join(RAW_PATH, "*.JPG")) + glob(os.path.join(RAW_PATH, "*.jpg"))))
#     ready_images = list(set(glob(os.path.join(READY_PATH, "*.JPG")) + glob(os.path.join(READY_PATH, "*.jpg"))))

#     for ea_img in raw_images:

#         if not ea_img.replace("raw", "ready") in ready_images:

#             df = getImgData(ea_img)

#             for ea in range(len(df)):
#                 attachment_id = df.iloc[ea]['attachment_id']
#                 email_id = df.iloc[ea]['email_id']
#                 photo_location = df.iloc[ea]['photo_location']
#                 caption = df.iloc[ea]['caption']
#                 date_taken = df.iloc[ea]['date_taken']


                # try:
                #     exif = get_exif(ea_img)
                #     metadata = get_labeled_exif(exif)
                #     geotags = get_geotagging(exif)
                #     lat, lon = get_coordinates(geotags)
                #     date_taken = metadata["DateTimeOriginal"]

                # except:
                #     lat, lon = add_geolocation(photo_location)

                # if not lat and not lon:
                #     lat, lon = None, None
                #     clean_resize_insert(ea_img, attachment_id, date_taken, lat, lon)
                
                
                # else:

                #     clean_resize_insert(ea_img, attachment_id, date_taken, lat, lon)

# def dataPipeline(image_dictionary):

#     for k, v in image_dictionary.items():
#         n = 1

#         for ea_img in v['Attachments']:

#             print('Processing image')

#             attachmentObj = service.users().messages().attachments().get(
#                     userId='me', 
#                     messageId=k,
#                     id=ea_img
#                     ).execute()
            
#             img_name = re.sub("[^a-zA-Z]+", "", f"{v['Caption']}") + f'_{n}.JPG'
#             n+= 1

#             # load image into RAW DATA FOLDER 
#             # returns NONE if there is no pipeline error
#             pipeline_error = imageFromBytes(attachmentObj['data'], RAW_PATH, img_name)

#             if pipeline_error:
#                 # CALL FUNCTION TO SEND EMAIL THAT THERE WAS AN ISSUE
#                 # break
#                 pass
#             if not pipeline_error:

#                 pathway = os.path.join(RAW_PATH, img_name)

#                 try:
#                     exif = get_exif(pathway)
#                     metadata = get_labeled_exif(exif)
#                     geotags = get_geotagging(exif)
#                     lat, lon = get_coordinates(geotags)

#                 except:
#                     exif = get_exif(pathway)
#                     metadata = get_labeled_exif(exif)
#                     location = add_geolocation(v['Location'])
#                     if not location:
#                         # CALL FUNCTION TO SEND EMAIL THERE WAS AN ISSUE
#                         pass
                    
#                     lat, lon = location

#                 try:
#                     date_taken = metadata["DateTimeOriginal"]
#                 except:
#                     date_taken = datetime.now().strftime("%Y:%m:%d")
#                 guid_num = (
#                     float(metadata.get("ApertureValue", random.randint(1, 200))) *
#                     float(metadata.get('BrightnessValue', random.randint(1, 200)))*
#                     float(metadata.get('ExposureTime', random.randint(1, 200)))
#                     * lat
#                     * lon
#                 )
#                 guid = f"{guid_num}_{date_taken}"

#                 final_path = os.path.join(ready_path, img_name)

#                 print(f'Final image ready for saving. Final path: ', final_path)
                    
#                 final_img = clean_and_resize(final_path)

#                 if "'" in v['Caption'] and v['Caption'].count("'")%2:
#                     idx = v['Caption'].index("'")
#                     v['Caption'] = v['Caption'][:idx] + "'" + v['Caption'][idx:]
#                     print(v['Caption'])

#                 insert_sql = f"""
#                         INSERT INTO roadtrip.images VALUES (
#                             '{guid}',
#                             '{k}',
#                             '{final_path.split('/')[-1]}',
#                             TO_TIMESTAMP('{date_taken}', 'YYYY:MM:DD HH24:MI:SS')::timestamp,
#                             ST_SetSRID(ST_Point({lon}, {lat}), 4326),
#                             '{v['Caption']}'
#                         )
#                         ON CONFLICT (guid) DO UPDATE SET
#                             email_id = EXCLUDED.email_id,
#                             file_name = EXCLUDED.file_name,
#                             date_taken = EXCLUDED.date_taken,
#                             geom = EXCLUDED.geom,
#                             caption = EXCLUDED.caption
#                         ;
#                         """

#                 insert_pg(insert_sql)

#                 print("Completed. ", final_path)




if __name__ == "__main__":

    try:
    
        print("Starting")
        while True:

            server = connectGmail()
            img_dict = fetchEmailData(server)
            loadRawImages(img_dict, server)

            print("Sleeping")
            sleep(60)
    
    except Exception as e:
        logging.error("This is the error: %s", e, exc_info=1)
        raise e