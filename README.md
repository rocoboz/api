# BorsaPy Ultimate API

FastAPI tabanlı, BIST ve TEFAS odaklı, frontend dostu finans verisi katmanı. Bu sürümde API modüler yapıya taşındı, cache sistemi Redis-ready hale getirildi, route çakışmaları giderildi, null/0 semantiği netleştirildi ve Render deploy akışı production kullanıma uygunlaştırıldı.

## Mimari

- `main.py`: ince entrypoint
- `api_core/app.py`: FastAPI bootstrap, middleware, router registration
- `api_core/routes/*`: stocks, funds, market, economy, search, ops
- `api_core/services/*`: cache, security, providers, response, normalizers, analytics, observability
- `borsapy_lib/`: upstream kütüphane kopyası

## Temel Prensipler

- Eksik veya güvenilmez veri `null` döner.
- Gerçek sıfır olan hesap ve sayaçlar `0` olarak kalır.
- Pahalı endpointlerde cache ve rate limit uygulanır.
- Geriye uyumluluk korunur; çoğu eski endpoint ham JSON döndürmeye devam eder.
- Yeni meta ihtiyacı olan listelerde `envelope=true` ile `success/data/error/meta` zarfı alınabilir.

## Ortam Değişkenleri

- `API_KEY`: API anahtarı. `OPEN` ise public kullanım açılır.
- `REDIS_URL`: Redis bağlantısı. Boşsa memory cache fallback kullanılır.
- `RENDER_EXTERNAL_URL`: keep-alive self ping için Render URL’i.
- `REQUEST_TIMEOUT_SECONDS`: upstream timeout.
- `GZIP_MINIMUM_SIZE`: gzip eşiği.
- `CORS_ALLOW_ORIGINS`: virgülle ayrılmış origin listesi.
- `TWITTER_AUTH_TOKEN`: opsiyonel Twitter auth.
- `TWITTER_CT0`: opsiyonel Twitter ct0.
- `EVDS_API_KEY`: TCMB EVDS API anahtarı (zaman serisi verilerini indirmek için gereklidir).

## Yerel Çalıştırma

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Yerel doğrulama:

```bash
python -m py_compile main.py
python test_api.py
```

Varsayılan smoke test hedefi `http://127.0.0.1:8000` adresidir. Canlı ortamı test etmek için:

```bash
set API_BASE_URL=https://your-render-service.onrender.com
python test_api.py
```

## Endpoint Grupları

### Ops

- `/ping`
- `/ops/cache`
- `/ops/health`
- `/ops/ready`

### Stocks

- `/stocks/list`
- `/stocks/compare`
- `/stocks/{symbol}`
- `/stocks/{symbol}/history`
- `/stocks/{symbol}/depth`
- `/stocks/{symbol}/disclosures`
- `/stocks/{symbol}/dividends`
- `/stocks/{symbol}/financials`
- `/stocks/{symbol}/health`
- `/stocks/{symbol}/recommendations`
- `/stocks/{symbol}/holders`
- `/stocks/{symbol}/etfs`
- `/stocks/{symbol}/calendar`

### Funds

- `/funds/list`
- `/funds/screener`
- `/funds/{code}`
- `/funds/{code}/allocation`
- `/funds/{code}/allocation-history`
- `/funds/{code}/history`
- `/funds/{code}/estimated-return`

### Market / Analysis

- `/market/screener`
- `/market/breadth`
- `/market/heatmap`
- `/market/summary`
- `/market/scan`
- `/market/presets`
- `/market/presets/{preset_name}`
- `/market/news`
- `/home/highlights`
- `/analysis/{symbol}`
- `/analysis/{symbol}/sentiment`
- `/analysis/{symbol}/insight`

### Economy / Search

- `/market/economy/rates`
- `/market/economy/calendar`
- `/market/economy/inflation`
- `/market/tax`
- `/search`
- `/search/tweets`

### Crypto

- `/crypto/list`
- `/crypto/{symbol}`
- `/crypto/{symbol}/history`

### FX / Bank Rates

- `/fx/list`
- `/fx/gold/all`
- `/fx/{symbol}`
- `/fx/{symbol}/history`
- `/fx/{symbol}/bank-rates`
- `/fx/{symbol}/bank-rate/{bank}`
- `/fx/{symbol}/institution-rates`
- `/fx/{symbol}/institution-rate/{institution}`

### Bonds & Eurobonds

- `/bonds/list`
- `/bonds/risk-free-rate`
- `/bonds/{maturity}`
- `/eurobonds/list`
- `/eurobonds/{isin}`
- `/eurobonds/{isin}/history`

### EVDS (CBRT TCMB Data)

- `/evds/categories`
- `/evds/search`
- `/evds/datagroups`
- `/evds/series`
- `/evds/series/{code}`
- `/evds/series/{code}/history`
- `/evds/download`
- `/evds/dashboard`
- `/evds/announcements`

### Portfolio & Backtest

- `/portfolio/analysis` (POST)
- `/portfolio/rebalance` (POST)
- `/backtest/run` (POST)

## Response Contract

### Envelope kullanan endpointler

- `/ping`
- `/`
- `/ops/*`
- `/market/summary`
- `/home/highlights`
- `envelope=true` verilen liste/search endpointleri

Örnek:

```json
{
  "success": true,
  "data": [],
  "error": null,
  "meta": {
    "limit": 50,
    "offset": 0,
    "count": 50,
    "generated_at": "2026-03-21T21:00:00+03:00"
  }
}
```

### Geriye uyumlu ham endpointler

- Çoğu mevcut liste ve detay endpointi varsayılan olarak ham JSON döndürür.
- `funds/list`, `stocks/list`, `market/screener`, `search`, `stocks/compare` için `envelope=true` desteklenir.

## Cache ve Rate Limit

- Realtime cache: 30 saniye
- Market cache: 60 saniye
- Static cache: 24 saat
- Redis varsa shared cache kullanılır, yoksa memory fallback çalışır.
- Pahalı endpointler:
  - `/funds/{code}/estimated-return`
  - `/stocks/{symbol}/depth`
  - `/market/breadth`
- Bu endpointlerde limit daha sıkıdır.

## Nullable Alanlar

Aşağıdaki alanlar upstream kaynak boş verdiğinde `null` dönebilir:

- `risk_value`
- `price`
- `change`
- `daily_return`
- `return_ytd`
- `pe`
- `pddd`
- `market_cap`
- `volume`

Bu durum mapping hatası değil, veri kaynağının boş veya güvenilmez değer dönmesidir.

## Render Deploy

Bu repo `render.yaml` içerir. Önerilen kurulum:

1. GitHub’a push et
2. Render’da Blueprint deploy kullan
3. Web service + Redis service birlikte oluşsun
4. Env değerlerini doğrula
5. Deploy sonrası smoke test çalıştır

Start command:

```bash
gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 2 --threads 4 --timeout 120
```

## Deploy Sonrası Kontrol Listesi

- `/ping`
- `/ops/cache`
- `/stocks/list?limit=3&offset=0`
- `/funds/list?limit=3&offset=50`
- `/market/summary`
- `/search?q=THYAO`
- `/funds/TLY`
- `/stocks/THYAO/history?period=1mo&interval=1d`
- `/crypto/list?quote=TRY`
- `/fx/list`
- `/bonds/list`
- `/eurobonds/list?currency=USD`
- `/evds/categories`
- `/portfolio/analysis` (POST)
- `/backtest/run` (POST)

## Notlar

- Redis yoksa API çalışır, ama çoklu instance senaryosunda shared cache avantajı kaybolur.
- 1000 kullanıcı kapasitesi yalnız app koduna bağlı değildir; Render planı, upstream rate limit ve Redis kullanımı belirleyicidir.
- `borsapy_lib` upstream kaynaktan beslendiği için bazı veri boşlukları uygulama yerine kaynağa bağlı olabilir.
