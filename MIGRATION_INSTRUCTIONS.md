# 📦 Konsolide Repo Sıfırlama

Bu zip, projenin **şu ana kadar uygulanmış tüm patch'lerin son halini** içerir.
Manuel patch karmaşası yerine bu klasörle repo'nu komple yenileyebilirsin.

## Tek seferde uygulama

```bash
cd /yol/to/ortopedist     # GitHub'a push ettiğin lokal repo

# 1. ZIP'i indir, /tmp/'ye aç
unzip ~/Downloads/ortopedist-final.zip -d /tmp/

# 2. Ana repo'daki YANLIŞ ai-cover-patch klasörünü temizle
rm -rf ai-cover-patch

# 3. Tüm dosyaları üzerine kopyala
cp -r /tmp/ortopedist-final/. .

# 4. Sonucu doğrula (aşağıdakilerin hepsi var olmalı)
ls services/image_generator.py services/wxr_importer.py templates/admin/migrate.html
grep -c "openai" requirements.txt          # 1 olmalı
grep -c "lang_url" app.py                  # 3+ olmalı
grep -c "generate-cover" routes/api.py     # 1+ olmalı

# 5. Commit + push
git add -A
git commit -m "chore: konsolide patch sıfırlama - tüm özellikler"
git push
```

Railway otomatik redeploy eder (~2-3 dk, openai paketi de kurulacak).

## İçerik

Bu zip'in içerdiği özellikler:

✓ Auto-create_all (DB tabloları boot'ta otomatik)
✓ /healthz endpoint (Railway healthcheck)
✓ Auto-admin (ADMIN_EMAIL + ADMIN_PASSWORD env var'ından)
✓ Bootstrap endpoint (/admin/bootstrap?key=...)
✓ Akıllı dil switcher (lang_url helper)
✓ WordPress XML upload (/admin/migrate-wp - WXR yükle)
✓ URL scrape migrasyon (yedek)
✓ AI kapak görseli (OpenAI gpt-image-1 ile)
✓ Mevcut tüm AI özellikleri (yazma, çeviri, geliştirme, SEO, konu keşfi)

## Gerekli Railway Variables

```
SECRET_KEY=<rastgele hex, ASCII>
ANTHROPIC_API_KEY=sk-ant-...
ADMIN_EMAIL=ozgur@ortopedist.blog
ADMIN_PASSWORD=AsciiOnlyPassword123     # ⚠ Türkçe karakter YOK
ADMIN_NAME=Özgür Karakoyun

# Opsiyonel - AI kapak için
OPENAI_API_KEY=sk-proj-...
IMAGE_QUALITY=medium                    # low | medium | high
IMAGE_MODEL=gpt-image-1
```

PostgreSQL plugin de eklenmiş olmalı (DATABASE_URL otomatik gelir).
