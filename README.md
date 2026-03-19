# 📊 BorsaPy Ultimate API (v1.0.7 - Performance Edition)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green?style=for-the-badge&logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Ultrafast-success?style=for-the-badge)

**BorsaPy Ultimate API**, Borsa İstanbul (BIST), VIOP, Fonlar ve Makroekonomik verileri milisaniyeler içinde sunan, **yüksek performanslı ve simülasyon yetenekli** bir finansal ağ geçididir.

Bu sürüm (v1.0.7), veri çekme hızını optimize eden **Katmanlı Önbellek (Layered Cache)**, ileri düzey **Fon İçerik Analizi (Deep Scan)** ve **Dinamik Twitter Oturumu** desteği ile donatılmıştır.

---

## 🔥 v1.0.7 Pro Özellikler

*   **⚡ Katmanlı Önbellek (Smart Cache):** Veriler oynaklıklarına göre 10sn, 60sn ve 24saatlik havuzlarda saklanarak gecikme (latency) minimize edildi.
*   **📡 Fon Derin Tarama (Deep Scan):** `/funds/{code}/estimated-return` uç noktası artık fonun **KAP üzerindeki gerçek portföy dağılımını (PDF)** okuyarak, içindeki hisselerin anlık performansına göre tahmin üretir.
*   **📊 Market Breadth (Piyasa Genişliği):** Borsada yükselen/düşen hisse oranlarını (A/D Ratio) anlık hesaplar.
*   **🐦 Dinamik Twitter Auth:** API kullanıcıları artık kendi `auth_token` ve `ct0` bilgilerini göndererek kendi limitleriyle sosyal arama yapabilirler.
*   **🔥 Isı Haritası (Heatmap):** Sektörel performansları ve hacim şampiyonlarını gruplayan yeni veri motoru.

---

## 📡 API Uç Noktaları (Endpoints)

### 📈 Hisse Senedi & Analiz
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/stocks/{symbol}` | Anlık fiyat, oranlar ve **KAP şirket detayları**. |
| `GET` | `/stocks/{symbol}/depth` | Simüle edilmiş **Volume-Profile** bazlı derinlik verisi. |
| `GET` | `/stocks/{symbol}/history` | Geçmiş fiyat verileri (O-H-L-C-V). |
| `GET` | `/analysis/{symbol}` | **Teknik Sinyal:** RSI, Supertrend ve Al/Sat durumu. |
| `GET` | `/market/screener` | Gelişmiş filtreleme (F/K, PD/DD, Değişim). |

### 💰 Fonlar (TEFAS & KAP)
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/funds/{code}/estimated-return` | **AMİRAL GEMİSİ:** Fonun gerçek içeriğini (PDF) analiz ederek anlık getiri tahminler. |
| `GET` | `/funds/screener` | TEFAS kategori bazlı fon tarama. |
| `GET` | `/funds/compare` | Birden fazla fonu karşılaştırma. |

### 🌍 Piyasa & Makro (Ultra-Pro)
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/market/breadth` | BIST Genel Yükselen/Düşen (Advance/Decline) istatistikleri. |
| `GET` | `/market/heatmap` | Sektörel değişim ve hacim odaklı ısı haritası verisi. |
| `GET` | `/market/economy/inflation` | Güncel Enflasyon (TÜFE/ÜFE) özeti. |
| `GET` | `/market/economy/rates` | TCMB güncel faiz oranları. |
| `GET` | `/market/tax` | Yatırım araçları stopaj tablosu. |

### 🔍 Sosyal & Global Arama
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/search/tweets` | **Dinamik:** Twitter duyarlılık araması (Opsiyonel: `auth_token`, `ct0`). |
| `GET` | `/search` | Global varlık araması (Hisse, Fon, VIOP, Kripto). |

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
Sunucunuzda şu **Çevre Değişkenlerini (Env Vars)** tanımlayarak tam yetenekleri açabilirsiniz:
*   `API_KEY`: Uç noktalara erişim şifreniz (`x-api-key` header).
*   `TWITTER_AUTH_TOKEN` & `TWITTER_CT0`: Varsayılan sosyal arama hesabı.

---

## ⚠️ Yasal Uyarı
Bu yazılım tarafından sağlanan tüm veriler eğitim ve bilgilendirme amaçlıdır. **Kesinlikle yatırım tavsiyesi niteliği taşımaz.** Verilerin doğruluğu ve gecikmesinden doğacak sorumluluk kullanıcıya aittir.
