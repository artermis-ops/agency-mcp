from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import uvicorn, json, os, requests, datetime

app = FastAPI(title="Your Agency MCP — Multi-Client Edition")

# Load client config (this is the ONLY file that changes per client)
CONFIG_FILE = "client_config.json"
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError("Create client_config.json first!")

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

TOOLS = [
    {"name": "get_current_weather", "description": "Get real-time weather for any city", "inputSchema": {"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}},
    {"name": "list_emails", "description": "List recent emails from Gmail inbox", "inputSchema": {"type":"object","properties":{"limit":{"type":"integer"}},"required":["limit"]}},
    {"name": "read_email", "description": "Read a specific email by ID", "inputSchema": {"type":"object","properties":{"email_id":{"type":"string"}},"required":["email_id"]}},
    {"name": "send_email", "description": "Send an email reply", "inputSchema": {"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}},
    {"name": "create_calendar_event", "description": "Book a meeting on Google Calendar", "inputSchema": {"type":"object","properties":{"title":{"type":"string"},"start_time":{"type":"string"},"duration_minutes":{"type":"integer"}},"required":["title","start_time"]}},
]

@app.api_route("/v1", methods=["GET", "POST"])
async def root(request: Request):
    return {"tools": TOOLS}

class WeatherInput(BaseModel): city: str
@app.post("/v1/tools/get_current_weather")
async def get_current_weather(input: WeatherInput):
    url = f"https://wttr.in/{input.city}?format=j1"
    data = requests.get(url, timeout=5).json()
    temp = data["current_condition"][0]["temp_C"]
    desc = data["current_condition"][0]["weatherDesc"][0]["value"]
    return {"temperature_c": temp, "description": desc}

class ListEmails(BaseModel): limit: int = 10
@app.post("/v1/tools/list_emails")
async def list_emails(input: ListEmails):
    # Placeholder — you’ll plug real Gmail API here later
    return {"emails": [{"id": "123", "subject": "Demo lead", "from": "client@example.com"}]}

# Add more tools here later (read_email, send_email, calendar, etc.)

if __name__ == "__main__":
    print(f"Agency MCP ready for client: {config.get('company_name', 'Unknown')}")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
