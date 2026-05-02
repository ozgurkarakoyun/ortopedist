# SEO Bakımı Timeout Düzeltmesi (v2)

## Sorun

İlk patch'te "AI ile Eksik Meta'ları Doldur" butonu **40 yazıyı tek istekte** işliyordu:
- Backend: 3-4 dakika boyunca AI çağırıyor
- Frontend: 60 saniye sonra Railway proxy timeout
- JS: boş response alıp "JSON.parse: unexpected character" hatası

## Çözüm

Endpoint **tekli** çalışacak şekilde bölündü:
- `/admin/seo-cleanup/missing-list` (GET): eksik yazıların listesini döner
- `/admin/seo-cleanup/fill-one/<id>` (POST): tek bir yazıyı işler (~3-5 sn)

JS yazıları **sırayla** çağırır, her biri için anlık ✅/❌ gösterir.
İlerleme: "İşleniyor: 17 / 40 — Yazı başlığı" gibi.

## Değişen 2 dosya

```
routes/admin.py                     (3 endpoint - missing-list, fill-one, fill-missing deprecated)
templates/admin/seo_cleanup.html    (yeni JS - sıralı işleme)
```

## Kurulum

```bash
cd /yol/to/ortopedist
unzip ~/Downloads/seo-fix-v2.zip -d /tmp/

cp /tmp/seo-fix-v2/routes/admin.py routes/admin.py
cp /tmp/seo-fix-v2/templates/admin/seo_cleanup.html templates/admin/seo_cleanup.html

git add routes/admin.py templates/admin/seo_cleanup.html
git commit -m "fix: SEO bakım butonu timeout sorununu çöz - tek tek işle"
git push
```

Railway redeploy bekle (~1-2 dk).

## Kullanım

Admin → 🔧 SEO Bakımı → "🤖 AI ile Eksik Meta'ları Doldur":
- Önce kaç yazı eksik bulduğunu söyler
- Sırayla her yazı için API çağrısı (~3-5 sn / yazı)
- Her yazıdan sonra ✅ veya ❌ ile sonuç görünür
- Tarayıcı sekmeyi açık bırak, kapama

40 yazı için tahmini süre: 3-4 dakika
40 yazı için tahmini maliyet: ~$0.50
