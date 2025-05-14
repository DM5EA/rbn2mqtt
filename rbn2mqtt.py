import telnetlib
import json
import time
import threading
import paho.mqtt.client as mqtt

# Konfiguration
TELNET_HOST = "telnet.reversebeacon.net"
TELNET_PORT = 7000
TELNET_USERNAME = "DM5EA"
TELNET_LOGIN_PROMPT = b"Please enter your call:"

MQTT_BROKER = "192.168.43.61"
MQTT_PORT = 1883
MQTT_TOPIC = "rbn"
MQTT_TOPIC_QRG = "rbn/QRG"
MQTT_TOPIC_DB = "rbn/dB"
MQTT_TOPIC_WPM = "rbn/WpM"
MQTT_TOPIC_CALL = "rbn/CALL"
MQTT_TOPIC_UTC = "rbn/UTC"

# MQTT-Client initialisieren
mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Erfolgreich mit MQTT verbunden")
    else:
        print(f"❌ Verbindung fehlgeschlagen mit Code {rc}")

def connect_mqtt():
    mqtt_client.on_connect = on_connect
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()

def process_and_publish(line):
    fields = line.strip().split()
    timetup = time.gmtime()
    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', timetup)

    if len(fields) >= 5 and fields[4] == TELNET_USERNAME:
#        print(line.strip())
        data = {
            "fields": fields,
            "timestamp": timetup 
        }
        json_payload = json.dumps(data)
        mqtt_client.publish(MQTT_TOPIC_CALL,fields[2][:-3])
        mqtt_client.publish(MQTT_TOPIC_QRG,fields[3])
        mqtt_client.publish(MQTT_TOPIC_DB,fields[6])
        mqtt_client.publish(MQTT_TOPIC_WPM,fields[8])
        mqtt_client.publish(MQTT_TOPIC_UTC,ts)
#        mqtt_client.publish(MQTT_TOPIC_UTC,fields[11][:-1])
#        mqtt_client.publish(MQTT_TOPIC, json_payload)
#        print(f"📤 Gesendet an Topic '{MQTT_TOPIC}': {json_payload}")
#    else:
#        print(f"⏭️ Zeile ignoriert: {line.strip()}")

def telnet_listener():
    try:
        with telnetlib.Telnet(TELNET_HOST, TELNET_PORT) as tn:
            print(f"🔌 Verbunden mit Telnet {TELNET_HOST}:{TELNET_PORT}")

            # Warte auf Login-Prompt und sende Benutzernamen
            tn.read_until(TELNET_LOGIN_PROMPT)
            tn.write(TELNET_USERNAME.encode("utf-8") + b"\n")
            print(f"👤 Benutzername '{TELNET_USERNAME}' gesendet")

            while True:
                line = tn.read_until(b"\n").decode("utf-8")
                if line:
                    process_and_publish(line)

    except Exception as e:
        print(f"⚠️ Telnet-Fehler: {e}")

def main():
    connect_mqtt()
    time.sleep(2)  # Warten bis MQTT-Verbindung aufgebaut ist

    telnet_thread = threading.Thread(target=telnet_listener)
    telnet_thread.start()

if __name__ == "__main__":
    main()
