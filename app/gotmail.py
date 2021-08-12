from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import folium
from folium import IFrame
import folium.plugins as plugins

from PIL import ImageFile, Image
ImageFile.LOAD_TRUNCATED_IMAGES = True
from PIL.ExifTags import TAGS
from PIL.ExifTags import GPSTAGS

from contextlib import closing
import os.path
import base64
import re
import psycopg2
import random
import pandas as pd
from glob import glob
import logging

from headers import GEOPY_USRNAME, VALID_EMAILS, DB_CONNECTION_DOCKER, DB_CONNECTION_LOCAL
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

def resize_and_save(old_filepath, new_filepath, m_data):

    image = Image.open(old_filepath)

    if m_data.get('Orientation') == 3:
        image=image.rotate(180, expand=True)
    elif m_data.get('Orientation') == 6:
        image=image.rotate(270, expand=True)
    elif m_data.get('Orientation') == 8:
        image=image.rotate(90, expand=True)

    width, height = image.size

    if width >= height:
        w = 292
        h = 219

    if height >= width:
        w = 219
        h = 292

    image = image.resize((w,h), Image.ANTIALIAS)

    data = list(image.getdata())

    no_exif = Image.new(image.mode, image.size)
    no_exif.putdata(data)

    no_exif.save(new_filepath)
    os.remove(old_filepath)


def extractEmail(text:str):
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    if match:
        return match.group(0)

def add_geolocation(city_and_state: str) -> tuple:

    geolocator = Nominatim(user_agent=GEOPY_USRNAME)
    location = geolocator.geocode(city_and_state)

    if location:
        return (location.latitude, location.longitude)
        
    else:
        return (None, None)

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

def connectGmail(token = 'token.json'):
    
    print('Establishing connection to GMAIL.')

    # Define the SCOPES. If modifying it, delete the token.pickle file.
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

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
        
        check_content = f"""
                    SELECT email_id FROM roadtrip.images;
                    """

        with closing(psycopg2.connect(DB_CONNECTION)) as conn:
            with conn:
                df = pd.read_sql(check_content, conn)

            if not msg['id'] in df.email_id.to_list():

                msg_content = gmail_connection.users().messages().get(userId='me', id=msg['id']).execute()
                photo_information = {}
                n = 1

                if msg_content['snippet'] and 'date' in msg_content['snippet'].lower():
                    date = msg_content['snippet'].lower().split('date:')[1].split(';')[0].strip().title()
                    if not ":" in date:
                        date += ' 0:00 AM'
                    photo_information['Date'] = datetime.strptime(date.replace(",", ""), '%B %d %Y %H:%M %p')



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

                if "'" in caption and caption.count("'")%2:
                    idx = caption.index("'")
                    caption = caption[:idx] + "'" + caption[idx:]

                if "'" in photo_location and photo_location.count("'")%2:
                    idx = photo_location.index("'")
                    photo_location = photo_location[:idx] + "'" + photo_location[idx:]

                exif = get_exif(filepath)
                metadata = get_labeled_exif(exif)

                try:
                    geotags = get_geotagging(exif)
                    lat, lon = get_coordinates(geotags)
                    date_taken = metadata["DateTimeOriginal"]
                
                except:
                    lat, lon = add_geolocation(photo_location)
                    date_taken = message_value.get('Date', datetime.now())

                if not lat and not lon:
                    lon, lat = DEFAULT_GEO
                    resize_and_save(filepath, filepath.replace("raw", "nogeodata"), metadata)
                    insertImg(attachment_ID, email_id, photo_location, caption, filepath.replace("raw", "nogeodata"), date_taken, lat, lon)

                if lat and lon:
                    resize_and_save(filepath, filepath.replace("raw", "ready"), metadata)
                    insertImg(attachment_ID, email_id, photo_location, caption, filepath.replace("raw", "ready"), date_taken, lat, lon)

def generateMap():

    US_CENTER = ('39.009734', '-97.555620')

    fetch_sql = f"""SELECT
                        attachment_id,
                        filepath,
                        caption,
                        date_taken,
                        ST_X(geom) AS lon_x,
                        ST_Y(geom) AS lat_y
                    FROM
                        roadtrip.images;"""

    with closing(psycopg2.connect(DB_CONNECTION)) as conn:
        df = pd.read_sql(fetch_sql, conn)

    folium_map = folium.Map(location=US_CENTER, 
    zoom_start=4, scrollWheelZoom=False, tiles=None)

    folium_map.add_child(plugins.Geocoder())
    folium.TileLayer('openstreetmap', name = 'Street').add_to(folium_map)
    folium.TileLayer('Stamen Terrain', name = 'Terrain').add_to(folium_map)
    folium.TileLayer(
        tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr = 'Esri',
        name = 'Satellite'
    ).add_to(folium_map)
    folium.LayerControl().add_to(folium_map)
    folium_map.add_child(plugins.Fullscreen(position='topleft', title='Full Screen', title_cancel='Exit Full Screen', force_separate_button=False))

    for idx in range(len(df)):

        img_name = df.iloc[idx]['caption']
        filepath = df.iloc[idx]['filepath']
        lon = df.iloc[idx]['lon_x']
        lat = df.iloc[idx]['lat_y']

        # resize appropriately
        image = Image.open(filepath)
        width, height = image.size
        width = width + 25
        height = height + 25

        # nesting the image loading and route mapping to a try except-- top candidate for future refactor

        try:

            encoded = base64.b64encode(open(filepath, 'rb').read())
            html = '<img src="data:image/JPG;base64,{}">'.format(encoded.decode("UTF-8"))
            
            iframe = IFrame(html, width=width, height=height)

            popup = folium.Popup(iframe, max_width=width+25)
            tooltip = img_name.replace("_"," ")
        
            folium.Marker(location=(lat, lon), tooltip=tooltip, popup=popup, icon=folium.Icon(color='blue')).add_to(folium_map)

        except:
            pass

    # try:
    #     draw_line = list(df.sort_values(by='date_taken')[['lat_y', 'lon_x']].apply(tuple, axis=1))
    #     folium.PolyLine(draw_line, color="#c20dff", weight=2.5, opacity=1).add_to(folium_map)
    # except:
    #     pass

    folium_map.save('templates/map.html')

if __name__ == "__main__":

    print("Starting: Generating default map")
    sleep(60)
    generateMap()

    while True:

        try:
            print("Begin data pull from Gmail")
            server = connectGmail()
            img_dict = fetchEmailData(server)
            loadRawImages(img_dict, server)
            generateMap()
            print("Data pull successful")

        except Exception as e:
            logging.error("This is the error: %s", e, exc_info=1)
            print(e)

        print("Sleeping")
        sleep(60*60*4)