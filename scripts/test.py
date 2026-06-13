import requests

phone = "919625138140"
apikey = "YOUR_API_KEY"

message = "AI Job Agent: 3 New Jobs Found"

url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={message}&apikey={apikey}"

requests.get(url)