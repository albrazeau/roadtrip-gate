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
        sender = ''

        for part in msg_content['payload']['parts']:
            if 'attachmentId' in part['body'].keys():

                n = 1

                for element in msg_content['payload']['headers']:
                    if element['name'] == 'Subject':
                        subject = element['value']
                    if element['name'] == 'From':
                        sender = element['value']
                
                msg_body = msg_content['snippet']
                attachmentId = part['body']['attachmentId']

                pipeline_fields = extractMessageBody(msg_body)

                if pipeline_fields['Valid'] == True:

                    attachmentObj = service.users().messages().attachments().get(
                                    userId=userId, 
                                    messageId=msg['id']
                                    id=part['body']['attachmentId']
                                    ).execute()

                    attachment = base64.urlsafe_b64decode(
                        attachmentObj["data"]
                        )

                    photo_filepath = f"./data/raw/{subject}_{n}.JPG"

                    with open(photo_filepath, "wb") as f:
                        f.write(attachment)

                    return photo_filepath, pipeline_fields

def extractMessageBody(msg_body):

    msg_body = msg_body.lower().split(",")
    fields = {
        'Location':'',
        'Caption':'',
        'Valid': False
    }

    if 'beepthisjeep' in msg_body.replace(" ",""):
        fields['Valid'] = True

    for msg in msg_body:
        if 'location' in msg:
            fields['Location'] = msg.replace('location','').capitalize().strip()
        if 'caption' in msg:
            fields['Caption'] = msg.replace('caption','').capitalize().strip()
    
    return fields

def generateResponse(sender, to, subject, message_text):
    """Create a message for an email.

    Args:
        sender: Email address of the sender.
        to: Email address of the receiver.
        subject: The subject of the email message.
        message_text: The text of the email message.

    Returns:
        An object containing a base64url encoded email object.
    """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_string())}
    

def sendMessage(service, user_id, message):
  """Send an email message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

  Returns:
    Sent Message.
  """
  try:
    message = (service.users().messages().send(userId=user_id, body=message)
               .execute())
    print 'Message Id: %s' % message['id']
    return message
  except errors.HttpError, error:
    print 'An error occurred: %s' % error