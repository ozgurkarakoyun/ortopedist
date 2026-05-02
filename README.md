# Google Analytics 4 Entegrasyonu

GA4 tracking script'ini head içine ekler. ID env var'dan okunur.

## Özellikler

- ✅ ID env var'dan: `GA_MEASUREMENT_ID`
- ✅ Admin paneli ve API yollarında GA YOK (kendi gezişlerini sayma)
- ✅ IP anonimizasyonu açık (KVKK uyumlu)
- ✅ Async yükleme (sayfa hızını etkilemez)

## Değişen 2 dosya

```
app.py                  (context'e ga_measurement_id eklendi)
templates/base.html     (head içine GA4 script blok)
```

## Kurulum

```bash
cd /yol/to/ortopedist
unzip ~/Downloads/ga4-patch.zip -d /tmp/

cp /tmp/ga4-patch/app.py app.py
cp /tmp/ga4-patch/templates/base.html templates/base.html

git add app.py templates/base.html
git commit -m "feat: Google Analytics 4 integration"
git push
```

## Railway Variables

Web service → Variables → +New:

```
GA_MEASUREMENT_ID=G-7237GFWNT7
```

## Doğrulama

Railway redeploy bittikten sonra:

1. `https://ortopedist.blog` aç
2. Sağ tık → "Sayfa kaynağını görüntüle"
3. Ctrl+F → "G-7237GFWNT7" ara
4. Bulmali → `<script async src="https://www.googletagmanager.com/gtag/js?id=G-7237GFWNT7">`

5. Sonra GA4'e dön: https://analytics.google.com
6. **Realtime** raporuna git
7. Başka bir sekmede siteyi aç
8. ~30 saniye içinde "1 user in last 30 minutes" görmeli

NOT: Admin paneli ziyaretleri sayılmaz (kendi gezişlerini istatistiğe karıştırma).
NOT: ÜLke verileri, en çok okunan yazılar, mobil/desktop oranı gibi tüm normal GA4 metrikleri çalışır.
