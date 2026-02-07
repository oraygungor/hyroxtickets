#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
import os
import requests
from datetime import datetime
from pathlib import Path

# Timezone desteği (Python 3.9+)
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# Sabitler
EVENTS_FILE = "events.json"
DATA_DIR = "data"
EXCLUDE_KEYWORDS = ["SPECTATOR", "RELAY"]  # İstenmeyen bilet tipleri

def now_copenhagen() -> datetime:
    """Zaman damgası için Kopenhag veya yerel saat döner."""
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo("Europe/Copenhagen"))

def date_filename(dt: datetime) -> str:
    """Dosya adı formatı: 07.02.2026.json"""
    return dt.strftime("%d.%m.%Y") + ".json"

def fetch_html(url: str, timeout: int = 30) -> str:
    """Verilen URL'den HTML içeriğini çeker."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def extract_next_data(html: str) -> dict:
    """HTML içindeki __NEXT_DATA__ JSON bloğunu regex ile bulur."""
    m = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        raise ValueError("__NEXT_DATA__ script tag bulunamadı (Sayfa yapısı değişmiş olabilir).")
    
    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"__NEXT_DATA__ JSON parse hatası: {e}") from e

def build_inventory(next_data: dict) -> dict:
    """Ham veriden stok ve bilet bilgilerini ayıklar."""
    props = next_data.get("props", {}).get("pageProps", {})
    
    # Bazen 'event' ana objesi doğrudan pageProps altında olmayabilir, kontrol edelim
    event = props.get("event") or props.get("fallback", {}).get("event", {})
    
    if not event:
        # Event verisi bulunamazsa boş dön
        return {"tickets": [], "by_parkur": {}}

    tickets = event.get("tickets", []) or []
    categories = event.get("categories", []) or []

    # Kategori ID -> Kategori İsmi eşleşmesi (örn: Men Open)
    cat_map = {c.get("ref"): (c.get("name") or "Unknown") for c in categories}

    rows = []
    for t in tickets:
        name = (t.get("name") or "").strip()
        if not name:
            continue

        upper = name.upper()
        # İstenmeyen kelimeleri filtrele (Spectator, Relay vb.)
        if any(k in upper for k in EXCLUDE_KEYWORDS):
            continue

        active = bool(t.get("active"))
        stock = int(t.get("v") or 0) # 'v' genelde stok miktarını tutar
        style = t.get("styleOptions") or {}
        hidden = bool(style.get("hiddenInSelectionArea"))

        # Aktif, stoğu olan ve gizli olmayan biletleri al
        if active and stock > 0 and not hidden:
            parkur = cat_map.get(t.get("categoryRef"), "Unknown")
            rows.append({"parkur": parkur, "ticket": name, "stock": stock})

    # Özetleme: Parkur -> Ticket -> Toplam Stok
    by_parkur = {}
    for r in rows:
        p = r["parkur"]
        n = r["ticket"]
        s = r["stock"]
        by_parkur.setdefault(p, {})
        # Aynı isimde birden fazla bilet varsa stoklarını topla
        by_parkur[p][n] = by_parkur[p].get(n, 0) + s

    return {"tickets": rows, "by_parkur": by_parkur}

def load_events():
    """events.json dosyasını yükler."""
    if not os.path.exists(EVENTS_FILE):
        print(f"HATA: {EVENTS_FILE} bulunamadı.")
        sys.exit(1)
    
    try:
        with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"HATA: {EVENTS_FILE} geçerli bir JSON değil.")
        sys.exit(1)

def main():
    events = load_events()
    dt = now_copenhagen()
    filename = date_filename(dt)

    print(f"--- Tarama Başladı: {dt.isoformat()} ---")

    for event in events:
        event_id = event.get('id')
        event_name = event.get('name')
        url = event.get('url')

        if not event_id or not url:
            print(f"ATLANDI: ID veya URL eksik -> {event}")
            continue

        print(f"\nİşleniyor: {event_name} ({event_id})")
        
        try:
            # 1. HTML Çek
            html = fetch_html(url)
            
            # 2. Veriyi Ayrıştır
            next_data = extract_next_data(html)
            inventory = build_inventory(next_data)
            
            # 3. Çıktı Klasörünü Hazırla: data/istanbul-2026/
            event_dir = Path(DATA_DIR) / event_id
            event_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = event_dir / filename

            # 4. JSON Oluştur
            payload = {
                "event_id": event_id,
                "event_name": event_name,
                "event_url": url,
                "fetched_at": dt.isoformat(),
                **inventory
            }

            # 5. Dosyaya Yaz
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            
            # Özet Log
            total_tickets = sum(len(v) for v in inventory["by_parkur"].values())
            print(f"✅ BAŞARILI: {output_path} (Kategori sayısı: {len(inventory['by_parkur'])}, Bilet türü: {total_tickets})")

        except Exception as e:
            print(f"❌ HATA: {event_name} işlenirken sorun oluştu: {str(e)}")

if __name__ == "__main__":
    main()
