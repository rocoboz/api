# FinansAPI v3.0 🚀

BIST (Borsa İstanbul), TEFAS Yatırım Fonları, TCMB, Döviz, Altın, Kripto Para ve Tahvil piyasaları için geliştirilmiş yüksek performanslı, anahtarsız ve modüler finansal veri katmanı.

---

## 🏗️ Proje Mimarisi

* **`main.py`**: Uygulama giriş noktası ve ASGI sunucu başlatıcısı.
* **`api_core/`**: FastAPI rotaları, önbellek stratejileri, rate limiting ve yanıt modelleri.
* **`finans_core/`**: Kamuya açık finansal veri kaynaklarını (KAP, İş Yatırım, TEFAS, TCMB, TradingView) normalize eden dahili veri motoru.
* **`frontend/`**: React, Vite ve TailwindCSS ile geliştirilmiş yapay zeka destekli çoklu ajan analiz paneli.

---

## ⚡ Hızlı Başlangıç

### 1. Yerel Kurulum

```bash
# Bağımlılıkları yükleyin
pip install -r requirements.txt

# API sunucusunu başlatın
uvicorn main:app --reload
```

Sunucu varsayılan olarak `http://127.0.0.1:8000` adresinde başlar.
* **Etkileşimli Swagger Dokümantasyonu:** `http://127.0.0.1:8000/docs`
* **Alternatif Dokümantasyon (ReDoc):** `http://127.0.0.1:8000/redoc`

### 2. Testleri Çalıştırma

```bash
# Yerel test
python test_api.py

# Canlı sunucuyu test etmek için
set API_BASE_URL=https://sunucu-adresiniz.onrender.com
python test_api.py
```

---

## ⚙️ Ortam Değişkenleri

Uygulama kamuya açık verilerle sıfır API anahtarıyla çalışacak şekilde tasarlanmıştır. İhtiyaca göre aşağıdaki değişkenler tanımlanabilir:

| Değişken | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `API_KEY` | `OPEN` | API güvenlik anahtarı. `OPEN` bırakıldığında genel kullanıma açıktır. |
| `REDIS_URL` | *(Boş)* | Redis bağlantı URL'i. Boş bırakılırsa bellek içi (in-memory) TTL önbellek kullanılır. |
| `REQUEST_TIMEOUT_SECONDS` | `30` | Harici veri istekleri için zaman aşımı süresi (saniye). |
| `CORS_ALLOW_ORIGINS` | `*` | İzin verilen CORS adresleri (virgülle ayrılmış). |
| `EVDS_API_KEY` | *(Opsiyonel)* | TCMB EVDS serilerini indirmek için kullanıcı anahtarı. |

---

## 📡 API Uç Noktaları

### 1. Sistem & Sağlık (`/ops`)
* `GET /ping` — Servis canlılık kontrolü.
* `GET /ops/health` — Sistem kaynakları ve önbellek sağlık durumu.
* `GET /ops/cache` — Bellek ve Redis önbellek istatistikleri.
* `GET /ops/ready` — Servis hazır olma durumu.

### 2. Hisse Senetleri (`/stocks`)
* `GET /stocks/list` — BIST şirketler listesi (sayfalama destekli).
* `GET /stocks/{symbol}` — Anlık fiyat, hacim ve şirket künyesi (Örn: `THYAO`).
* `GET /stocks/{symbol}/history` — Tarihsel grafik ve mum verileri (`period`, `interval`).
* `GET /stocks/{symbol}/health` — **Piotroski F-Score** ve finansal sağlık analizi (0-9 puan & derecelendirme).
* `GET /stocks/{symbol}/financials` — Bilanço ve gelir tablosu verileri.
* `GET /stocks/{symbol}/depth` — Anlık derinlik ve kademe verileri.
* `GET /stocks/{symbol}/dividends` — Geçmiş temettü ödemeleri ve verimleri.
* `GET /stocks/{symbol}/recommendations` — Hedef fiyatlar ve analist tavsiyeleri.
* `GET /stocks/{symbol}/holders` — Şirket ortaklık yapısı ve büyük pay sahipleri.
* `GET /stocks/{symbol}/etfs` — Hissede pozisyonu olan TEFAS fonları.
* `GET /stocks/{symbol}/disclosures` — Son KAP bildirimleri.
* `GET /stocks/{symbol}/calendar` — Bilanço açıklama takvimi.
* `GET /stocks/compare?symbols=THYAO,ASELS` — Çoklu hisse karşılaştırması.

### 3. TEFAS Yatırım Fonları (`/funds`)
* `GET /funds/list` — Tüm TEFAS fonlarının listesi.
* `GET /funds/{code}` — Fon anlık detayları, getiri oranları ve büyüklüğü.
* `GET /funds/{code}/allocation` — Güncel portföy varlık dağılımı (Hisse, Bono, Döviz vb.).
* `GET /funds/{code}/allocation-history` — Tarihsel portföy dağılım değişimi.
* `GET /funds/{code}/holdings` — **KAP portföy dağılım raporundan taranan hisse senedi sepeti ve ağırlıkları.**
* `GET /funds/{code}/history` — Tarihsel fon pay fiyatı grafiği.
* `GET /funds/{code}/estimated-return` — BIST seansı esnasında anlık tahmini günlük getiri.
* `GET /funds/screener` — Fon tipi ve getiri kriterlerine göre fon tarayıcı.

### 4. Piyasa, Taramalar & Hazır Stratejiler (`/market`)
* `GET /market/presets` — Hazır teknik tarama stratejileri listesi.
* `GET /market/presets/{preset_name}` — Hazır stratejiyi çalıştırır (`golden-cross`, `oversold`, `macd-bullish`, vb.).
* `GET /market/scan?universe=XU030&condition=rsi < 40` — Özel matematiksel tarama motoru.
* `GET /market/screener` — Temel ve teknik filtrelerle hisse tarama.
* `GET /market/breadth` — Piyasa genel genişliği (yükselen/düşen oranı).
* `GET /market/heatmap` — Sektörel getiri ısı haritası.
* `GET /market/summary` — Endeksler, en çok artanlar/azalanlar ve piyasa özeti.
* `GET /market/news` — Güncel BIST ve ekonomi haber akışı.
* `GET /analysis/{symbol}` — Otomatik teknik sinyal özeti.

### 5. Döviz & Altın Matrisi (`/fx`)
* `GET /fx/list` — Desteklenen para birimleri ve kurumlar.
* `GET /fx/gold/all` — **Tüm altın türleri matrisi** (Gram, 22 Ayar Bilezik, 18/14 Ayar, Çeyrek, Yarım, Tam, Ata, Gremse, Reşat, Ons).
* `GET /fx/{asset}` — Döviz veya altın anlık kuru (Örn: `USD`, `gram-altin`, `22-ayar-bilezik`).
* `GET /fx/{asset}/history` — Tarihsel döviz/altın grafiği.
* `GET /fx/{asset}/bank-rates` — Bankaların anlık alış-satış kurları ve makas farkları.
* `GET /fx/{asset}/institution-rates` — Kapalıçarşı ve serbest piyasa kurum kurları.

### 6. Kripto Para (`/crypto`)
* `GET /crypto/list` — BIST/TRY ve USDT bazlı kripto para çiftleri.
* `GET /crypto/{symbol}` — Anlık kripto fiyatı (Örn: `BTCTRY`).
* `GET /crypto/{symbol}/history` — Kripto para mum geçmişi.

### 7. Tahvil, Bono & Eurobond (`/bonds`)
* `GET /bonds/list` — Gösterge devlet tahvili faiz oranları.
* `GET /bonds/risk-free-rate` — Piyasa risksiz faiz oranı (RFR).
* `GET /eurobonds/list` — Türkiye Eurobond getirileri ve kupon oranları.

### 8. Ekonomi Takvimi & TCMB (`/market/economy`)
* `GET /market/economy/rates` — TCMB resmi kurları.
* `GET /market/economy/calendar` — Günlük/haftalık ekonomik takvim.
* `GET /market/economy/inflation` — TÜİK resmi TÜFE enflasyon oranları ve hesaplayıcı.
* `GET /market/tax` — Finansal enstrümanlar güncel stopaj tablosu.
* `GET /evds/categories` & `/evds/search` — TCMB EVDS veri kategorileri ve serileri.

### 9. Portföy Simülasyonu & Backtest (POST)
* `POST /portfolio/analysis` — Portföy risk metrikleri (Sharpe, Volatilite, Alfa, Beta).
* `POST /portfolio/rebalance` — Hedef ağırlıklara göre portföy dengeleme hesabı.
* `POST /backtest/run` — BIST hisseleri üzerinde teknik strateji simülasyonu.

---

## 💻 Yanıt Formatı (Response Structure)

İsteğe bağlı olarak liste uç noktalarında `envelope=true` parametresi gönderilerek standart zarf yapısı alınabilir:

```json
{
  "success": true,
  "data": [ ... ],
  "error": null,
  "meta": {
    "limit": 50,
    "offset": 0,
    "count": 50
  }
}
```

---

## 🔒 Güvenlik & Gizlilik
* Bu proje **açık kaynaklı ve kamuya açık (public)** çalışacak şekilde geliştirilmiştir.
* Kod tabanında hiçbir sabit token, şifre veya özel bağlantı barındırılmaz.
