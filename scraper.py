/* --- HTML İÇİNDEKİ YENİ SCRIPT PARÇASI --- */

async function loadAllData() {
    // 1. Doğrudan history.json dosyasını çek
    const url = `${CONFIG.dataDir}/history.json?t=${Date.now()}`;
    
    try {
        const res = await fetch(url);
        if(!res.ok) throw new Error("Veri dosyası (history.json) bulunamadı.");
        
        const json = await res.json();
        
        // JSON zaten array formatında geliyor, sadece biletleri işleyip HISTORY'e atıyoruz
        HISTORY = json.map(day => ({
            date: day.date,
            timestamp: day.timestamp,
            tickets: processTickets(day.tickets)
        }));
        
        if(!HISTORY.length) throw new Error("Veri dosyası boş.");

        // Bilgi mesajını güncelle
        document.getElementById("dbStatus").textContent = 
            `Veri Aralığı: ${HISTORY[0].date} - ${HISTORY[HISTORY.length-1].date}`;

    } catch(err) {
        throw new Error(`Veri yüklenemedi: ${err.message}`);
    }
}
