import requests

url = "https://www.spcfz.ae/wp-json/spc/v1/activities"

r = requests.get(url)

print("Total Records:", r.headers.get("X-WP-Total"))
print("Total Pages:", r.headers.get("X-WP-TotalPages"))
print("Records Returned:", len(r.json()))