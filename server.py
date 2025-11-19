import os
import json
import requests
import datetime
import base64
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events"
]

def get_services():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token.json", "w") as f:
                f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds), build("calendar", "v3", credentials=creds)

gmail_service, calendar_service = get_services()

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# TOOL DEFINITIONS (this is the only part ChatGPT sees)
TOOLS = [
    {"name": "get_current_weather",      "description": "Get real-time weather", "inputSchema": {"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}},
    {"name": "list_emails",             "description": "List recent emails",    "inputSchema": {"type":"object","properties":{"limit":{"type":"integer"}},"required":[]}},
    {"name": "send_email",               "description": "Send an email",         "inputSchema": {"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}},
    {"name": "create_calendar_event",    "description": "Book a meeting",        "inputSchema": {"type":"object","properties":{"title":{"type":"string"},"date":{"type":"string"},"time":{"type":"string"}},"required":["title","date","time"]}}
]

@app.get("/v1")
@app.post("/v1")
def root():                     # ← no async, no Request → fixes the FastAPI error
    return {"tools": TOOLS}
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

class WeatherInput(BaseModel): city: str
@app.post("/v1/tools/get_current_weather")
def weather(input: WeatherInput):
    data = requests.get(f"https://wttr.in/{input.city}?format=j1").json()
    return {"temperature_c": data["current_condition"][0]["temp_C"], "description": data["current_condition"][0]["weatherDesc"][0]["value"]}

class ListInput(BaseModel): limit: int = 10
@app.post("/v1/tools/list_emails")
def list_emails(input: ListInput):
    results = gmail_service.users().messages().list(userId="me", maxResults=input.limit).execute()
    msgs = results.get("messages", [])
    emails = []
    for m in msgs:
        msg = gmail_service.users().messages().get(userId="me", id=m["id"]).execute()
        headers = msg["payload"]["headers"]
        subject = next((h["value"] for h in headers if h["name"]=="Subject"), "")
        sender  = next((h["value"] for h in headers if h["name"]=="From"), "")
        emails.append({"id": m["id"], "subject": subject, "from": sender})
    return {"emails": emails}

class SendInput(BaseModel): to: str ; subject: str ; body: str
@app.post("/v1/tools/send_email")
def send_email(input: SendInput):
    msg = MIMEText(input.body)
    msg["to"], msg["from"], msg["subject"] = input.to, "me", input.subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"status": "sent"}

class EventInput(BaseModel): title: str ; date: str ; time: str ; duration_minutes: int = 30
@app.post("/v1/tools/create_calendar_event")
def create_event(input: EventInput):
    start = f"{input.date}T{input.time}:00"
    end   = (datetime.datetime.fromisoformat(start) + datetime.timedelta(minutes=input.duration_minutes)).isoformat()
    event = {"summary": input.title, "start": {"dateTime": start, "timeZone": "Europe/London"}, "end": {"dateTime": end, "timeZone": "Europe/London"}}
    created = calendar_service.events().insert(calendarId="primary", body=event).execute()
    return {"link": created.get("htmlLink")}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

