# 📈 BorsaPy API Service

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Status](https://img.shields.io/badge/Status-Active-success)

**BorsaPy API**, Borsa İstanbul (BIST), Döviz, Altın, Kripto Para ve TEFAS Fon verilerini JSON formatında sunan profesyonel, yüksek performanslı bir REST API servisidir. Mobil uygulamalar, algoritmik ticaret botları ve finansal analiz araçları için özel olarak tasarlanmıştır.

Bu proje, güçlü [borsapy](https://github.com/saidsurucu/borsapy) kütüphanesini modern bir API arayüzü ile dış dünyaya açar.

---

## 🚀 Özellikler

*   **⚡ Anlık Piyasa Verileri:** BIST hisseleri için gecikmesiz/gecikmeli fiyat, hacim ve değişim verileri.
*   **🏦 Banka Kurları:** 20+ Türk bankasının canlı Döviz ve Altın alış/satış kurları.
*   **📊 Teknik Analiz:** Sunucu tarafında hesaplanan RSI, MACD, SMA gibi değerler ve indikatör sinyalleri.
*   **💰 Kripto Para & Fonlar:** Kripto paraların (Binance/BTCTurk) ve TEFAS üzerindeki fonların detaylı verileri.
*   **📅 Ekonomik Takvim & Enflasyon:** Günlük ekonomik olaylar takvimi.
*   **📡 Kesintisiz (Keep-Alive):** Render üzerinde uykuyu engelleyen otomatik self-ping altyapısı mevcuttur.

---

## 📡 API Uç Noktaları (Endpoints)

Servis yayına alındığında `/docs` adresinden interaktif dökümantasyona (Swagger UI) erişebilirsiniz.

| Metod | Uç Nokta (Endpoint) | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/stocks/list` | Tüm BIST şirketlerinin listesini getirir. |
| `GET` | `/stocks/{symbol}` | Hisse özet bilgileri (Fiyat, FK, PD/DD, Piyasa Değeri). |
| `GET` | `/stocks/{symbol}/history` | Tarihsel OHLCV verileri. (`period` ve `interval` parametreleri alabilir). |
| `GET` | `/stocks/{symbol}/financials` | Şirketin mali tabloları (`type`: `balance`, `income`, `cashflow`). |
| `GET` | `/market/screener` | Tüm hisselerin anlık piyasa verileri (Fiyat, Değişim, Hacim). |
| `GET` | `/market/index/{symbol}` | Endeks (Örn: `XU100`, `XU030`) tarihsel verileri. |
| `GET` | `/analysis/{symbol}` | Otomatik teknik analiz ve indikatör değerleri (RSI, SMA). |
| `GET` | `/fx/list` | Takip edilen döviz ve emtiaların listesi. |
| `GET` | `/fx/{symbol}` | Banka ve serbest piyasa kurları (Örn: `USD`, `EUR`, `gram-altin`). |
| `GET` | `/crypto/list` | Desteklenen Kripto para kurları. |
| `GET` | `/crypto/{symbol}` | Seçili Kripto paranın (Örn: `BTCUSDT`) değerleri. |
| `GET` | `/funds/{code}` | TEFAS fon detayları (Örn: `AFT`, `TCD`). |
| `GET` | `/funds/{code}/history` | Fonların tarihsel fiyat değişim verileri. |
| `GET` | `/bonds/{name}` | Devlet Tahvili ve Eurobond piyasa verileri. |
| `GET` | `/market/economy/calendar` | Bugünkü güncel veya yaklaşan önemli ekonomik etkinlikler. |
| `GET` | `/search?q={query}` | Hisse kodu veya şirket adına göre arama yapar. |

---

## 🛠 Kurulum ve Yayınlama (Deploy)

Bu proje **Render**, **Railway** veya herhangi bir VPS üzerinde çalışmaya hazırdır.

### OnRender Ücretsiz Sürüm (Keep-Alive Özelliği)
Render normalde ücretsiz servisleri 15 dakika hareketsizlikten sonra uyutur. Bu durumun önüne geçmek için **BorsaPy API**, render linkinizi `RENDER_EXTERNAL_URL` ortam değişkeninden (otomatik oluşturulur) algılayarak her 14 dakikada bir kendi kendini uyarır (self-ping ping_regularly task) ve API'nizi 7/24 uyanık tutmaya çalışır. 

*Yine de tam garanti olması için ek bir güvenlik katmanı olarak [cron-job.org](https://cron-job.org) adresinden oluşturduğunuz render URL'nize (örn. `https://api-projem.onrender.com/`) her 10 dakikada bir istek atan ücretsiz bir ping görevi ayarlayabilirsiniz.*

### Yerel Çalıştırma (Localhost)

```bash
# Gerekli paketleri yükleyin
pip install -r requirements.txt

# Sunucuyu başlatın
uvicorn main:app --reload
```
API şu adreste çalışacaktır: `http://127.0.0.1:8000`

---

## ⚠️ Yasal Uyarı

Bu API tarafından sağlanan veriler bilgilendirme amaçlıdır. Yatırım tavsiyesi değildir. Veriler üçüncü parti kaynaklardan sağlanmakta olup doğruluk veya kesintisizlik garantisi verilmez.
