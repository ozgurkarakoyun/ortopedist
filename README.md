# SEO Meta Düzeltmeleri

Tespit edilen 3 SEO sorununu çözer:
1. Bazı yazılarda `<title>` etiketinde "None — Ortopedist" yazıyordu
2. Ana sayfa kartlarında bazı yazıların özetinde "None" string'i görünüyordu
3. Open Graph ve JSON-LD meta description'ları boştu

## Yaptığı

### Şablon tarafı (kalıcı çözüm)
- Yeni Jinja filter `|clean`: "None"/"null"/"undefined" string'lerini boş kabul eder
- Yeni Jinja filter `|smart_description`: meta_description → excerpt → içeriğin ilk 160 karakterine kadar otomatik fallback yapar
- Tüm public şablonlar bu filter'ı kullanır

### Admin tarafı (mevcut bozuk veriyi düzelt)
- Yeni sayfa: `/admin/seo-cleanup` — sol sidebar'da "🔧 SEO Bakımı" linki
- 1. Adım: "None" string'lerini gerçek NULL'a çevir (ücretsiz, anlık)
- 2. Adım: AI ile eksik meta_description ve excerpt'leri toplu doldur

## Değişen Dosyalar

```
app.py                              (clean + smart_description filter eklendi)
routes/admin.py                     (3 yeni endpoint: seo_cleanup_page, normalize, fill_missing)
templates/admin/base.html           (sidebar'a "SEO Bakımı" linki)
templates/admin/seo_cleanup.html    (YENİ - bakım arayüzü)
templates/public/index.html         (smart_description filter'ı kullanır)
templates/public/post.html          (clean + smart_description filter'ı)
templates/public/search.html        (smart_description filter'ı)
```

## Kurulum

```bash
cd /yol/to/ortopedist
unzip ~/Downloads/seo-fix-patch.zip -d /tmp/

cp /tmp/seo-fix-patch/app.py app.py
cp /tmp/seo-fix-patch/routes/admin.py routes/admin.py
cp /tmp/seo-fix-patch/templates/admin/base.html templates/admin/base.html
cp /tmp/seo-fix-patch/templates/admin/seo_cleanup.html templates/admin/seo_cleanup.html
cp /tmp/seo-fix-patch/templates/public/index.html templates/public/index.html
cp /tmp/seo-fix-patch/templates/public/post.html templates/public/post.html
cp /tmp/seo-fix-patch/templates/public/search.html templates/public/search.html

git add app.py routes/admin.py templates/
git commit -m "fix: SEO meta tag düzeltmeleri (None string sorunu)"
git push
```

Railway redeploy bekle (~1-2 dk).

## Kullanım

1. Admin'e gir: https://ortopedist.blog/admin
2. Sol menü → **🔧 SEO Bakımı**
3. **Adım 1**: "🧹 Bozuk String'leri Temizle" butonuna bas (ücretsiz, anlık)
4. **Adım 2**: "🤖 AI ile Eksik Meta'ları Doldur" (~$0.50 / 40 yazı, 5 dk)

Adım 1'den sonra zaten ana sayfada "None" görünmeyecek (filter'lar fallback yapıyor).
Adım 2 sonra yazıların kendi özel meta_description'ları olacak (Google için ideal).
