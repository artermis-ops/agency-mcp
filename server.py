import os, json, requests, datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = FastAPI(title="Your Agency MCP — Gmail + Calendar Live")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Load client config (the only file you change per client)
with open("client_config.json") as f:
    config = json.load(f)

# Google OAuth scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events"
]

def get_google_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds), build("calendar", "v3", credentials=creds)

gmail_service, calendar_service = get_google_service()

TOOLS = [
    {"name":"get_current_weather","description":"Get real-time weather","inputSchema":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}},
    {"name":"list_emails","description":"List recent emails","inputSchema":{"type":"object","properties":{"limit":{"type":"integer","default":10}},"required":[]}},
    {"name":"read_email","description":"Read full email by ID","inputSchema":{"type":"object","properties":{"email_id":{"type":"string"}},"required":["email_id"]}},
    {"name":"send_email","description":"Send email","inputSchema":{"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}},
    {"name":"classify_lead","description":"Classify email as Hot/Warm/Cold","inputSchema":{"type":"object","properties":{"email_body":{"type":"string"}},"required":["email_body"]}},
    {"name":"create_calendar_event","description":"Book a meeting","inputSchema":{"type":"object","properties":{"title":{"type":"string"},"date":{"type":"string"},"time":{"type":"string"},"duration_minutes":{"type":"integer","default":30}},"required":["title","date","time"]}}
]

@app.api_route("/v1", methods=["GET", "POST"])
async def root(request: Request):
    return {"tools": TOOLS}

# 1. Weather (unchanged)
class WeatherInput(BaseModel): city: str
@app.post("/v1/tools/get_current_weather")
async def get_current_weather(input: WeatherInput):
    data = requests.get(f"https://wttr.in/{input.city}?format=j1", timeout=5).json()
    temp = data["current_condition"][0]["temp_C"]
    desc = data["current_condition"][0]["weatherDesc"][0]["value"]
    return {"temperature_c": temp, "description": desc}

# 2. List recent emails
class ListInput(BaseModel): limit: int = 10
@app.post("/v1/tools/list_emails")
async def list_emails(input: ListInput):
    results = gmail_service.users().messages().list(userId="me", maxResults=input.limit).execute()
    messages = results.get('messages', [])
    emails = []
    for msg in messages:
        msg_data = gmail_service.users().messages().get(userId="me", id=msg['id']).execute()
        payload = msg_data['payload']
        headers = payload['headers']
        subject = next(h['value'] for h in headers if h['name'] == 'Subject')
        sender = next(h['value'] for h in headers if h['name'] == 'From')
        emails.append({"id": msg['id'], "subject": subject, "from": sender})
    return {"emails": emails}

# 3. Read full email
class ReadInput(BaseModel): email_id: str
@app.post("/v1/tools/read_email")
async def read_email(input: ReadInput):
    msg = gmail_service.users().messages().get(userId="me", id=input.email_id, format='full').execute()
    # Simplified extraction
    payload = msg['payload']
    body = payload.get("body", {}).get("data", "No body")
    return {"body": body, "snippet": msg['snippet']}

# 4. Send email
class SendInput(BaseModel): to: str; subject: str; body: str
@app.post("/v1/tools/send_email")
async def send_email(input: SendInput):
    from email.mime.text import MIMEText
    import base64
    message = MIMEText(input.body)
    message['to'] = input.to
    message['from'] = "me"
    message['subject'] = input.subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    gmail_service.users().messages().send(userId="me", body={'raw': raw}).execute()
    return {"status": "sent"}

# 5. Classify lead (simple AI-free version — you can plug Grok/Claude later)
class ClassifyInput(BaseModel): email_body: str
@app.post("/v1/tools/classify_lead")
async def classify_lead(input: ClassifyInput):
    text = input.email_body.lower()
    if any(word in text for word in ["urgent", "asap", "call me", "interested"]):
        return {"classification": "Hot", "confidence": 0.9}
    elif any(word in text for word in ["maybe", "later", "price"]):
        return {"classification": "Warm", "confidence": 0.7}
    else:
        return {"classification": "Cold", "confidence": 0.8}

# 6. Book calendar event
class EventInput(BaseModel): title: str; date: str; time: str; duration_minutes: int = 30
@app.post("/v1/tools/create_calendar_event")
async def create_event(input: EventInput):
    start_str = f"{input.date}T{input.time}:00"
    end_str = (datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00")) + datetime.timedelta(minutes=input.duration_minutes)).isoformat()
    event = {
        'summary': input.title,
        'start': {'dateTime': start_str, 'timeZone': 'Europe/London'},
        'end': {'dateTime': end_str, 'timeZone': 'Europe/London'},
    }
    event = calendar_service.events().insert(calendarId='primary', body=event).execute()
    return {"event_link": event.get('htmlLink'), "status": "booked"}

# Render port fix
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
