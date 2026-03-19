# 📊 BorsaPy Ultimate API (v1.0.9 - Ultimate Flow)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green?style=for-the-badge&logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Zero_Ban_Archive-success?style=for-the-badge)

**BorsaPy Ultimate API**, Borsa İstanbul (BIST), VIOP, Fonlar ve Makroekonomik verileri milisaniyeler içinde sunan, **yüksek performanslı ve simülasyon yetenekli** bir finansal ağ geçididir. En son sürüm (v1.0.9), "Ban-Proof" (Engellenemez) mimari ve zenginleştirilmiş veri seti ile donatılmıştır.

---

## 🛡️ v1.0.9 Yeni Nesil Özellikler

*   **🛡️ Zero-Ban Archive (Süper Cache):** KAP PDF indirme ve Şirket Künye sorguları gibi "ağır" işlemler **24 saatlik Static Cache**'e alındı. Bu sayede hedef sitelerin Firewall engellerine (Ban) takılma riski %99 azaltıldı.
*   **📊 Zenginleştirilmiş Veri Seti:** `/market/screener` artık sadece fiyat değil; **Hacim, Günlük Değişim %, PD/DD (PB Ratio) ve Piyasa Değeri** verilerini de döndürüyor.
*   **💸 Para Giriş-Çıkış Analizi:** `/market/breadth` artık yükselen/düşen hisse gruplarının **toplam Hacim (Volume)** miktarlarını da veriyor. Gerçek para hareketini takip etmek için ideal!
*   **📡 Fon Derin Tarama (Deep Scan v2):** `/funds/{code}/estimated-return` uç noktası, fonun KAP üzerindeki en güncel PDF sepetini okur, içeriği 24 saat hafızada tutar ve hisselerin anlık borsa performansına göre saniyelik getiri tahmini yapar.
*   **📄 Tam Fon Listesi:** `/funds/list` ile TEFAS üzerindeki tüm aktif fonların detaylı listesi (`fund_type` bazlı filtreleme ile) çekilebilir.

---

## 📡 API Uç Noktaları (Endpoints)

### 📈 Hisse Senedi & Analiz
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/stocks/list` | Tüm aktif BIST şirketlerinin listesi. |
| `GET` | `/stocks/{symbol}` | Anlık fiyat ve **24 saat cache'li KAP şirket künyesi**. |
| `GET` | `/stocks/{symbol}/depth` | Simüle edilmiş **Volume-Profile** bazlı derinlik verisi. |
| `GET` | `/market/screener` | **V2:** F/K, PD/DD, Hacim, Piyasa Değeri ve Değişim dahil tam tarama. |
| `GET` | `/analysis/{symbol}` | **Teknik Sinyal:** RSI, Supertrend durumu. |

### 💰 Fonlar (TEFAS & KAP)
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/funds/list` | TEFAS'taki tüm fonların listesi (`?fund_type=YAT` veya `EYF`). |
| `GET` | `/funds/{code}/estimated-return` | **AMİRAL GEMİSİ:** Fonun PDF içeriğini analiz ederek anlık getiri tahminler. |
| `GET` | `/funds/screener` | Getiri bazlı fon tarama ve sıralama motoru. |
| `GET` | `/funds/compare` | Birden fazla fonu (Örn: `TLY,PHE,TFA`) karşılaştırma. |

### 🌍 Piyasa & Makro (Ultra-Pro)
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/market/breadth` | **Pro:** Yükselen/Düşen grupların **Hacim (Para akışı)** dağılımı. |
| `GET` | `/market/heatmap` | Sektörel değişim ve hacim odaklı ısı haritası verisi. |
| `GET` | `/market/economy/inflation` | Güncel Enflasyon (TÜFE/ÜFE) özeti. |
| `GET` | `/market/economy/rates` | TCMB güncel faiz oranları. |

### 🔍 Sosyal & Global Arama
| Metod | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/search/tweets` | Twitter/X hisse duyarlılık araması (Dinamik Auth destekli). |
| `GET` | `/search` | Global varlık araması (Hisse, Fon, VIOP, Kripto, Döviz). |

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
*   `API_KEY`: Uç noktalara erişim şifreniz (`x-api-key` header). "OPEN" yapılırsa şifresiz açılır.
*   `TWITTER_AUTH_TOKEN` & `TWITTER_CT0`: Sosyal arama için oturum bilgileri.

---

## ⚠️ Yasal Uyarı
Bu yazılım tarafından sağlanan tüm veriler eğitim ve bilgilendirme amaçlıdır. **Kesinlikle yatırım tavsiyesi niteliği taşımaz.** Verilerin doğruluğu ve gecikmesinden doğacak sorumluluk kullanıcıya aittir.
