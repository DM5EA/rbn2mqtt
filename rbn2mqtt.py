import socket
import json
import time
import threading
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

# Konfiguration
TELNET_HOST = "telnet.reversebeacon.net"
TELNET_PORT = 7000
TELNET_USERNAME = "DM5EA"
TELNET_LOGIN_PROMPT = b"Please enter your call:"

MQTT_BROKER = "192.168.43.62"
MQTT_PORT = 1883
MQTT_TOPIC = "rbn"
MQTT_TOPIC_QRG = "rbn/QRG"
MQTT_TOPIC_DB = "rbn/dB"
MQTT_TOPIC_WPM = "rbn/WpM"
MQTT_TOPIC_CALL = "rbn/CALL"
MQTT_TOPIC_UTC = "rbn/UTC"

mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
#mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc, properties): 
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
    
    # Sicherstellen, dass genug Felder für die Indizes vorhanden sind (mindestens 9 Felder für Index 8)
    if len(fields) >= 9 and fields[4] == TELNET_USERNAME:
        timetup = time.gmtime()
        ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', timetup)
        
        data = {
            "fields": fields,
            "timestamp": timetup
        }
        json_payload = json.dumps(data)
        
        try:
            mqtt_client.publish(MQTT_TOPIC_CALL, fields[2][:-3])
            mqtt_client.publish(MQTT_TOPIC_QRG, fields[3])
            mqtt_client.publish(MQTT_TOPIC_DB, fields[6])
            mqtt_client.publish(MQTT_TOPIC_WPM, fields[8])
            mqtt_client.publish(MQTT_TOPIC_UTC, ts)
#            print(f"📤 Gesendet an MQTT: {fields[2][:-3]} auf {fields[3]} kHz")
        except Exception as mqtt_err:
            print(f"❌ MQTT Sende-Fehler: {mqtt_err}")

def telnet_listener():
    try:
        # Ersatz für telnetlib mittels Standard-Socket
        with socket.create_connection((TELNET_HOST, TELNET_PORT), timeout=10) as sock:
            print(f"🔌 Verbunden mit {TELNET_HOST}:{TELNET_PORT}")
            
            # Puffer für empfangene Daten
            buffer = b""
            
            # Warten auf den Login-Prompt
            while TELNET_LOGIN_PROMPT not in buffer:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buffer += chunk
            
            # Login senden
            sock.sendall(TELNET_USERNAME.encode("utf-8") + b"\n")
            print(f"👤 Benutzername '{TELNET_USERNAME}' gesendet")
            
            # Restpuffer leeren und in Zeilen schneiden
            buffer = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    print("⚠️ Verbindung vom Server getrennt.")
                    break
                
                buffer += data
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    try:
                        line = line_bytes.decode("utf-8", errors="ignore")
                        if line:
                            process_and_publish(line)
                    except Exception as e:
                        print(f"Fehler beim Dekodieren der Zeile: {e}")

    except Exception as e:
        print(f"⚠️ Netzwerk-/Telnet-Fehler: {e}")

def main():
    connect_mqtt()
    time.sleep(2)

    telnet_thread = threading.Thread(target=telnet_listener, daemon=True)
    telnet_thread.start()
    
    # Haupt-Thread am Leben halten
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("👋 Programm beendet.")

if __name__ == "__main__":
    main()

