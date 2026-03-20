# 📊 BorsaPy Ultimate API (v1.2.1 - Pro Sync Edition)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green?style=for-the-badge&logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Stable_v1.2.1-success?style=for-the-badge)

**BorsaPy Ultimate API**, Borsa İstanbul (BIST), VIOP ve TEFAS Fon verilerini milisaniyeler içinde sunan profesyonel bir finansal ağ geçididir. v1.2.1 "Pro Sync" sürümü ile frontend-backend uyumu ve veri derinliği en üst seviyeye taşınmıştır.

---

## 💎 v1.2.1 "Pro Sync" Yenilikleri

*   **🔍 Birleşik Arama (Unified Search):** Tek bir `/search` aramasıyla hem hisseleri hem de fonları (TP2, TLY vb.) anında bulabilirsiniz.
*   **📡 Sınırsız Veri Desteği:** `/list` uç noktalarına eklenen `limit` ve `offset` parametreleri ile 50 sınırlaması tarihe karıştı. Binlerce veriyi tek seferde veya sayfalayarak çekebilirsiniz.
*   **💰 Fon Detay Kartları:** `/funds/{code}` ile fonun TEFAS'taki yatırımcı sayısı, risk değeri ve tam portföy dağılımına anında erişim.
*   **🛡️ NaN Shield (Stabilite):** Yeni halka arzlar (MEYSU, MTRKS vb.) gibi RSA/MA verisi kısa olan sembollerde API artık asla çökmüyor, eksik veriyi `null` geçerek stabil kalıyor.

---

## 📡 API Uç Noktaları ve Kullanım Rehberi

### 🧠 Akıllı Analiz & AI
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/analysis/{symbol}/insight` | **Hibrit AI:** Teknik + Temel + KAP Haber harmanlı 0-100 puanlı analiz. |
| `GET` | `/analysis/{symbol}` | **Sinyal:** RSI, Golden Cross ve Supertrend teknik sinyalleri. |

### 📈 Hisse Senedi & Fonlar (Global)
| Metod | Uç Nokta | Örnek Parametreler | Açıklama |
| :--- | :--- | :--- | :--- |
| `GET` | `/stocks/{symbol}/history` | `?period=1mo` / `?period=1y` | Hissenin veya Fonun (3 harf) tarihsel fiyat dökümü. |
| `GET` | `/stocks/{symbol}` | `/stocks/THYAO` | Hisse canlı fiyatı ve detaylı KAP bilgileri. |
| `GET` | `/funds/{code}` | `/funds/TP2` | Fonun TEFAS detay kartı (Fiyat, Risk, Portföy). |
| `GET` | `/search` | `?q=THY` veya `?q=TP2` | **Akıllı Arama:** Hem hisseleri hem fonları beraber bulur. |

### 📋 Listeleme ve Sayfalama (Pagination)
**İpucu:** Tüm listeleme uç noktalarında `limit` (kaç adet?) ve `offset` (nereden başlasın?) kullanabilirsiniz.
*   `/stocks/list?limit=500` -> İlk 500 hisseyi listeler.
*   `/funds/list?fund_type=YAT&limit=300` -> Tüm Yatırım Fonlarını (YAT) listeler.
*   `/funds/list?fund_type=EYF&limit=200` -> Tüm Emeklilik Fonlarını (EYF) listeler.

---

## 🔐 Güvenlik ve Kurulum

### Yerel Kurulum (Local Setup)
```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# API'yi başlat (Local: http://127.0.0.1:8000)
uvicorn main:app --reload
```

### Sunucu Ayarları (Render / Docker)
*   **API_KEY:** `x-api-key` header'ı üzerinden zorunludur.
*   **TWITTER_AUTH_TOKEN & CT0:** Sadece `/analysis/{symbol}/sentiment` (Sosyal Medya Analizi) uç noktası için opsiyoneldir. **Insight ve Temel özellikler için zorunlu değildir.**

---

## ⚠️ Yasal Uyarı
Bu yazılım tarafından sağlanan tüm veriler eğitim ve bilgilendirme amaçlıdır. **Kesinlikle yatırım tavsiyesi niteliği taşımaz.** AI tahminleri hatalı olabilir, yatırım kararlarınızı profesyonel danışmanlara danışarak alınız.
