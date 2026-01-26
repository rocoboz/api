# 📈 BorsaPy API Service

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Status](https://img.shields.io/badge/Status-Active-success)

**BorsaPy API**, Borsa İstanbul (BIST), Döviz, Altın, Kripto Para ve TEFAS Fon verilerini JSON formatında sunan profesyonel, yüksek performanslı bir REST API servisidir. Mobil uygulamalar, algoritmik ticaret botları ve finansal analiz araçları için özel olarak tasarlanmıştır.

Bu proje, güçlü [borsapy](https://github.com/saidsurucu/borsapy) kütüphanesini modern bir API arayüzü ile dış dünyaya açar.

---

## 🚀 Özellikler

*   **⚡ Anlık Piyasa Verileri:** BIST hisseleri için 15 dakika gecikmeli fiyat, hacim ve değişim verileri.
*   **🏦 Banka Kurları:** 20+ Türk bankasının (Akbank, İş, Garanti vb.) canlı Döviz ve Altın alış/satış kurları.
*   **📊 Teknik Analiz Motoru:** Sunucu tarafında hesaplanan RSI, MACD, SMA, Bollinger Bantları ve Al/Sat sinyalleri.
*   **📑 Mali Tablolar:** Şirketlerin detaylı Bilanço, Gelir Tablosu ve Nakit Akış tabloları.
*   **💰 Yatırım Fonları:** TEFAS üzerindeki tüm fonların detaylı analiz verileri.
*   **🔍 Akıllı Arama:** Hisseleri ve şirketleri isme veya koda göre bulan gelişmiş arama motoru.

---

## 📡 API Uç Noktaları (Endpoints)

Servis yayına alındığında `/docs` adresinden interaktif dökümantasyona (Swagger UI) erişebilirsiniz.

| Metod | Uç Nokta (Endpoint) | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/` | Servis durumunu ve versiyon bilgisini döner. |
| `GET` | `/stocks/list` | Tüm BIST şirketlerinin listesini getirir. |
| `GET` | `/stocks/{symbol}` | Hisse özet bilgileri (Fiyat, FK, PD/DD, Piyasa Değeri). |
| `GET` | `/stocks/{symbol}/history` | Tarihsel OHLCV verileri. (`period` ve `interval` parametreleri alabilir). |
| `GET` | `/stocks/{symbol}/financials` | Şirketin mali tabloları (`type`: `balance`, `income`, `cashflow`). |
| `GET` | `/market/screener` | Tüm hisselerin anlık piyasa verileri (Fiyat, Değişim, Hacim). |
| `GET` | `/market/index/{symbol}` | Endeks (Örn: `XU100`, `XU030`) tarihsel verileri. |
| `GET` | `/analysis/{symbol}` | Otomatik teknik analiz ve indikatör değerleri (RSI, SMA). |
| `GET` | `/fx/list` | Takip edilen döviz ve emtiaların listesi. |
| `GET` | `/fx/{symbol}` | Banka ve serbest piyasa kurları (Örn: `USD`, `EUR`, `gram-altin`). |
| `GET` | `/funds/{code}` | TEFAS fon detayları (Örn: `AFT`, `TCD`). |
| `GET` | `/funds/{code}/history` | Fonların tarihsel fiyat değişim verileri. |
| `GET` | `/bonds/{name}` | Devlet Tahvili ve Eurobond verileri. |
| `GET` | `/search?q={query}` | Hisse kodu veya şirket adına göre arama yapar. |

---

## 🛠 Kurulum ve Yayınlama (Deploy)

Bu proje **Render**, **Railway** veya herhangi bir VPS üzerinde çalışmaya hazırdır.

### Seçenek 1: Render.com (Önerilen)

1.  Bu projeyi GitHub hesabınıza **Fork** edin veya dosyaları yükleyin.
2.  [Render Dashboard](https://dashboard.render.com/)'a gidin.
3.  **New +** butonuna basıp **Web Service** seçin.
4.  GitHub reponuzu bağlayın.
5.  Aşağıdaki ayarları girin:
    *   **Runtime:** `Python 3`
    *   **Build Command:** `pip install -r requirements.txt`
    *   **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 10000`
6.  **Create Web Service** butonuna basın.

### Seçenek 2: Yerel Çalıştırma (Localhost)

```bash
# Gerekli paketleri yükleyin
pip install -r requirements.txt

# Sunucuyu başlatın
uvicorn main:app --reload
```
API şu adreste çalışacaktır: `http://127.0.0.1:8000`

---

## ⚠️ Yasal Uyarı

Bu API tarafından sağlanan veriler bilgilendirme amaçlıdır. Yatırım tavsiyesi değildir. Veriler kaynak kuruluşlardan (İş Yatırım, TradingView, KAP vb.) sağlanmakta olup doğruluk garantisi verilmez.

---
