import socket
import threading
import time

# --- KONFIGURATION ---
HAMALERT_HOST = "hamalert.org"
HAMALERT_PORT = 7300
LOCAL_PORT = 7300  # Port in SDR-Control eintragen

CALLSIGN = "<CALL>"  # Ihr HamAlert-Rufzeichen
PASSWORD = "<PW>"    # Ihr HamAlert-Passwort
# ---------------------

connected_clients = set()
clients_lock = threading.Lock()

def handle_local_client(client_socket, client_address):
   """Verwaltet SDR-Control-Verbindungen"""
   print(f"[Proxy] SDR-Control verbunden: {client_address}")

   try:
       # 1. Begrüßung senden (muss mit \r\n enden)
       client_socket.sendall(b"Welcome to Local DX Cluster Server\r\n")
       time.sleep(0.1)

       # 2. Den CC-Cluster Prompt genau so senden, wie SDR-Control ihn erwartet
       client_socket.sendall(b"CCCluster de <CALL>-7 >\r\n")
       print(f"[Proxy] Handshake mit SDR-Control erfolgreich.")

   except Exception as e:
       print(f"[Proxy-Fehler] Handshake fehlgeschlagen: {e}")
       client_socket.close()
       return

   with clients_lock:
       connected_clients.add(client_socket)

   # Verbindung halten und Keepalive-Befehle von SDR-Control schlucken
   while True:
       try:
           data = client_socket.recv(1024)
           if not data:
               break
           # Jedes Lebenszeichen beantworten wir mit dem Prompt
           client_socket.sendall(b"CCCluster de <CALL>-7 >\r\n")
       except Exception:
           break

   with clients_lock:
       connected_clients.remove(client_socket)
   print(f"[Proxy] SDR-Control getrennt: {client_address}")
   client_socket.close()

def process_and_send_spot(spot_line):
   """Reinigt die rohe Textzeile und sendet sie mit Pacing an SDR-Control"""
   spot_line = spot_line.strip()

   # SDR-Control reagiert NUR auf Zeilen, die exakt mit "DX de " beginnen
   if not spot_line or not spot_line.startswith("DX de"):
       return

   print(f"[PROXY -> SDR-CONTROL]: {spot_line}")

   # Wir hängen den Prompt direkt an die Zeile an, damit SDR-Control weiß:
   # "Dieser eine Spot ist jetzt komplett fertig, bitte auswerten!"
   # final_packet = f"{spot_line}\r\nCCCluster de <CALL>-7 >\r\n".encode('utf-8')
   final_packet = f"{spot_line}\n".encode('utf-8')

   with clients_lock:
       current_clients = list(connected_clients)

   for client in current_clients:
       try:
           client.sendall(final_packet)
           # WICHTIG: 50ms Pause nach jedem gesendeten Paket!
           # Das verhindert, dass SDR-Control mehrere Spots im TCP-Puffer zusammenmischt.
           time.sleep(0.05)
       except Exception:
           with clients_lock:
               if client in connected_clients:
                   connected_clients.remove(client)


def hamalert_worker():
   """Verbindet sich mit HamAlert und liest den Stream zeilenweise"""
   while True:
       try:
           print(f"[HamAlert] Verbinde mit {HAMALERT_HOST}:{HAMALERT_PORT}...")
           s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
           s.settimeout(5.0)
           s.connect((HAMALERT_HOST, HAMALERT_PORT))
           s.settimeout(None)

           # Blind-Login Rhythmus
           time.sleep(1.5)
           s.sendall(f"{CALLSIGN}\r\n".encode('utf-8'))
           time.sleep(1.5)
           s.sendall(f"{PASSWORD}\r\n".encode('utf-8'))
           time.sleep(1.5)

           print("[HamAlert] Login vollzogen. Fordere Historie an...")
           s.sendall(b"sh/dx 10\r\n")

           # --- ZEILENBASIERTER PUFFER ---
           # Verhindert, dass unvollständige TCP-Pakete den Parser blockieren
           data_buffer = ""
           while True:
               chunk = s.recv(4096).decode('utf-8', errors='ignore')
               if not chunk:
                   print("[HamAlert] Server hat die Verbindung geschlossen.")
                   break

               data_buffer += chunk
               # Solange Zeilenumbrüche im Puffer sind, verarbeiten wir sie einzeln
               while "\n" in data_buffer:
                   line, data_buffer = data_buffer.split("\n", 1)
                   process_and_send_spot(line)

       except Exception as e:
           print(f"[HamAlert-Fehler] Verbindung abgebrochen: {e}")

       print("[Proxy] Neustart in 10 Sekunden...")
       time.sleep(10)

def main():
   t = threading.Thread(target=hamalert_worker, daemon=True)
   t.start()

   server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
   server.bind(("0.0.0.0", LOCAL_PORT))
   server.listen(5)
   print(f"[Proxy] Server läuft auf Port {LOCAL_PORT}. Bereit für SDR-Control.")

   try:
       while True:
           client_sock, client_addr = server.accept()
           client_thread = threading.Thread(target=handle_local_client, args=(client_sock, client_addr), daemon=True)
           client_thread.start()
   except KeyboardInterrupt:
       print("\n[Proxy] Beendet.")
   finally:
       server.close()

if __name__ == "__main__":
   main()

