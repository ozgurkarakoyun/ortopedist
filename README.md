# WordPress İçerik Migrasyonu Patch'i (v2 — WXR XML desteği)

Bu paket admin paneline iki migrasyon yöntemi ekler:
1. **WXR XML upload** (önerilen) — WordPress'in resmi export dosyasını yükle
2. **URL scrape** (yedek) — sitemap+RSS taraması

## Değişen / yeni dosyalar

```
services/wxr_importer.py            (YENİ - WXR XML parser)
routes/admin.py                     (genişletildi - 3 yeni endpoint)
templates/admin/migrate.html        (sekme yapısı: XML / URL)
templates/admin/base.html           (sidebar'a "İçerik Aktar" linki)
templates/admin/dashboard.html      (dashboard'a migrasyon kartı)
```

## Kurulum

```bash
cd /yol/to/ortopedist-blog
unzip ~/Downloads/migrate-patch.zip -d /tmp/

cp /tmp/migrate-patch/routes/admin.py routes/admin.py
cp /tmp/migrate-patch/services/wxr_importer.py services/wxr_importer.py
cp /tmp/migrate-patch/templates/admin/migrate.html templates/admin/migrate.html
cp /tmp/migrate-patch/templates/admin/base.html templates/admin/base.html
cp /tmp/migrate-patch/templates/admin/dashboard.html templates/admin/dashboard.html

git add routes/admin.py services/wxr_importer.py templates/admin/
git commit -m "feat: WXR XML import + bootstrap admin"
git push
```

Railway otomatik redeploy eder (~1-2 dk).

## Kullanım — WXR Yöntemi (Önerilen)

1. WordPress.com → **Araçlar → Dışa Aktar** → tüm içerik → XML indir
2. Yeni site → admin → **📥 İçerik Aktar** → **WXR Yükle** sekmesi
3. XML dosyasını seç → **Yükle ve Aktar**
4. ~30 saniyede tüm yazılar gelir; her yazının ✅ durumu görünür
