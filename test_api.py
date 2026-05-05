import os
import requests

TOKEN = os.environ.get("FC_FOOTBALL_DATA_TOKEN")

url = "https://api.football-data.org/v4/competitions"
headers = {
    "X-Auth-Token": TOKEN
}

response = requests.get(url, headers=headers)

print("Status:", response.status_code)
print("Response:", response.text[:300])





