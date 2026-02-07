import requests
from bs4 import BeautifulSoup
import json
import re
import os
import time
from datetime import datetime

# --- AYARLAR ---
BASE_URL = "https://hyrox.com/find-my-race/"
JSON_FILE = "events.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_text(text):
    """Metinlerdeki gereksiz boşlukları temizler."""
    if not text: return ""
    return text.strip()

def generate_id(name, date_str):
    """Yarış isminden ve yıldan benzersiz ID oluşturur (örn: hyrox-vienna-2026)."""
    # Yılı bul
    year_match = re.search(r'\d{4}', date_str)
    year = year_match.group(0) if year_match else "2026"
    
    # İsmi temizle
    slug = name.lower()
    slug = slug.replace('®', '').replace('™', '')
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    
    return f"{slug}-{year}"

def format_date_dd_mm_yyyy(date_str):
    """
    '6. Feb. 2026' formatını '06.02.2026' formatına çevirir.
    """
    if not date_str: return ""
    
    # Ay sözlüğü
    months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
        'january': '01', 'february': '02', 'march': '03', 'april': '04', 'june': '06',
        'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    try:
        # Regex ile gün, ay ve yılı yakala
        match = re.search(r'(\d{1,2})[\.\s]+([A-Za-z]+)[\.\s]+(\d{4})', date_str)
        if match:
            day = match.group(1).zfill(2) # Tek haneyse başına 0 ekle
            month_name = match.group(2).lower()[:3] # İlk 3 harfi al
            year = match.group(3)
            
            if month_name in months:
                return f"{day}.{months[month_name]}.{year}"
    except Exception as e:
        print(f"Tarih formatlama hatası ({date_str}): {e}")
    
    return date_str # Hata olursa orijinalini döndür

def get_checkout_url(event_page_url):
    """
    Etkinlik detay sayfasına gidip doğru checkout linkini bulur.
    """
    if not event_page_url: return ""
    
    try:
        time.sleep(1) # Sunucuyu yormamak için bekleme
        response = requests.get(event_page_url, headers=HEADERS, timeout=15)
        if response.status_code != 200: return event_page_url
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        found_link = None
        
        # 1. Öncelik: Hem 'checkout' hem 'season' içeren link
        for link in links:
            href = link['href']
            if '-season-' in href and '/checkout/' in href:
                found_link = href
                break
        
        # 2. Öncelik: Sadece 'season' içeren link (Bulunursa 'event' -> 'checkout' yapılır)
        if not found_link:
            for link in links:
                href = link['href']
                if '-season-' in href:
                    found_link = href
                    break
        
        if found_link:
            # Absolute URL yap
            if not found_link.startswith('http'):
                from urllib.parse import urljoin
                found_link = urljoin(event_page_url, found_link)
            
            # Link Düzeltme (/event/ -> /checkout/)
            if '/event/' in found_link:
                found_link = found_link.replace('/event/', '/checkout/')
            
            # Query parametrelerini temizle (? sonrası)
            found_link = found_link.split('?')[0]
            
            return found_link
            
    except Exception as e:
        print(f"Link tarama hatası ({event_page_url}): {e}")
        
    return event_page_url # Bulamazsa ana linki döndür

def main():
    print("--- Hyrox Yarış Tarayıcısı Başlatılıyor ---")
    
    # 1. Mevcut JSON'u Yükle (Eski verileri korumak için)
    existing_events = {}
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # ID'yi anahtar yaparak sözlüğe çevir (Hızlı erişim için)
                for item in data:
                    existing_events[item['id']] = item
            print(f"Mevcut dosya yüklendi: {len(existing_events)} kayıt.")
        except json.JSONDecodeError:
            print("Mevcut JSON dosyası bozuk, yeni baştan oluşturulacak.")

    # 2. Ana Sayfayı Tara
    try:
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"Ana sayfaya erişilemedi: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Grid yapısını bul (HTML yapısına göre CSS seçici)
    articles = soup.select('.w-grid-list article.event')
    print(f"Sitede {len(articles)} adet yarış bulundu. İşleniyor...")

    processed_count = 0
    
    for article in articles:
        # İsim ve Link
        title_tag = article.select_one('.entry-title a')
        if not title_tag: continue
        
        raw_name = clean_text(title_tag.text)
        event_page_url = title_tag['href']
        
        # Tarih
        date_tag = article.select_one('.event_date_1 .w-post-elm-value')
        raw_date = clean_text(date_tag.text) if date_tag else "Tarih Yok"
        
        # Verileri İşle
        formatted_date = format_date_dd_mm_yyyy(raw_date)
        event_id = generate_id(raw_name, raw_date)
        
        print(f"[{processed_count + 1}/{len(articles)}] Taranıyor: {raw_name}...", end="", flush=True)
        
        # Checkout Linkini Bul
        final_url = get_checkout_url(event_page_url)
        
        # EĞER ÖDEME LİNKİ YOKSA LİSTEYE EKLEME (İsteğiniz üzerine)
        if '-season-' not in final_url:
             print(" [ATLANDI - Ödeme linki bulunamadı]")
             processed_count += 1
             continue

        # Yeni Veri Objesi
        new_entry = {
            "id": event_id,
            "name": raw_name,
            "url": final_url,
            "startDate": formatted_date
        }
        
        # 3. Güncelleme Mantığı (Merge)
        if event_id in existing_events:
            # Varsa güncelle (Link değişmiş olabilir)
            existing_events[event_id].update(new_entry)
            print(" [GÜNCELLENDİ]")
        else:
            # Yoksa ekle
            existing_events[event_id] = new_entry
            print(" [YENİ EKLENDİ]")
            
        processed_count += 1

    # 4. JSON Olarak Kaydet
    # Dictionary'i tekrar listeye çevir ve tarihe göre sıralayabiliriz (opsiyonel)
    final_list = list(existing_events.values())
    
    # Sonucu Kaydet
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)
    
    print(f"\nİşlem tamamlandı. Toplam {len(final_list)} yarış 'events.json' dosyasına kaydedildi.")

if __name__ == "__main__":
    main()
