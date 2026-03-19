# 📊 BorsaPy Ultimate API (v1.2.0 - Hybrid AI Engine)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green?style=for-the-badge&logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Hybrid_AI_Enabled-success?style=for-the-badge)

**BorsaPy Ultimate API**, Borsa İstanbul (BIST), VIOP ve Fon verilerini sunan **yüksek performanslı ve Hibrit AI destekli** bir finansal ağ geçididir. v1.2.0 sürümü ile Twitter'a bağımlılığı bitiriyor; KAP haberlerini ve teknik/temel verileri harmanlayan "Insight" motorunu sunuyoruz.

---

## 💎 v1.2.0 Hibrit AI Özellikleri

*   **🧠 Hibrit Insight Motoru:** `/analysis/{symbol}/insight` ucu ile hissenin **Teknik (RSI, MA), Temel (F/K, PD/DD) ve Haber (KAP)** verilerini tek bir potada eriterek **0-100 arası bir Güven Skoru** üretir.
*   **📡 Bağımsız KAP Analizi:** Twitter Auth bilgisi olmasa bile, en güncel KAP bildirimlerini okuyup sentiment (duyarlılık) analizi yapar. 
*   **📊 Gerçek Veri Odaklı:** "0" veya hatalı veri riskine karşı tüm finansal çarpanlar (P/E, P/B) ve hacim verileri doğrulanmıştır.
*   **🗓️ Global Ekonomik Ajanda:** `/market/economy/calendar` ile artık sadece Türkiye değil, dünya piyasalarındaki dev olayları da takip edebilirsiniz.

---

## 📡 API Uç Noktaları (Endpoints)

### 🧠 AI & Akıllı Analiz
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/analysis/{symbol}/insight` | **ULTIMATE:** Teknik + Temel + KAP Haber harmanlı 0-100 puanlı analiz. |
| `GET` | `/analysis/{symbol}/sentiment` | **Twitter:** Sosyal medya duyarlılık analizi (Opsiyonel Auth gerektirir). |
| `GET` | `/analysis/{symbol}` | **Teknik:** RSI, Supertrend ve Golden Cross sinyal motoru. |

### 📈 Hisse Senedi & Piyasa
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/stocks/{symbol}/dividends` | Şirketin geçmiş temettü ödemeleri. |
| `GET` | `/stocks/{symbol}/financials` | Gelir tablosu ve Bilanço özetleri. |
| `GET` | `/market/screener` | PD/DD, F/K ve Hacim içeren profesyonel tarayıcı. |
| `GET` | `/market/breadth` | BIST para girişi ve yükselen/düşen hacim dağılımı. |

### 💰 Fonlar (TEFAS & KAP)
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/funds/list` | Tüm aktif yatırım ve emeklilik fonları listesi. |
| `GET` | `/funds/{code}/estimated-return` | **Deep Scan:** Fonun PDF içeriğine göre anlık getiri tahmini. |

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
*   **API_KEY:** Yetkilendirme için gereklidir.
*   **TWITTER_AUTH_TOKEN & CT0:** Sadece sosyal medya sentiment analizi kullanılacaksa gereklidir. Insight motoru için **zorunlu değildir**.

---

## ⚠️ Yasal Uyarı
Bu yazılım tarafından sağlanan tüm veriler eğitim ve bilgilendirme amaçlıdır. **Kesinlikle yatırım tavsiyesi niteliği taşımaz.** AI skorları algoritmik tahminlerdir, son karar yatırımcının kendisine aittir.
