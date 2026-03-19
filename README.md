# 📊 BorsaPy Ultimate API (v1.1.0 - Ultimate Edition)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green?style=for-the-badge&logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Ultimate_Edition-success?style=for-the-badge)

**BorsaPy Ultimate API**, Borsa İstanbul (BIST), VIOP, Fonlar ve Makroekonomik verileri milisaniyeler içinde sunan, **yüksek performanslı ve AI destekli** bir finansal ağ geçididir. v1.1.0 sürümü ile artık sadece veri sunmakla kalmıyor, veriyi yorumlayan bir akıl sunuyor.

---

## 💎 v1.1.0 Ultimate Özellikler

*   **🧠 AI Sentiment Engine (Duyarlılık Analizi):** `/analysis/{symbol}/sentiment` uç noktası ile hisse hakkındaki sosyal medya ve haber akışını tarayarak **BULLISH (Boğa)** veya **BEARISH (Ayı)** skorlaması yapar.
*   **🗓️ Ekonomik Takvim (Financial Calendar):** `/market/economy/calendar` ile Türkiye ve Dünya piyasalarındaki kritik gelişmeleri (Faiz, Enflasyon, Fed) anlık takip edin.
*   **💰 Temettü Takvimi & Bilanço:** Şirketlerin geçmiş temettü ödemeleri ve detaylı gelir tabloları (Income Statement, Balance Sheet) artık bir endpoint uzaklığında.
*   **📡 Gelişmiş Teknik Sinyal v2:** RSI ve Supertrend'e ek olarak; **MA50/MA200 (Golden Cross) takibi** ve otomatik "STRONG BUY" sinyal motoru eklendi.
*   **🛡️ Zero-Ban Archive:** KAP ve PDF verileri için 24 saatlik statik cache kalkanı devam ediyor.

---

## 📡 API Uç Noktaları (Endpoints)

### 🧠 Akıllı Analiz & AI
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/analysis/{symbol}/sentiment` | **AI:** Sosyal medya duyarlılık skoru ve "Bullish/Bearish" etiketi. |
| `GET` | `/analysis/{symbol}` | **Pro:** RSI, Supertrend, MA50/200 ve "Strong Buy" sinyalleri. |

### 📈 Hisse Senedi & Finansallar
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/stocks/{symbol}/dividends` | Şirketin kuruşu kuruşuna tüm temettü geçmişi. |
| `GET` | `/stocks/{symbol}/financials` | Gelir tablosu, Bilanço veya Nakit Akışı özetleri. |
| `GET` | `/stocks/list` | Tüm aktif BIST şirketlerinin listesi. |
| `GET` | `/market/screener` | F/K, PD/DD, Hacim ve Piyasa Değeri bazlı gelişmiş tarama. |

### 💰 Fonlar (TEFAS & KAP)
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/funds/list` | TEFAS'taki tüm fonların listesi (`?fund_type=YAT` veya `EYF`). |
| `GET` | `/funds/{code}/estimated-return` | **AMİRAL GEMİSİ:** Fonun PDF içeriğini analiz ederek anlık getiri tahminler. |

### 🌍 Piyasa & Ajanda (Ultra-Pro)
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/market/economy/calendar` | **Yeni:** Küresel ve yerel ekonomik takvim (`?scope=today/week/month`). |
| `GET` | `/market/breadth` | BIST para akışı (Yükselen/Düşen Hacim Dağılımı). |
| `GET` | `/market/heatmap` | Sektörel değişim ve hacim odaklı ısı haritası. |

---

## 🔐 Güvenlik ve Kurulum

### Yerel Kurulum (Local Setup)
```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# API'yi başlat
uvicorn main:app --reload
```

### Sunucu Ayarları (Render / Docker)
*   **API_KEY:** `x-api-key` header üzerinden yetkilendirme sağlar.
*   **TWITTER_AUTH_TOKEN & CT0:** Sosyal duyarlılık analizi için gereklidir.

---

## ⚠️ Yasal Uyarı
Bu yazılım tarafından sağlanan tüm veriler eğitim ve bilgilendirme amaçlıdır. **Kesinlikle yatırım tavsiyesi niteliği taşımaz.** AI tarafından üretilen skorlar hatalı olabilir, yatırım kararlarınızı profesyonel danışmanlara danışarak alınız.
