import os
import requests
import json

def check_tickets():
    # GitHub Secrets veya Environment'dan URL'i alıyoruz.
    # Eğer environment'da yoksa test için hardcoded URL kullanılabilir.
    url = os.environ.get('URL', 'https://api.hyrox.com/waitlist-endpoint-or-ticket-url') 
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    try:
        print(f"İstek gönderiliyor: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # DÜZELTİLEN KISIM BURASI:
        # JSON zaten array formatında geliyor, sadece biletleri işleyip HISTORY'e atıyoruz
        data = response.json()

        print("Veri başarıyla çekildi.")
        
        # Eğer veri bir liste (array) ise işle
        if isinstance(data, list):
            print(f"Toplam {len(data)} adet kayıt bulundu.")
            for item in data:
                # Burada bilet kontrol mantığın olacak
                # Örneğin: print(item.get('name'))
                pass
        else:
            print("Gelen veri beklenen liste formatında değil.")
            print(json.dumps(data, indent=2))

    except json.JSONDecodeError:
        print("Hata: Gelen yanıt JSON formatında değil.")
        # Hata ayıklamak için gelen yanıtın ilk 200 karakterini yazdır
        print(f"Gelen yanıt başı: {response.text[:200]}")
    except Exception as e:
        print(f"Bir hata oluştu: {e}")

if __name__ == "__main__":
    check_tickets()
