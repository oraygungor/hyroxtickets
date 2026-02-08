import json
import os
import glob
from datetime import datetime, timedelta

# --- AYARLAR ---
DATA_DIR = "data"
EVENTS_FILE = "events.json"
OUTPUT_FILE = "notifications.json"

# Zaman Pencereleri (Gün)
WINDOW_NEW_EVENT = 30   # Yeni yarışlar için geriye dönük kontrol
WINDOW_STOCK_CHANGE = 7 # Stok değişimleri için geriye dönük kontrol

# Eşik Değer
LOW_STOCK_THRESHOLD = 5 # Kaçın altına düşünce "Running Low" desin?

# Harici Tutulacak Kelimeler
EXCLUDED_KEYWORDS = ["RELAY", "CHARITY", "SPECTATOR"] 

def load_json(path):
    if not os.path.exists(path): return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def is_excluded(ticket_name):
    name_upper = ticket_name.upper()
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in name_upper:
            return True
    return False

def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d")

def generate_news():
    events_list = load_json(EVENTS_FILE)
    event_map = {e['id']: e['name'] for e in events_list}
    
    notifications = []
    today = datetime.now()
    
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    
    for file_path in json_files:
        event_id = os.path.basename(file_path).replace(".json", "")
        event_name = event_map.get(event_id, event_id)
        
        data = load_json(file_path)
        history = data.get("history", [])
        
        if not history:
            continue
            
        # --- 1. YENİ YARIŞ KONTROLÜ ---
        first_entry = history[0]
        first_date = parse_date(first_entry['date'])
        if (today - first_date).days <= WINDOW_NEW_EVENT:
            notifications.append({
                "type": "new_event",
                "message": f"NEW EVENT: {event_name} added to calendar.",
                "date": first_entry['date'],
                "priority": 1
            })

        # --- 2. STOK GEÇMİŞİ ANALİZİ (Son 7 Gün) ---
        for i in range(len(history) - 1, 0, -1):
            current_day = history[i]
            prev_day = history[i-1]
            
            curr_date_obj = parse_date(current_day['date'])
            if (today - curr_date_obj).days > WINDOW_STOCK_CHANGE:
                break
                
            current_tickets = {t['ticket']: t['stock'] for t in current_day['data']['tickets'] if not is_excluded(t['ticket'])}
            prev_tickets = {t['ticket']: t['stock'] for t in prev_day['data']['tickets'] if not is_excluded(t['ticket'])}
            
            all_tickets = set(current_tickets.keys()) | set(prev_tickets.keys())
            
            for t_name in all_tickets:
                curr_stock = current_tickets.get(t_name, 0)
                prev_stock = prev_tickets.get(t_name, 0)
                
                clean_name = t_name.replace("HYROX", "").strip()
                event_date_str = current_day['date']
                
                # --- MANTIK ZİNCİRİ (if - elif - elif) ---
                # Bu yapı sayesinde bir durum gerçekleşirse diğerlerine bakmaz.
                
                # DURUM A: RESTOCK (0 -> Pozitif)
                # Dün kesinlikle 0 olmalı. Bugün 1 bile olsa Restock sayılır.
                if prev_stock == 0 and curr_stock > 0:
                    notifications.append({
                        "type": "restock",
                        "message": f"RESTOCK: {curr_stock} tickets released for {clean_name} at {event_name}!",
                        "date": event_date_str,
                        "priority": 3
                    })
                
                # DURUM B: RUNNING LOW (Yüksek -> Düşük)
                # ÇAKIŞMA ENGELLEME:
                # Sadece dün eşik değerin ÜSTÜNDEYSE (>5) ve bugün altına indiyse çalışır.
                # Eğer dün 0 idiyse (Restock durumu), burası "False" döner ve çalışmaz.
                elif prev_stock > LOW_STOCK_THRESHOLD and 0 < curr_stock <= LOW_STOCK_THRESHOLD:
                     notifications.append({
                        "type": "low_stock",
                        "message": f"HURRY UP: Only {curr_stock} tickets left for {clean_name} at {event_name}!",
                        "date": event_date_str,
                        "priority": 2
                    })

                # DURUM C: SOLD OUT (Pozitif -> 0)
                elif prev_stock > 0 and curr_stock == 0:
                    notifications.append({
                        "type": "soldout",
                        "message": f"SOLD OUT: {clean_name} at {event_name} is gone.",
                        "date": event_date_str,
                        "priority": 0
                    })

    # Sıralama: Önce Tarih (Yeni -> Eski), Sonra Önem Derecesi
    notifications.sort(key=lambda x: (x['date'], x['priority']), reverse=True)
    
    # UI dolmasın diye limit
    recent_notifications = notifications[:20]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(recent_notifications, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {len(recent_notifications)} notifications.")

if __name__ == "__main__":
    generate_news()
