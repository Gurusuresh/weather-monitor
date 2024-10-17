import requests
import time
import schedule
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import smtplib
from email.mime.text import MIMEText
import matplotlib.pyplot as plt
from config import API_KEY, CITIES, INTERVAL, ALERT_TEMP_THRESHOLD, CONSECUTIVE_UPDATES_THRESHOLD, EMAIL, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD

Base = declarative_base()

# Database setup
engine = create_engine('sqlite:///weather.db')
Session = sessionmaker(bind=engine)
session = Session()

# WeatherData table
class WeatherData(Base):
    __tablename__ = 'weather_data'
    id = Column(Integer, primary_key=True)
    city = Column(String)
    temp = Column(Float)
    feels_like = Column(Float)
    weather_condition = Column(String)
    timestamp = Column(DateTime)

Base.metadata.create_all(engine)

# Email alert function
def send_alert(city, current_temp):
    msg = MIMEText(f"Alert! The temperature in {city} has exceeded {ALERT_TEMP_THRESHOLD}C.\nCurrent Temperature: {current_temp}C.")
    msg["Subject"] = f"Weather Alert for {city}"
    msg["From"] = SMTP_USERNAME
    msg["To"] = EMAIL

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, EMAIL, msg.as_string())
        print(f"Alert email sent for {city}.")

# Fetch and process weather data
def fetch_weather():
    for city in CITIES:
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}"
            response = requests.get(url)
            data = response.json()

            temp_kelvin = data["main"]["temp"]
            feels_like_kelvin = data["main"]["feels_like"]
            weather_condition = data["weather"][0]["main"]
            timestamp = datetime.utcfromtimestamp(data["dt"])

            temp_celsius = temp_kelvin - 273.15
            feels_like_celsius = feels_like_kelvin - 273.15

            # Save to database
            weather_entry = WeatherData(city=city, temp=temp_celsius, feels_like=feels_like_celsius, weather_condition=weather_condition, timestamp=timestamp)
            session.add(weather_entry)
            session.commit()

            print(f"Data fetched for {city}: {temp_celsius}C, {weather_condition}, {timestamp}")

            check_for_alert(city, temp_celsius)

        except Exception as e:
            print(f"Error fetching weather data for {city}: {e}")

# Check alert thresholds
def check_for_alert(city, current_temp):
    results = session.query(WeatherData).filter(WeatherData.city == city).order_by(WeatherData.timestamp.desc()).limit(CONSECUTIVE_UPDATES_THRESHOLD).all()

    if len(results) >= CONSECUTIVE_UPDATES_THRESHOLD:
        if all(entry.temp > ALERT_TEMP_THRESHOLD for entry in results):
            send_alert(city, current_temp)

# Daily summary
def daily_summary():
    summaries = {}
    today = datetime.utcnow().date()

    for city in CITIES:
        results = session.query(WeatherData).filter(WeatherData.city == city, WeatherData.timestamp >= today).all()

        if results:
            temps = [entry.temp for entry in results]
            avg_temp = sum(temps) / len(temps)
            max_temp = max(temps)
            min_temp = min(temps)
            conditions = [entry.weather_condition for entry in results]
            dominant_condition = max(set(conditions), key=conditions.count)

            summaries[city] = {
                "avg_temp": avg_temp,
                "max_temp": max_temp,
                "min_temp": min_temp,
                "dominant_condition": dominant_condition,
            }

            # Store or display the summary
            print(f"City: {city}, Avg: {avg_temp}C, Max: {max_temp}C, Min: {min_temp}C, Condition: {dominant_condition}")

    # Visualize daily summary
    plot_summary(summaries)

# Plot summary
def plot_summary(summaries):
    cities = list(summaries.keys())
    avg_temps = [summaries[city]['avg_temp'] for city in cities]
    max_temps = [summaries[city]['max_temp'] for city in cities]
    min_temps = [summaries[city]['min_temp'] for city in cities]

    plt.figure(figsize=(10, 6))
    plt.plot(cities, avg_temps, label='Average Temp', marker='o')
    plt.plot(cities, max_temps, label='Max Temp', marker='o')
    plt.plot(cities, min_temps, label='Min Temp', marker='o')
    plt.title('Daily Weather Summary')
    plt.xlabel('City')
    plt.ylabel('Temperature (C)')
    plt.legend()
    plt.show()

# Schedule tasks
schedule.every(INTERVAL).seconds.do(fetch_weather)
schedule.every().day.at("23:59").do(daily_summary)

# Run scheduled tasks
while True:
    schedule.run_pending()
    time.sleep(1)
