#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
import os
import requests
from datetime import datetime
from pathlib import Path

# Timezone desteği
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# Sabitler
EVENTS_FILE = "events.json"
DATA_DIR = "data"
EXCLUDE_KEYWORDS = ["SPECTATOR", "RELAY"] 

def now_copenhagen() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo("Europe/Copenhagen"))

def fetch_html(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def extract_next_data(html: str) -> dict:
    m = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        raise ValueError("__NEXT_DATA__ script tag bulunamadı.")
    return json.loads(m.group(1).strip())

def build_inventory(next_data: dict) -> dict:
    props = next_data.get("props", {}).get("pageProps", {})
    event = props.get("event") or props.get("fallback", {}).get("event", {})
    
    if not event:
        return {"tickets": [], "by_parkur": {}}

    tickets = event.get("tickets", []) or []
    categories = event.get("categories", []) or []
    cat_map = {c.get("ref"): (c.get("name") or "Unknown") for c in categories}

    rows = []
    for t in tickets:
        name = (t.get("name") or "").strip()
        if not name or any(k in name.upper() for k in EXCLUDE_KEYWORDS):
            continue

        active = bool(t.get("active"))
        stock = int(t.get("v") or 0)
        style = t.get("styleOptions") or {}
        hidden = bool(style.get("hiddenInSelectionArea"))

        if active and stock > 0 and not hidden:
            parkur = cat_map.get(t.get("categoryRef"), "Unknown")
            rows.append({"parkur": parkur, "ticket": name, "stock": stock})

    by_parkur = {}
    for r in rows:
        p = r["parkur"]
        n = r["ticket"]
        s = r["stock"]
        by_parkur.setdefault(p, {})
        by_parkur[p][n] = by_parkur[p].get(n, 0) + s

    return {"tickets": rows, "by_parkur": by_parkur}

def update_history_file(event_id, event_name, event_url, inventory_data):
    Path(DATA_DIR).mkdir(exist_ok=True)
    
    file_path = Path(DATA_DIR) / f"{event_id}.json"
    current_dt = now_copenhagen()
    today_str = current_dt.strftime("%Y-%m-%d")

    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Uyarı: {file_path} bozuk, yeni dosya oluşturuluyor.")
            data = {"event_id": event_id, "history": []}
    else:
        data = {
            "event_id": event_id,
            "event_name": event_name,
            "url": event_url,
            "history": []
        }

    new_entry = {
        "date": today_str,
        "fetched_at": current_dt.isoformat(),
        "total_stock": sum(len(v) for v in inventory_data["by_parkur"].values()),
        "data": inventory_data
    }

    found_index = -1
    for i, entry in enumerate(data["history"]):
        if entry.get("date") == today_str:
            found_index = i
            break
    
    if found_index != -1:
        print(f"   🔄 {today_str} verisi güncelleniyor...")
        data["history"][found_index] = new_entry
    else:
        print(f"   ➕ {today_str} verisi ekleniyor...")
        data["history"].append(new_entry)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return file_path

def main():
    if not os.path.exists(EVENTS_FILE):
        print(f"HATA: {EVENTS_FILE} bulunamadı.")
        sys.exit(1)

    with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
        events = json.load(f)

    current_dt = now_copenhagen()
    print(f"--- Tarama Başladı: {current_dt.isoformat()} ---")

    for event in events:
        event_id = event.get('id')
        event_name = event.get('name')
        url = event.get('url')
        start_date_str = event.get('startDate') # Tarihi alıyoruz

        if not event_id or not url:
            continue

        # --- TARİH KONTROLÜ (YENİ EKLENEN KISIM) ---
        if start_date_str:
            try:
                # String tarihi (06.02.2026) datetime objesine çevir
                event_date = datetime.strptime(start_date_str, "%d.%m.%Y")
                
                # Timezone sorununu çözmek için naive date kullanıyoruz (sadece gün/ay/yıl)
                # Eğer bugün > yarış tarihi ise atla
                if current_dt.date() > event_date.date():
                    print(f"\n⏩ ATLANDI: {event_name} - Yarış tarihi ({start_date_str}) geçmiş.")
                    continue
            except ValueError:
                print(f"⚠️ Uyarı: {event_name} için tarih formatı hatalı ({start_date_str}), yine de kontrol ediliyor.")
        # ---------------------------------------------

        print(f"\nİşleniyor: {event_name} ({event_id})")
        
        try:
            html = fetch_html(url)
            next_data = extract_next_data(html)
            inventory = build_inventory(next_data)
            saved_path = update_history_file(event_id, event_name, url, inventory)
            print(f"✅ KAYDEDİLDİ: {saved_path}")

        except Exception as e:
            print(f"❌ HATA: {event_name} - {str(e)}")

if __name__ == "__main__":
    main()
