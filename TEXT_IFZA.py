import requests

url = "https://one.ifza.com/api/utils/getBusinessActivities"

response = requests.get(url)

print(response.status_code)
print(response.text[:500])