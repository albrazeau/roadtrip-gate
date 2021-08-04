from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os.path
import base64
import email
from email.mime.text import MIMEText
# from bs4 import BeautifulSoup
# import html2text
from geopy.geocoders import Nominatim
from headers import GEOPY_USRNAME, VALID_EMAILS
import re
from pipeline import get_exif, get_coordinates, get_geotagging, get_labeled_exif

def extractEmail(text:str):
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    if match:
        return match.group(0)


# Define the SCOPES. If modifying it, delete the token.pickle file.
SCOPES = ['https://mail.google.com/',
'https://www.googleapis.com/auth/gmail.modify',
'https://www.googleapis.com/auth/gmail.readonly']

if os.path.exists('token.pickle'):

    # Read the token from the file and store it in the variable creds
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)

service = build('gmail', 'v1', credentials=creds)

# request a list of all the messages
result = service.users().messages().list(userId='me').execute()

# We can also pass maxResults to get any number of emails. Like this:
# result = service.users().messages().list(maxResults=200, userId='me').execute()
messages = result.get('messages')

image_dictionary = {}

# iterate through all the messages
for msg in messages:

    msg_content = service.users().messages().get(userId='me', id=msg['id']).execute()
    photo_information = {}
    n = 1

    # extract subject and validate sender 
    for element in msg_content['payload']['headers']:
        print(element)
        if element['name'] == 'Subject':
            location, caption = element['value'].split(";")
            photo_information['Location'] = location
            photo_information['Caption'] = caption

        if element['name'] == 'From' and extractEmail(element['value']) in VALID_EMAILS:
            photo_information['Valid'] = True

    for part in msg_content['payload']['parts']:
        if 'attachmentId' in part['body'].keys():
            # print(part['body']['attachmentId'])

            if msg['id'] in image_dictionary.keys():
                image_dictionary[msg['id']]['Attachments'].append(part['body']['attachmentId'])
            else:
                photo_information['Attachments'] = []
                photo_information['Attachments'].append(part['body']['attachmentId'])
                image_dictionary[msg['id']] = photo_information

    for k, v in image_dictionary.items():
        n = 1

        path = '/home/ubuntu/workbench/roadtrip-gate/data/raw'

        for ea_img in v['Attachments']:
            attachmentObj = service.users().messages().attachments().get(
                    userId='me', 
                    messageId=k,
                    id=ea_img
                    ).execute()

            path = os.path.join(path, f"{v['Location']}.JPG")
            print(path)

            

def imageFromBytes(byte_string: str, image_path):

    attachment = base64.urlsafe_b64decode(
                byte_string
                )

    if not os.path.exists(image_path):
        with open(image_path, "wb") as f:
            f.write(attachment)

def loadDatabase(imagepath, image_data):

    exif = get_exif(img)
    metadata = get_labeled_exif(exif)
    geotags = get_geotagging(exif)
    lat, lon = get_coordinates(geotags)

    if not lat and lon:
        location = add_geolocation(v['Location'])
        print("didn't work")

        if not location:
            # Send email that this didn't work
        



    print(geotags, lat, lon)

            clean_filename = f"clean_{os.path.basename(v['Caption'])}{n}"

            output_img_path = os.path.join(clean_dir, clean_filename)

            if not os.path.exists(output_img_path):
                with open(output_img_path, "wb") as f:
                    f.write(attachment)

        if add_geolocation(v['Location']):
            print(v['Location'])
            print(add_geolocation(v['Location']))
        else:
            ### Send email saying there was an error
            pass


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


def add_geolocation(city_and_state: str) -> tuple:

    geolocator = Nominatim(user_agent=GEOPY_USRNAME)
    location = geolocator.geocode(city_and_state)

    if location:
        return (location.latitude, location.longitude)
        
    else:
        return None


# docker
        raw_img_dir = "/data/raw"
        clean_dir = "/data/ready"

# local
    # raw_img_dir = "/home/ubuntu/workbench/roadtrip-gate/data/raw"
    # clean_dir = "/home/ubuntu/workbench/roadtrip-gate/data/ready"