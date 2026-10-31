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
# Çevrimdışı sözleşme testleri (ağ erişimi gerektirmez)
.venv/Scripts/python.exe tests/test_fx_contract.py
.venv/Scripts/python.exe tests/test_portfolio_contract.py

# Yerel entegrasyon testi
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
| `REQUEST_TIMEOUT_SECONDS` | `20` | HTTP isteği için üst süre (saniye). |
| `PROVIDER_TIMEOUT_SECONDS` | `15` | Veri sağlayıcısına yapılan tek istek için zaman aşımı (saniye). |
| `CORS_ALLOW_ORIGINS` | `*` | İzin verilen CORS adresleri (virgülle ayrılmış). |
| `EVDS_API_KEY` | *(Opsiyonel)* | TCMB EVDS serilerini indirmek için kullanıcı anahtarı (`EVDS_KEY` de kabul edilir). |
| `DOVIZCOM_TOKEN` | *(Opsiyonel)* | doviz.com için yedek Bearer anahtarı. Tanımlı değilse token siteden taranır ve yoksa istek anahtarsız gönderilir. |
| `CACHE_WARMER_ENABLED` | `0` | Açılırsa arka plan önbellek ısıtıcısı çalışır. Ücretsiz Render planında varsayılan olarak kapalıdır. |
| `KEEP_ALIVE_ENABLED` | `0` | Açılırsa servis kendisine periyodik ping atar. Ücretsiz plan kotasını tüketir. |

### Render ücretsiz plan notları

* Örnek başına 512 MB bellek, 0,1 vCPU ve ayda 750 örnek saati vardır. `render.yaml` bu nedenle **tek Gunicorn işçisi** ile çalışır; eşzamanlılık G/Ç bekleyen isteklerde iş parçacığı havuzundan gelir.
* 15 dakika istek almazsa servis uykuya geçer; ilk istek 30-60 saniye sürebilir.
* Giden IP yurt dışındadır. TCMB, EVDS, TEFAS ve KAP gibi Türkiye merkezli kaynaklar zaman zaman yavaşlayabilir veya isteği reddedebilir. `GET /ops/providers` hangi kaynağın erişilebilir olduğunu ölçer.
* Önbellek bellek içidir; yeniden başlatmada sıfırlanır. Kalıcı disk ve Redis ücretsiz planda yoktur.

---

## 📡 API Uç Noktaları

### 1. Sistem & Sağlık (`/ops`)
* `GET /ping` — Servis canlılık kontrolü.
* `GET /ops/health` — Sistem kaynakları ve önbellek sağlık durumu.
* `GET /ops/cache` — Bellek ve Redis önbellek istatistikleri.
* `GET /ops/ready` — Servis hazır olma durumu.
* `GET /ops/providers` — canlidoviz, doviz.com, TCMB, EVDS, TEFAS, TradingView, BtcTurk, KAP ve Borsa İstanbul erişilebilirlik testi (durum kodu ve gecikme ile).

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
* `GET /stocks/movers` — **Günün en çok yükselen (gainers), düşen (losers) ve en hacimli hisseleri.**
* `GET /stocks/dividends/top` — **BIST en yüksek temettü verimine sahip şirketler sıralaması.**
* `GET /stocks/dividends/calendar` — **BIST temettü dağıtım takvimi ve net ödeme tutarları.**
* `GET /stocks/indices/{code}` — **BIST 30, BIST 50, BIST 100 bileşen hisseleri ve canlı fiyatları** (Örn: `/stocks/indices/xu030`).
* `GET /stocks/sectors` — **BIST sektör listesi ve endeks kodları** (Banka, Sanayi, Holding, Teknoloji vb.).
* `GET /stocks/sectors/{sector}` — **Sektöre ait hisseler ve anlık fiyatları** (Örn: `/stocks/sectors/banka`).

### 3. TEFAS Yatırım Fonları (`/funds`)
* `GET /funds/list` — Tüm TEFAS fonlarının listesi.
* `GET /funds/top?period=1y` — **En çok kazandıran şampiyon fonlar** (1m, 3m, 6m, ytd, 1y).
* `GET /funds/{code}` — Fon anlık detayları, getiri oranları ve büyüklüğü.
* `GET /funds/{code}/allocation` — Güncel portföy varlık dağılımı (Hisse, Bono, Döviz vb.).
* `GET /funds/{code}/allocation-history` — Tarihsel portföy dağılım değişimi.
* `GET /funds/{code}/holdings` — **KAP portföy dağılım raporundan taranan hisse senedi sepeti ve ağırlıkları.**
* `GET /funds/{code}/history` — Tarihsel fon pay fiyatı grafiği.
* `GET /funds/{code}/estimated-return` — BIST seansı esnasında anlık tahmini günlük getiri.
* `GET /funds/screener` — Fon tipi ve getiri kriterlerine göre fon tarayıcı.

### 4. Piyasa, Taramalar & Hazır Stratejiler (`/market`)
* `GET /market/overview` — **Tek ekranda tam piyasa özeti** (BIST endeksleri, Dolar/Euro, Altın, Seans durumu ve Günün yıldızları).
* `GET /market/status` — **BIST canlı seans durumu** (Açık/Kapalı, seans aşaması ve çalışma saatleri).
* `GET /market/ipo` — **BIST Halka Arz (IPO) takvimi** (Aktif, yaklaşan ve tamamlanan halka arzlar).
* `GET /market/presets` — Hazır teknik tarama stratejileri listesi.
* `GET /market/presets/{preset_name}` — Hazır stratejiyi çalıştırır (`golden-cross`, `oversold`, `macd-bullish`, vb.).
* `GET /market/scan?universe=XU030&condition=rsi < 40` — Özel matematiksel tarama motoru.
* `GET /market/screener` — Temel ve teknik filtrelerle hisse tarama.
* `GET /market/breadth` — Piyasa genel genişliği (yükselen/düşen oranı).
* `GET /market/heatmap` — Sektörel getiri ısı haritası.
* `GET /market/summary` — Endeksler, en çok artanlar/azalanlar ve piyasa özeti.
* `GET /market/news` — Güncel BIST ve ekonomi haber akışı.
* `GET /analysis/{symbol}` — Otomatik teknik sinyal özeti.
* `GET /analysis/{symbol}/indicators` — **Detaylı matematiksel teknik göstergeler** (RSI, MACD, Bollinger, EMA/SMA, Supertrend).

### 5. Döviz & Altın Matrisi (`/fx`)
* `GET /fx/list` — Desteklenen para birimleri ve kurumlar.
* `GET /fx/assets` — **Varlık kataloğu**: para birimleri ile altın, gümüş, platin ve enerji ürünlerinin saflık, ağırlık ve kaynak kimlikleri. `kind=gold` gibi filtre kabul eder.
* `GET /fx/convert?from=USD&to=TRY&amount=100` — **Canlı döviz, altın ve TL çevirici / hesap makinesi** (Örn: USD, EUR, gram-altin, ceyrek-altin).
* `GET /fx/gold/all` — **Altın matrisi** (Gram, Has, 22 Ayar Bilezik, 18/14 Ayar, Çeyrek, Yarım, Tam, Cumhuriyet, Ata, Gremse, Reşat, Ons). Fiyatlar önce canlı kotasyondan alınır; yalnızca kotasyon alınamazsa `source: "formula"` etiketiyle gram altından hesaplanır.
* `GET /fx/quotes?symbols=USD,gram-altin,ons-altin` — **Toplu fiyat sorgusu**; en fazla 30 varlık, tek istekte.
* `GET /fx/{asset}` — Döviz veya altın anlık kuru (Örn: `USD`, `gram-altin`, `22-ayar-bilezik`). Varsayılan `quote=TRY`; `quote=SOURCE` kaynak para birimini döndürür. `ons-altin` Türk lirasına çevrilir, `ons-altin-usd` veya `quote=SOURCE` Amerikan doları verir.
* `GET /fx/{asset}/history?period=1mo&quote=TRY&envelope=true` — Tarihsel döviz/altın grafiği. Her satırda `date` alanı bulunur; ons serisi varsayılan olarak Türk lirasına çevrilir ve dönüşüm bilgisi zarf içinde raporlanır.
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
* `GET /market/economy/rates` — TCMB politika faizi, gecelik koridor ve geç likidite penceresi oranları.
* `GET /market/economy/calendar` — Günlük/haftalık ekonomik takvim.
* `GET /market/economy/inflation` — Son açıklanan TÜFE ve ÜFE oranları (hesaplayıcı değil, özet).
* `GET /market/tax` — Finansal enstrümanlar güncel stopaj tablosu.
* `GET /evds/categories` & `/evds/search` — TCMB EVDS veri kategorileri ve serileri.

### 9. Finansal Hesaplayıcılar & Simülatör (`/calculator`)
* `GET /calculator/compound?initial=10000&monthly=2500&years=5&annual_rate=40` — **Bileşik getiri ve düzenli birikim büyüme simülatörü** (Yıllık döküm ve toplam kâr analizi).

### 10. Portföy Simülasyonu & Backtest (POST)
* `POST /portfolio/analysis` — Portföy analizi: güncel değer, maliyet, kâr/zarar, varlık dağılımı, değer geçmişi ve risk metrikleri (yıllık getiri, volatilite, Sharpe, Sortino, maksimum düşüş, Beta, Alfa).
* `POST /portfolio/rebalance` — Hedef ağırlıklara göre sapma ve dengeleme planı.
* `POST /backtest/run` — BIST hisseleri üzerinde teknik strateji simülasyonu.

Portföy istek gövdesi:

```json
{
  "holdings": [
    {
      "symbol": "gram-altin",
      "shares": 10,
      "cost": 5000,
      "asset_type": "fx",
      "purchase_date": "2026-01-15"
    }
  ],
  "benchmark": "XU100",
  "period": "1y",
  "risk_free_rate": null
}
```

Sözleşme notları:
* `asset_type` yalnızca `stock`, `fx`, `crypto`, `fund` değerlerini alır; başka bir değer **HTTP 422** döndürür. Fonlar için açıkça `"fund"` gönderilmelidir.
* `purchase_date` `YYYY-MM-DD` biçiminde veya `null` olabilir. `null` ise varlık tüm geçmiş boyunca elde tutulmuş kabul edilir. Geçersiz tarih **HTTP 422** döndürür.
* Değer geçmişi, farklı işlem takvimlerini ileri doldurma ile hizalar. Tüm varlıkların kotasyonu bulunan ilk tarihten başlar; eksik varlıkla toplanan kısmi portföy değerleri geçmişe ve risk metriklerine dahil edilmez.
* Risksiz faiz isteğe bağlıdır. Gönderilmezse 10 yıllık devlet tahvili getirisi kullanılır ve `risk_free_rate_source` alanı `10y_bond` olur. Oran alınamazsa değer `null` ve kaynak `unavailable` döner; Sharpe, Sortino ve Alfa hesaplanmaz.
* Yıllıklandırma 252 işlem günü varsayımı yerine gözlenen takvim aralığına göre yapılır.
* Analiz veya dengeleme sırasında beklenmeyen bir hata oluşursa **HTTP 500** ve açıklayıcı `detail` döndürülür.

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
* Kod tabanında sabit token veya şifre bulunmaz. doviz.com anahtarı yalnızca `DOVIZCOM_TOKEN` ortam değişkeninden okunur.
* TEFAS ve İş Yatırım isteklerinde TLS sertifika doğrulaması açıktır.
* `CORS_ALLOW_ORIGINS=*` iken tarayıcı kimlik bilgisi paylaşımı otomatik olarak kapatılır.
