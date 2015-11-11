
import requests, json, yaml

URL = "https://query.yahooapis.com/v1/public/yql"
REQUEST = dict(
    q='select * from weather.forecast where woeid in (select woeid from geo.places(1) where text="Waiting, Chatham Islands, New Zealand") and u="c"',
    format='json',
    env='store://datatables.org/alltableswithkeys')

r = requests.get(URL, params=REQUEST)

weather = r.json()

with open("weather.json", 'w') as f:
    json.dump(weather, f)

