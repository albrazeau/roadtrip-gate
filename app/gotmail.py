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

# from headers import GEOPY_USRNAME, VALID_EMAILS, DB_CONNECTION_DOCKER, DB_CONNECTION_LOCAL
from headers import GEOPY_USRNAME, VALID_EMAILS
from geopy.geocoders import Nominatim
from datetime import datetime
from time import sleep

from functools import partial

print = partial(print, flush=True)

# local
# DB_CONNECTION = DB_CONNECTION_LOCAL

# docker
# DB_CONNECTION = DB_CONNECTION_DOCKER

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


def insert_pg(sql):
    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        with conn:
            with conn.cursor() as curs:
                curs.execute(sql)
        conn.commit()

def clean_and_resize(img):

    image = Image.open(img.replace("ready","raw"))
    width, height = image.size

    w, h = int(width/7), int(height/7)
    image = image.resize((w,h), Image.ANTIALIAS)

    data = list(image.getdata())

    no_exif = Image.new(image.mode, image.size)
    no_exif.putdata(data)

    no_exif.save(img)

    return image

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
    result = service.users().messages().list(userId='me').execute()

    # can also pass maxResults to get any number of emails. Like this:
    # result = service.users().messages().list(maxResults=200, userId='me').execute()
    messages = result.get('messages')

    # object to hold valid image submission
    image_dictionary = {}

    # iterate through all the messages
    for msg in messages:

        msg_content = service.users().messages().get(userId='me', id=msg['id']).execute()
        photo_information = {}
        n = 1

        if msg_content['snippet'] and 'date' in msg_content['snippet'].lower():
            date = msg_content['snippet'].lower().split('date:')[1].split(';')[0]
            photo_information['Date'] = date


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

def loadRawImages(image_dictionary, service):

    for message_key, message_value in image_dictionary.items():
        n = 1

        # LOCAL PATH
        raw_path = '/home/ubuntu/workbench/roadtrip-gate/data/raw'

        # IN DOCKER
        # raw_path = '/data/raw'

        for img_id in message_value['Attachments']:

            if not img_id in 

            print('Processing Image (loading to raw folder.')

            attachmentObj = service.users().messages().attachments().get(
                    userId='me', 
                    messageId=message_key,
                    id=img_id
                    ).execute()

            img_name = re.sub("[^a-zA-Z]+", "", img_id) + '.JPG'

            pathway = os.path.join(raw_path, img_name)

            attachmentImg = base64.urlsafe_b64decode(
                attachmentObj['data']
                )

            if not os.path.exists(pathway):
                with open(pathway, "wb") as f:
                    f.write(attachmentImg)


def dataPipeline(image_dictionary):

    for k, v in image_dictionary.items():
        n = 1

        # LOCAL PATH
        raw_path = '/home/ubuntu/workbench/roadtrip-gate/data/raw'
        ready_path = '/home/ubuntu/workbench/roadtrip-gate/data/ready'

        # IN DOCKER
        # raw_path = '/data/raw'
        # ready_path = '/data/ready'

        for ea_img in v['Attachments']:

            print('Processing image')

            attachmentObj = service.users().messages().attachments().get(
                    userId='me', 
                    messageId=k,
                    id=ea_img
                    ).execute()
            
            img_name = re.sub("[^a-zA-Z]+", "", f"{v['Caption']}") + f'_{n}.JPG'
            n+= 1

            # load image into RAW DATA FOLDER 
            # returns NONE if there is no pipeline error
            pipeline_error = imageFromBytes(attachmentObj['data'], raw_path, img_name)

            if pipeline_error:
                # CALL FUNCTION TO SEND EMAIL THAT THERE WAS AN ISSUE
                # break
                pass
            if not pipeline_error:

                pathway = os.path.join(raw_path, img_name)

                try:
                    exif = get_exif(pathway)
                    metadata = get_labeled_exif(exif)
                    geotags = get_geotagging(exif)
                    lat, lon = get_coordinates(geotags)

                except:
                    exif = get_exif(pathway)
                    metadata = get_labeled_exif(exif)
                    location = add_geolocation(v['Location'])
                    if not location:
                        # CALL FUNCTION TO SEND EMAIL THERE WAS AN ISSUE
                        pass
                    
                    lat, lon = location

                try:
                    date_taken = metadata["DateTimeOriginal"]
                except:
                    date_taken = datetime.now().strftime("%Y:%m:%d")
                guid_num = (
                    float(metadata.get("ApertureValue", random.randint(1, 200))) *
                    float(metadata.get('BrightnessValue', random.randint(1, 200)))*
                    float(metadata.get('ExposureTime', random.randint(1, 200)))
                    * lat
                    * lon
                )
                guid = f"{guid_num}_{date_taken}"

                final_path = os.path.join(ready_path, img_name)

                print(f'Final image ready for saving. Final path: ', final_path)
                    
                final_img = clean_and_resize(final_path)

                if "'" in v['Caption'] and v['Caption'].count("'")%2:
                    idx = v['Caption'].index("'")
                    v['Caption'] = v['Caption'][:idx] + "'" + v['Caption'][idx:]
                    print(v['Caption'])

                insert_sql = f"""
                        INSERT INTO roadtrip.images VALUES (
                            '{guid}',
                            '{k}',
                            '{final_path.split('/')[-1]}',
                            TO_TIMESTAMP('{date_taken}', 'YYYY:MM:DD HH24:MI:SS')::timestamp,
                            ST_SetSRID(ST_Point({lon}, {lat}), 4326),
                            '{v['Caption']}'
                        )
                        ON CONFLICT (guid) DO UPDATE SET
                            email_id = EXCLUDED.email_id,
                            file_name = EXCLUDED.file_name,
                            date_taken = EXCLUDED.date_taken,
                            geom = EXCLUDED.geom,
                            caption = EXCLUDED.caption
                        ;
                        """

                insert_pg(insert_sql)

                print("Completed. ", final_path)


def checkExists(img_id):

    check_img = f"""
                SELECT * FROM roadtrip.images WHERE attachment_id = {img_id};
                """

    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        with conn:
            exists = pd.read_sql(check_img, conn)

    if exists:
        return True
    return False

if __name__ == "__main__":
    
    print("Starting")
    while True:

        service = connectGmail()
        img_dict = fetchEmailData(service)
        dataPipeline(img_dict)

        print("Sleeping")
        sleep(60)