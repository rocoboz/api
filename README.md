# 📊 BorsaPy Ultimate API (v1.0.7 - Performance Edition)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Status](https://img.shields.io/badge/Status-Ultra--Fast-success)

**BorsaPy Ultimate API**, Borsa İstanbul (BIST), VIOP, Fonlar ve Makroekonomik verileri milisaniyeler içinde sunan, **yüksek performanslı ve simülasyon yetenekli** bir finansal ağ geçididir.

Bu sürüm (v1.0.7), veri çekme hızını optimize eden **Katmanlı Önbellek (Layered Cache)** ve ileri düzey **Emir Derinliği Simülasyonu** ile donatılmıştır.

---

## 🔥 v1.0.7 Yenilikleri

*   **⚡ Katmanlı Önbellek (Smart Cache):** Veriler oynaklıklarına göre 10sn, 60sn ve 24saatlik havuzlarda saklanarak gecikme (latency) minimize edildi.
*   **📊 `/stocks/{symbol}/depth` (Simüle Emir Derinliği):** Gerçek zamanlı borsa tahtasını taklit eden "Volume-at-Price" algoritması eklendi.
*   **🛡️ Bloklanma Koruması:** Veri sağlayıcılardan (İş Yatırım, KAP vb.) bloklanmayı önleyen akıllı istek yönetimi ve hata yakalama sistemi.
*   **🏢 KAP Şirket Detayları:** Hisse sorgularına otomatik olarak şirket sektör, pazar ve faaliyet özeti eklendi.

---

## 📡 API Uç Noktaları (Endpoints)

| Metod | Uç Nokta (Endpoint) | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/stocks/{symbol}` | Hisse fiyat, oranlar ve **KAP şirket detayları**. |
| `GET` | `/stocks/{symbol}/depth` | Simüle edilmiş "Emir Tahtası / Derinlik" verisi. |
| `GET` | `/stocks/{symbol}/disclosures` | Güncel KAP haberleri ve bildirim linkleri. |
| `GET` | `/funds/{code}/estimated-return` | **ELİT:** Fonun o günkü **tahmini getirisini** hesaplar. |
| `GET` | `/funds/screener` | TEFAS Fon tarama ve kategorik listeleme. |
| `GET` | `/analysis/{symbol}` | **Pro Analiz:** RSI, Supertrend ve Sinyal üretimi. |
| `GET` | `/market/screener` | Gelişmiş hisse tarama ve filtreleme motoru. |
| `GET` | `/viop/list` | VIOP kontratları (Hisse, Endeks, Döviz vadeli). |
| `GET` | `/market/economy/inflation` | Güncel Enflasyon (TÜFE/ÜFE) özet verisi. |
| `GET` | `/market/tax` | Yatırım araçları güncel stopaj (vergi) oranları. |
| `GET` | `/search/tweets` | Twitter/X sosyal duyarlılık araması. |
| `GET` | `/search` | Global arama (Hisse, Fon, VIOP). |

---

## 🔐 Güvenlik ve Dağıtım

### Kurulum (Local)
1.  `pip install -r requirements.txt`
2.  `uvicorn main:app --reload`

### Render / OnRender Dağıtımı
1.  Ortam Değişkenlerinde `API_KEY` tanımlayın.
2.  `TWITTER_AUTH_TOKEN` ve `TWITTER_CT0` ekleyerek sosyal aramayı aktif edin.

---

## ⚠️ Yasal Uyarı
Bu API tarafından sağlanan veriler bilgilendirme amaçlıdır. Yatırım tavsiyesi değildir.
