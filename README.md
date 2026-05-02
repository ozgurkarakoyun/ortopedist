# Toplu Kapak Üretimi Patch'i

Kapağı olmayan yayında yazılar için **tek tıkla AI kapak üretir**.
SEO Bakımı ve Toplu Çeviri ile aynı yapı: tek tek işle, anlık progress.

## Yeni Sayfa: 🎨 Toplu Kapak

Sol sidebar'da **"🎨 Toplu Kapak"** linki.

İçerik:
- 📊 Durum kartları: Yayında / Kapaklı / Eksik sayıları
- 🤖 "Tüm Eksik Kapakları Üret" butonu — eksik sayısını gösterir
- 💰 Anlık maliyet hesabı (eksik × $0.04)
- 📋 İşlem listesi: her üretilen kapağın **küçük preview'ı** ile

## Akış

1. Buton → Eksik liste alınır
2. Tek tek `/api/posts/<id>/generate-cover` çağrılır (mevcut endpoint)
3. Her kapak üretildikçe **görsel önizleme** ile listeye eklenir
4. Yazıyı görüntüleme + düzenleme linkleri her kapağın yanında

## Zaten Mevcut: Yazı bazında üretim

Bu patch yeni endpoint EKLEMİYOR, sadece toplu çalışan UI ekliyor.
Mevcut `/api/posts/<id>/generate-cover` endpoint'i kullanılıyor.
Yani yazı düzenleme sayfasındaki "🎨 AI Kapak Üret" butonu çalışmaya devam eder.

## Değişen 3 dosya

```
routes/admin.py                       (2 yeni endpoint: covers_page, missing-list)
templates/admin/base.html             (sidebar'a yeni link)
templates/admin/covers.html           (YENİ - toplu üretim arayüzü)
```

## Kurulum

```bash
cd /yol/to/ortopedist
unzip ~/Downloads/bulk-covers-patch.zip -d /tmp/

cp /tmp/bulk-covers-patch/routes/admin.py routes/admin.py
cp /tmp/bulk-covers-patch/templates/admin/base.html templates/admin/base.html
cp /tmp/bulk-covers-patch/templates/admin/covers.html templates/admin/covers.html

git add routes/admin.py templates/admin/
git commit -m "feat: toplu kapak üretim sayfası"
git push
```

Railway redeploy bekle (~1-2 dk).

## Kullanım

1. Admin → sol menü → **🎨 Toplu Kapak**
2. "Eksik Kapağı Olan: X" sayısını gör
3. **🎨 Tüm Eksik Kapakları Üret (X)** butonuna bas
4. Her yazıdan sonra ekranda **preview ile** görmen lazım:
   - "İşleniyor: 5 / 12 — Yazı başlığı"
   - Üretilen kapağın küçük önizlemesi listede

## Maliyet

Her kapak yaklaşık **$0.04** (OpenAI gpt-image-1, medium quality).
12 eksik kapak → ~$0.48
40 yazıdan tümü eksik → ~$1.60

OpenAI kredinden harcanır (Anthropic'ten ayrı). Yetersiz krediyse:
https://platform.openai.com/settings/organization/billing
