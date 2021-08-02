from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os.path
import base64
import email
from bs4 import BeautifulSoup
  
# Define the SCOPES. If modifying it, delete the token.pickle file.
SCOPES = ['https://mail.google.com/',
'https://www.googleapis.com/auth/gmail.modify',
'https://www.googleapis.com/auth/gmail.readonly']

def connectServer():
    # Variable creds will store the user access token.
    # If no valid token found, we will create one.
    creds = None
  
    # The file token.pickle contains the user access token.
    # Check if it exists
    if os.path.exists('token.pickle'):
  
        # Read the token from the file and store it in the variable creds
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            print(creds)

    # If credentials are not available or are invalid, ask the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
  
        # Save the access token in token.pickle file for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Connect to the Gmail API
    service = build('gmail', 'v1', credentials=creds)

    return service

def checkMessages(service, userId = 'me'):
  
    # request a list of all the messages
    result = service.users().messages().list(userId='me').execute()

    # We can also pass maxResults to get any number of emails. Like this:
    # result = service.users().messages().list(maxResults=200, userId='me').execute()
    messages = result.get('messages')
  
    # messages is a list of dictionaries where each dictionary contains a message id.
  
    # iterate through all the messages
    for msg in messages:

        msg_content = service.users().messages().get(userId=userId, id=msg['id']).execute()
        subject = ''

        for part in msg_content['payload']['parts']:
            if 'attachmentId' in part['body'].keys():

                n = 1

                for element in msg_content['payload']['headers']:
                    if element['name'] == 'Subject':
                        subject = element['value']
                
                msg_body = msg_content['snippet']
                attachmentId = part['body']['attachmentId']

                attachmentObj = service.users().messages().attachments().get(
                                userId=userId, 
                                messageId=msg['id'],
                                id=part['body']['attachmentId']
                                ).execute()

                attachment = base64.urlsafe_b64decode(
                    attachmentObj["data"]
                    )

                with open(f"{subject}_{n}.JPG", "wb") as f:
                    f.write(attachment)