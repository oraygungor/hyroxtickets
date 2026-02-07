import json
import requests
import os

def load_events():
    """events.json dosyasını okur ve listeyi döndürür."""
    file_path = 'events.json'
    
    if not os.path.exists(file_path):
        print(f"HATA: {file_path} dosyası bulunamadı! Lütfen dosyanın repoda olduğundan emin ol.")
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Eğer JSON bir liste değilse (örneğin tek bir obje ise) listeye çevir
            if not isinstance(data, list):
                print("Uyarı: JSON içeriği bir liste değil, tekil obje olarak işleniyor.")
                return [data]
            return data
    except json.JSONDecodeError:
        print(f"HATA: {file_path} dosyası geçerli bir JSON formatında değil.")
        return []

def check_tickets():
    events = load_events()
    
    if not events:
        print("İşlenecek etkinlik bulunamadı.")
        return

    print(f"Toplam {len(events)} etkinlik bulundu. Kontrol başlıyor...\n")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for event in events:
        # JSON dosyasındaki anahtarların (keys) isimleri önemli.
        # Örnek: {"name": "Istanbul", "url": "https://..."}
        url = event.get('url')
        name = event.get('name', 'İsimsiz Etkinlik')

        if not url:
            print(f"UYARI: '{name}' etkinliği için URL tanımlanmamış, geçiliyor.")
            continue

        print(f"kontrol ediliyor: {name}...")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ {name}: Erişim Başarılı.")
                
                # BURADA KONTROL MANTIĞIN OLACAK
                # Örnek: Eğer sayfada "Sold Out" yazmıyorsa bilet var demektir.
                page_content = response.text.lower()
                
                if "sold out" in page_content or "tükendi" in page_content:
                    print(f"   ❌ Durum: TÜKENDİ ({name})")
                else:
                    print(f"   🎉 Durum: BİLET OLABİLİR! ({name})")
                    # Burada Telegram/Discord bildirimi gönderme kodu eklenebilir.
            
            else:
                print(f"⚠️ {name}: Sayfaya erişilemedi (Kod: {response.status_code})")

        except Exception as e:
            print(f"❌ {name}: Hata oluştu - {str(e)}")
        
        print("-" * 30)

if __name__ == "__main__":
    check_tickets()
