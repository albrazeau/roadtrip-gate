from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os.path
import base64
import email
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
# from headers import GEOPY_USRNAME


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
    
    if 'beepthisjeep' in msg_content['snippet'].lower().replace(" ",""):
        photo_information = {}

        for part in msg_content['payload']['parts']:
            if 'attachmentId' in part['body'].keys():

                for element in msg_content['payload']['headers']:
                    if element['name'] == 'Subject':
                        
                        photo_information['location'] = element['value'].split(";")[0]
                        photo_information['caption'] = element['value'].split(";")[-1]

                    if element['name'] == 'From':
                        photo_information['sender'] = element['value']

                photo_information['attachmentId'] = part['body']['attachmentId']

            if msg['id'] in image_dictionary.keys():
                image_dictionary[msg['id']].append(photo_information)
            else:
                image_dictionary[msg['id']] = [photo_information]
    

for k, v in image_dictionary.items():

    attachmentObj = service.users().messages().attachments().get(
                    userId='me', 
                    messageId=k,
                    id=v['attachmentId']
                    ).execute()


            # pipeline_fields = extractMessageBody(msg_body)

            # if pipeline_fields['Valid'] == True:

            #     attachmentObj = service.users().messages().attachments().get(
            #                     userId=userId, 
            #                     messageId=msg['id'],
            #                     id=part['body']['attachmentId']
            #                     ).execute()

            #     attachment = base64.urlsafe_b64decode(
            #         attachmentObj["data"]
            #         )

            #     photo_filepath = f"./data/raw/{subject}_{n}.JPG"


def add_geolocation(city_and_state: str) -> tuple:

    geolocator = Nominatim(user_agent='test')
    location = geolocator.geocode(city_and_state)

    if location:
        return location.latitude, location.longitude
        
    else:
        return "No location data found.", None