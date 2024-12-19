import os
import time
import board
import busio
import json
import firebase_admin
# import paho.mqtt.client as mqtt
import math

from firebase_admin import credentials, firestore
from adafruit_pm25.i2c import PM25_I2C
from adafruit_sgp30 import Adafruit_SGP30
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))

cred_path = os.path.join(script_dir, 'AQMNYUFirebaseAdminSDK.json')

# MQTT broker settings
# mqtt_broker = "tigoe.net"
# #mqtt_broker = "test.mosquitto.org"
# mqtt_port = 1883
# mqtt_topic = "steven/sensordata"
# mqtt_username = "undnet"  # Replace with your actual username
# mqtt_password = "m4nh0l3!"  # Replace with your actual password

# Flag to track connection status
connected = False

# Add breakpoints dictionary
BREAKPOINTS = {
    'pm25': [
        {'concentration': 0.0, 'index': 0},
        {'concentration': 12.0, 'index': 50},
        {'concentration': 35.4, 'index': 100},
        {'concentration': 55.4, 'index': 150},
        {'concentration': 150.4, 'index': 200},
        {'concentration': 250.4, 'index': 300},
        {'concentration': 500.4, 'index': 500},
    ],
    'pm10': [
        {'concentration': 0, 'index': 0},
        {'concentration': 54, 'index': 50},
        {'concentration': 154, 'index': 100},
        {'concentration': 254, 'index': 150},
        {'concentration': 354, 'index': 200},
        {'concentration': 424, 'index': 300},
        {'concentration': 604, 'index': 500},
    ],
    'tvoc': [
        {'concentration': 0, 'index': 0},
        {'concentration': 220, 'index': 50},
        {'concentration': 660, 'index': 100},
        {'concentration': 2200, 'index': 150},
        {'concentration': 5500, 'index': 200},
        {'concentration': 11000, 'index': 300},
        {'concentration': 30000, 'index': 500},
    ],
    'eco2': [
        {'concentration': 400, 'index': 0},
        {'concentration': 600, 'index': 50},
        {'concentration': 1000, 'index': 100},
        {'concentration': 1500, 'index': 150},
        {'concentration': 2000, 'index': 200},
        {'concentration': 5000, 'index': 300},
        {'concentration': 10000, 'index': 500},
    ],
    'pm1_0': [
        {'concentration': 0.0, 'index': 0},
        {'concentration': 12.0, 'index': 50},
        {'concentration': 35.4, 'index': 100},
        {'concentration': 55.4, 'index': 150},
        {'concentration': 150.4, 'index': 200},
        {'concentration': 250.4, 'index': 300},
        {'concentration': 500.4, 'index': 500},
    ],
}

def calculate_sub_index(concentration, pollutant):
    bp = BREAKPOINTS[pollutant]
    for i in range(len(bp) - 1):
        if bp[i]['concentration'] <= concentration <= bp[i + 1]['concentration']:
            I_hi = bp[i + 1]['index']
            I_lo = bp[i]['index']
            C_hi = bp[i + 1]['concentration']
            C_lo = bp[i]['concentration']
            C_p = concentration
            I_p = ((I_hi - I_lo) / (C_hi - C_lo)) * (C_p - C_lo) + I_lo
            return round(I_p)
    return bp[-1]['index']  # Return highest index if concentration exceeds all breakpoints

# Define callback functions
# def on_connect(client, userdata, flags, rc):
#     global connected
#     if rc == 0:
#         print("Connected to MQTT broker with result code " + str(rc))
#         connected = True  # Set the flag to True if connected successfully
#         client.subscribe(mqtt_topic)  # Subscribe to topic if needed
#     else:
#         print("Failed to connect, return code %d\n", rc)
#         connected = False  # Keep flag as False if connection failed

# def on_disconnect(client, userdata, rc):
#     global connected
#     print("Disconnected with result code " + str(rc))
#     connected = False  # Reset the flag when disconnected

# def on_publish(client, userdata, mid):
#     print("Message published with mid: " + str(mid))

# Initialize MQTT client and set callbacks
# mqtt_client = mqtt.Client()
# mqtt_client.username_pw_set(mqtt_username, mqtt_password)  # Set username and password
# mqtt_client.on_connect = on_connect
# mqtt_client.on_disconnect = on_disconnect
# # mqtt_client.on_message = on_message
# mqtt_client.on_publish = on_publish

# # Connect to the MQTT broker
# mqtt_client.connect(mqtt_broker, mqtt_port)

# Initialize Firebase Admin SDK
cred = credentials.Certificate('./AQMNYUFirebaseAdminSDK.json')
#cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize sensors
pm25 = PM25_I2C(i2c)
sgp30 = Adafruit_SGP30(i2c)
sgp30.iaq_init()

# Load baseline if available
try:
    with open("sgp30_baseline.json", "r") as f:
        baseline = json.load(f)
        sgp30.set_iaq_baseline(baseline["eCO2"], baseline["TVOC"])
        print("Baseline loaded:", baseline)
except (FileNotFoundError, KeyError):
    print("No baseline found. Running initial calibration...")

while True:
    try:
        # Read and print PM25 sensor data
        aqdata = pm25.read()
        pm1_0 = aqdata["pm10 standard"]
        pm2_5 = aqdata["pm25 standard"]
        pm10 = aqdata["pm100 standard"]
        print("PM 1.0:", pm1_0)
        print("PM 2.5:", pm2_5)
        print("PM 10:", pm10)

        # Read and print SGP30 sensor data
        eco2 = sgp30.eCO2
        tvoc = sgp30.TVOC
        print("eCO2:", eco2, "ppm")
        print("TVOC:", tvoc, "ppb")

        # Prepare data dictionary
        data = { 
            "timestamp": datetime.now().isoformat(),
            "pm1_0": pm1_0,
            "pm2_5": pm2_5,
            "pm10": pm10,
            "eCO2": eco2,
            "TVOC": tvoc,
            # Add sub-indices
            "pm1_0_index": calculate_sub_index(pm1_0, 'pm1_0'),
            "pm25_index": calculate_sub_index(pm2_5, 'pm25'),
            "pm10_index": calculate_sub_index(pm10, 'pm10'),
            "eco2_index": calculate_sub_index(eco2, 'eco2'),
            "tvoc_index": calculate_sub_index(tvoc, 'tvoc')
        }
        
        # Calculate max AQI
        max_aqi = max(
            data["pm1_0_index"],
            data["pm25_index"],
            data["pm10_index"],
            data["eco2_index"],
            data["tvoc_index"]
        )
        data["max_aqi"] = max_aqi

        # Send data to Firestore
        db.collection('air_quality').add(data)
        print("Data sent to Firestore", data)

        # Publish data to MQTT
        # mqtt_message = json.dumps(data)
        # mqtt_client.loop_start()
        # mqtt_client.publish(mqtt_topic, mqtt_message)
        # mqtt_client.loop_stop()
        # print("Data sent to MQTT Broker:", data)

        # Store baseline every hour
        current_time = time.time()
        if int(current_time) % 3600 < 2:  # Roughly every hour
            baseline = {"eCO2": sgp30.baseline_eCO2, "TVOC": sgp30.baseline_TVOC}
            with open("sgp30_baseline.json", "w") as f:
                json.dump(baseline, f)
            print("Baseline saved:", baseline)

        print()
        #frequency of data submission
        time.sleep(30)
        

    except RuntimeError as e:
        print("Error reading sensor data:", e)
        time.sleep(2)
