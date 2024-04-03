import json
import requests
import threading
import time
import pymongo
from datetime import datetime
import seaborn as sns
import matplotlib.pyplot as plt
import folium
from selenium import webdriver
# Load configuration
with open("config.json", "r") as f:
    config = json.load(f)

API_KEY = config["api_key"]
API_NAME = config["api_name"]
LOCATIONS = config["locations"]
REFRESH_FREQUENCY = config["refresh_frequency"]
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["weather_data"]
dbs=client["forecast_data"]
unique_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
min_temperature = 2 # def farenheit

# Function to fetch 5-day/3-hour forecast
def fetch_forecast(location):
    api_url = f"https://api.openweathermap.org/data/2.5/forecast?q={location}&appid={API_KEY}"
    response = requests.get(api_url)
    data = response.json()
    print(f"Forecast for {location}: {data}")    
    collection = dbs[location]
    collection.insert_one({"_id": unique_id, "location": location, "data": data})
    

# Function to fetch weather maps
def fetch_weather_maps(location):
    api_url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={API_KEY}"
    response = requests.get(api_url)
    data = response.json()
    print(f"Weather map for {location}: {data}")
    collection = db[location]    
    # unique_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    collection.insert_one({"_id": unique_id, "location": location, "data": data})

def findAlerts(location):        
    alerts = {"rain":set(),"snow":set(),"min_temperature":set()}
    collection=dbs[location]
    forecasts = collection.find({"location": location})
    for forecast_data in forecasts:
        forecast = forecast_data["data"]
        for forecast in forecast["list"]:
        # Converting temperature to Fahrenheit
            temperature = (float(forecast["main"]["temp"]) - 273.15)*(9/5)+32 
            if temperature<min_temperature:
                alerts["min_temperature"].add("Freezing temperature "+ temperature +" in "+location+" on "+str(forecast["dt_txt"]).split(" ")[0]+" at "+str(forecast["dt_txt"]).split(" ")[1])            
            elif forecast["weather"][0]["main"]=="Rain":
                alerts["rain"].add("Rain expected in "+location+" on "+str(forecast["dt_txt"]).split(" ")[0]+" at "+str(forecast["dt_txt"]).split(" ")[1])
            elif forecast["weather"][0]["main"]=="Snow":
                alerts["snow"].add("Snow expected in "+location+" on "+str(forecast["dt_txt"]).split(" ")[0]+" at "+str(forecast["dt_txt"]).split(" ")[1])
    for _,alert_items in alerts.items():
        for alert in alert_items:
            print(alert)

def plot_data(location):  
    collection=db[location]
    last_document = collection.find_one(sort=[('_id', -1)])
    latitude=last_document["data"]["coord"]["lat"]
    longitude=last_document['data']['coord']['lon']
    map_center = [latitude, longitude]
    weather=last_document['data']['weather'][0]['description']
    temperature=last_document['data']['main']['temp']
    windspeed=last_document['data']['wind']['speed']
    windDegree=last_document['data']['wind']['deg']
    m = folium.Map(location=map_center, zoom_start=10)
    # Add marker with weather description
    popup_text = f"Latitude: {latitude}<br>Longitude: {longitude}<br> Location: {location}<br>Weather: {weather}<br> temperature: {temperature} Kelvin <br> Wind Speed and Degree : {windspeed} and {windDegree}"
    popup = folium.Popup(popup_text, max_width=400)
    folium.Marker(location=map_center, popup=popup, tooltip="Click for weather").add_to(m)
    m.save(f"{location}_weather_map.html")
   
def plot_earlier_graphs(location):
    collection=dbs[location]
    current_time = datetime.now()
    forecasts = collection.find({"location": location})
    temp_data=[]
    for forecast_data in forecasts:
        forecast = forecast_data["data"]
        for forecast in forecast["list"]:
            dt_txt = datetime.strptime(forecast["dt_txt"], "%Y-%m-%d %H:%M:%S")
            time_difference = current_time - dt_txt
            if abs(time_difference.days)<10 :
                temp_data.append((forecast["dt_txt"],forecast["main"]["temp"]))
    temp_data.sort(key=lambda x: x[0])
    
    x = [entry[0] for entry in temp_data]
    y = [entry[1] for entry in temp_data]

    plt.figure(figsize=(10, 6))
    plt.plot(x, y, marker='o', linestyle='-')
    plt.title(f'Temperature Forecast for {location}')
    plt.xlabel('Date and Time')
    plt.ylabel('Temperature in Kelvin')
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    filename = f"temperature_graph_for_{location}.jpg"
    plt.savefig(filename, format='jpg')

# Create and start threads
threads = []
for location in LOCATIONS:
    forecast_thread = threading.Thread(target=fetch_forecast, args=(location,))
    map_thread = threading.Thread(target=fetch_weather_maps, args=(location,))
    plot_thread = threading.Thread(target=plot_data, args=(location,))
    find_alerts_thread = threading.Thread(target=findAlerts, args=(location,))
    
    # Start forecast and map threads
    forecast_thread.start()
    map_thread.start()
    
    # Join forecast and map threads to wait for completion
    forecast_thread.join()
    map_thread.join()
   
    threads.append(plot_thread)
    threads.append(find_alerts_thread)

# Start and wait for plotting and alerts threads
for thread in threads:
    thread.start()

for thread in threads:
    thread.join()

for location in LOCATIONS:
    plot_earlier_graphs(location)
