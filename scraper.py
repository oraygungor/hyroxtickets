#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
import requests
from datetime import datetime
from pathlib import Path

try:
    # Python 3.9+ için saat dilimi desteği
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# --- AYARLAR ---
EVENTS_CONFIG_FILE = "events.json"
BASE_DATA_DIR = Path("data")
EXCLUDE_KEYWORDS = ["SPECTATOR", "RELAY"]

def now_copenhagen() -> datetime:
    """Kopenhag saat dilimine göre şu anki zamanı döner."""
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo("Europe/Copenhagen"))

def fetch_html(url: str, timeout: int = 20) -> str:
    """Verilen URL'den HTML içeriğini çeker."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.7,en;q=0.6",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def extract_next_data(html: str) -> dict:
    """HTML içindeki __NEXT_DATA__ JSON objesini ayıklar."""
    m = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        raise ValueError("__NEXT_DATA__ etiketi bulunamadı.")
    return json.loads(m.group(1).strip())

def build_inventory(next_data: dict) -> dict:
    """JSON içinden bilet ve stok bilgilerini işler."""
    event = (
        next_data.get("props", {})
        .get("pageProps", {})
        .get("event", {})
    )

    tickets = event.get("tickets", []) or []
    categories = event.get("categories", []) or []
    cat_map = {c.get("ref"): (c.get("name") or "Unknown") for c in categories}

    rows = []
    by_parkur = {}

    for t in tickets:
        name = (t.get("name") or "").strip()
        if not name: continue

        upper = name.upper()
        if any(k in upper for k in EXCLUDE_KEYWORDS):
            continue

        active = bool(t.get("active"))
        stock = int(t.get("v") or 0)
        style = t.get("styleOptions") or {}
        hidden = bool(style.get("hiddenInSelectionArea"))

        # Aktif ve gizli olmayan biletleri al
        if active and stock > 0 and not hidden:
            parkur = cat_map.get(t.get("categoryRef"), "Unknown")
            rows.append({"parkur": parkur, "ticket": name, "stock": stock})
            
            by_parkur.setdefault(parkur, {})
            by_parkur[parkur][name] = by_parkur[parkur].get(name, 0) + stock

    return {"tickets": rows, "by_parkur": by_parkur}

def process_single_event(event_info: dict):
    """Tek bir etkinlik için veriyi çeker ve kaydeder."""
    event_id = event_info["id"]
    url = event_info["url"]
    name = event_info["name"]

    print(f"--- İşleniyor: {name} ---")
    
    try:
        html = fetch_html(url)
        next_data = extract_next_data(html)
        inventory = build_inventory(next_data)

        dt = now_copenhagen()
        filename = dt.strftime("%d.%m.%Y") + ".json"
        
        # Her event için kendi klasörü: data/istanbul-2026/
        event_dir = BASE_DATA_DIR / event_id
        event_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = event_dir / filename
        
        payload = {
            "event_id": event_id,
            "event_name": name,
            "fetched_at": dt.isoformat(),
            **inventory
        }

        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"BAŞARILI: {filename} kaydedildi.")
        
    except Exception as e:
        print(f"HATA ({name}): {str(e)}")

def main():
    # 1. events.json dosyasını oku
    events_path = Path(EVENTS_CONFIG_FILE)
    if not events_path.exists():
        print(f"HATA: {EVENTS_CONFIG_FILE} dosyası bulunamadı!")
        return

    try:
        with open(events_path, "r", encoding="utf-8") as f:
            all_events = json.load(f)
    except Exception as e:
        print(f"JSON Okuma Hatası: {e}")
        return

    # 2. Her etkinliği sırayla işle
    for event in all_events:
        process_single_event(event)

if __name__ == "__main__":
    main()
