import requests

# Session to maintain cookies
session = requests.Session()

# Login (replace with your credentials)
login_url = "https://www.instagram.com/accounts/login/ajax/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}
data = {
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD",
}
response = session.post(login_url, headers=headers, data=data)
print(response.json())  # Check if login was successful

# Fetch profile data
profile_url = "https://www.instagram.com/petrdvorak698/"
response = session.get(profile_url)
data = response.json()
print(data)