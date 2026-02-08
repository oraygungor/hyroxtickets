import json
import os
import glob
from datetime import datetime

# Ayarlar
DATA_DIR = "data"
EVENTS_FILE = "events.json"
OUTPUT_FILE = "notifications.json"

def load_json(path):
    if not os.path.exists(path): return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_news():
    events_list = load_json(EVENTS_FILE)
    # ID -> Event Name eşleşmesi için sözlük
    event_map = {e['id']: e['name'] for e in events_list}
    
    notifications = []
    
    # Tüm data klasöründeki event jsonlarını gez
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    
    for file_path in json_files:
        event_id = os.path.basename(file_path).replace(".json", "")
        event_name = event_map.get(event_id, event_id)
        
        data = load_json(file_path)
        history = data.get("history", [])
        
        # Karşılaştırma yapabilmek için en az 1 kayıt olmalı
        if not history:
            continue
            
        latest = history[-1]
        latest_date = latest['date']
        
        # --- DURUM 1: YENİ YARIŞ EKLENDİ ---
        # Eğer geçmişte sadece 1 kayıt varsa, bu yarış listeye yeni girmiştir.
        if len(history) == 1:
            notifications.append({
                "type": "new_event",
                "message": f"YENİ YARIŞ: {event_name} takvime eklendi!",
                "date": latest_date,
                "priority": 1
            })
            continue

        # --- DURUM 2 & 3: STOK DEĞİŞİMLERİ ---
        # Bir önceki günün verisini al
        previous = history[-2]
        
        # Biletleri sözlüğe çevir ki karşılaştırma kolay olsun: { "MEN OPEN": 10, ... }
        current_tickets = {t['ticket']: t['stock'] for t in latest['data']['tickets']}
        prev_tickets = {t['ticket']: t['stock'] for t in previous['data']['tickets']}
        
        all_ticket_names = set(current_tickets.keys()) | set(prev_tickets.keys())
        
        for t_name in all_ticket_names:
            curr_stock = current_tickets.get(t_name, 0)
            prev_stock = prev_tickets.get(t_name, 0)
            
            clean_name = t_name.replace("HYROX", "").strip()
            
            # Senaryo A: Bilet Yoktu/Bitmişti -> Şimdi Var (RESTOCK)
            if prev_stock == 0 and curr_stock > 0:
                notifications.append({
                    "type": "restock",
                    "message": f"BİLET AÇILDI: {event_name} - {clean_name} kategorisinde {curr_stock} bilet satışa çıktı!",
                    "date": latest_date,
                    "priority": 2
                })
                
            # Senaryo B: Bilet Vardı -> Şimdi Bitti (SOLD OUT)
            elif prev_stock > 0 and curr_stock == 0:
                notifications.append({
                    "type": "soldout",
                    "message": f"TÜKENDİ: {event_name} - {clean_name} biletleri az önce bitti.",
                    "date": latest_date,
                    "priority": 0
                })

    # Bildirimleri tarihe göre (en yeni en üstte) ve önceliğe göre sırala
    # Priority: 2 (Restock - En Önemli), 1 (New Event), 0 (Sold Out)
    notifications.sort(key=lambda x: (x['date'], x['priority']), reverse=True)
    
    # Sadece son 1-2 günün bildirimlerini tutmak mantıklı olabilir veya son 10 bildirim
    recent_notifications = notifications[:10] 
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(recent_notifications, f, indent=2, ensure_ascii=False)
    
    print(f"{len(recent_notifications)} bildirim oluşturuldu.")

if __name__ == "__main__":
    generate_news()
