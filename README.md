# BorsaPy Ultimate API

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green?style=for-the-badge&logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Stable-success?style=for-the-badge)

`BorsaPy Ultimate API`, Borsa Istanbul, TEFAS ve seçili piyasa verilerini frontend dostu bir FastAPI katmanında sunar. Bu sürümde dashboard entegrasyonu, özet endpointleri ve daha düzenli arama/screener davranışı iyileştirildi.

---

## Öne Çıkanlar

- Birleşik arama: `/search` artık hisse, fon ve eşleşen endeksleri tek çağrıda dönebilir.
- Dashboard özetleri: `/market/summary` ve `/home/highlights` ile frontend tek uçtan özet veri çekebilir.
- Daha esnek screener: `/market/screener` artık `limit`, `offset`, `sort`, `direction` parametrelerini destekler.
- Fon geçmişi: `/funds/{code}/history` ile fon fiyat eğrisi ayrı endpointten alınabilir.
- Tutarlı base responses: `/ping` ve `/` endpointleri `success/data/error/meta` zarfı döndürür.

---

## Temel Endpointler

### Analiz

| Method | Endpoint | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/analysis/{symbol}` | RSI, MA ve sinyal verileri |
| `GET` | `/analysis/{symbol}/insight` | Hibrit teknik + temel + haber skoru |
| `GET` | `/analysis/{symbol}/sentiment` | Twitter/X duyarlılık analizi |

### Hisse ve Fon

| Method | Endpoint | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/stocks/{symbol}` | Hisse özet ve KAP detayları |
| `GET` | `/stocks/{symbol}/history` | Hisse veya 3 harfli fon için fiyat geçmişi |
| `GET` | `/stocks/{symbol}/depth` | Simüle order-flow / depth görünümü |
| `GET` | `/stocks/{symbol}/dividends` | Temettü geçmişi |
| `GET` | `/stocks/{symbol}/financials` | Finansal tablolar |
| `GET` | `/funds/list` | Sayfalanabilir fon listesi |
| `GET` | `/funds/{code}` | Fon detay kartı |
| `GET` | `/funds/{code}/history` | Fon geçmiş fiyat eğrisi |
| `GET` | `/funds/{code}/estimated-return` | Tahmini günlük getiri ve dağılım |

### Piyasa ve Dashboard

| Method | Endpoint | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/market/screener` | Hisse tarayıcı verisi |
| `GET` | `/market/breadth` | Advance/decline görünümü |
| `GET` | `/market/heatmap` | Isı haritası için sektör bazlı veri |
| `GET` | `/market/summary` | Dashboard için birleşik özet veri |
| `GET` | `/home/highlights` | Öne çıkan hisseler ve fonlar |
| `GET` | `/market/economy/inflation` | Enflasyon verisi |
| `GET` | `/market/economy/rates` | TCMB faiz oranları |
| `GET` | `/market/economy/calendar` | Ekonomik takvim |
| `GET` | `/market/tax` | Stopaj / vergi tablosu |

### Arama

| Method | Endpoint | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/search?q=THY` | Hisse, fon ve endeks eşleşmeleri |
| `GET` | `/search/tweets?q=THYAO` | Twitter/X araması |

---

## Parametreler

### `/market/screener`

- `limit`: Kaç kayıt döneceği
- `offset`: Sayfalama başlangıcı
- `sort`: Sıralanacak kolon (`change`, `price`, `volume`, `pe`, `pddd`, `market_cap`)
- `direction`: `asc` veya `desc`

Örnek:

```bash
/market/screener?limit=20&offset=0&sort=change&direction=desc
```

### `/funds/list`

- `fund_type`: `YAT`, `EYF` vb.
- `limit`
- `offset`

Örnek:

```bash
/funds/list?fund_type=YAT&limit=100&offset=0
```

---

## Response Notları

- `/ping` ve `/` artık şu zarfı kullanır:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

- Diğer mevcut endpointlerin büyük bölümü geriye uyumluluk için ham JSON döndürmeye devam eder.
- Frontend bu sürümde hem zarf yapısını hem ham response yapısını tolere edecek şekilde tasarlanmıştır.

---

## Yerel Kurulum

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Yerel test:

```bash
python -m py_compile main.py
```

---

## Render Deploy

- Bu repo GitHub'a pushlandıktan sonra Render üzerinde manuel deploy tetiklenmelidir.
- Canlı API adresi:

```text
https://your-render-service.onrender.com/
```

- Deploy sonrası kontrol edilmesi önerilen uçlar:

```text
/ping
/market/summary
/home/highlights
/search?q=THY
```

---

## Yasal Uyarı

Bu API tarafından sunulan veriler bilgilendirme amaçlıdır. Yatırım tavsiyesi niteliği taşımaz.
