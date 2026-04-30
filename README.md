# Dil Switcher Düzeltmesi

## Sorun

EN/AR butonlarına tıklayınca aynı TR sayfası kalıyordu, çünkü butonlar
sadece session'a yazıyordu, URL'yi değiştirmiyordu. Türkçe URL ise her
zaman Türkçe içerik göstermek üzere route edilmiş.

## Çözüm

Dil butonu artık mevcut sayfanın **hedef dildeki karşılığına** yönlendiriyor:
- `/yazi/foo` üzerinde EN'e tıkla → `/en/post/foo`
- `/hakkimda` üzerinde EN'e tıkla → `/en/about`
- `/kategori/x` üzerinde AR'ye tıkla → `/ar/category/x`
- vb.

## Değişen dosyalar

```
app.py                       (lang_url() helper eklendi)
templates/base.html          (lang switcher lang_url kullanıyor)
```

## Kurulum

```bash
cd /yol/to/ortopedist-blog
unzip ~/Downloads/lang-fix-patch.zip -d /tmp/
cp /tmp/lang-fix-patch/app.py app.py
cp /tmp/lang-fix-patch/templates/base.html templates/base.html

git add app.py templates/base.html
git commit -m "fix: dil switcher mevcut sayfanın hedef dildeki URL'sine yönlensin"
git push
```

Railway otomatik redeploy eder.

## ÖNEMLİ NOT — boş içerik

Bu düzeltme sadece **URL**'yi düzeltir. Ama şu an 40 yazının hepsi
sadece Türkçe'de — EN/AR çevirileri yok. Bu yüzden:

- `/en/` → "No published articles yet" mesajı görünür (boş)
- `/en/post/foo` → o yazının EN çevirisi yoksa otomatik TR'ye yönlenir

İngilizce/Arapça içerik istiyorsan: admin → yazıyı düzenle →
"→ English" veya "→ العربية" butonuna bas → AI çevirir →
onayla → yayında. Toplu çeviri için her yazıya ayrı ayrı yapman
gerek (40 yazı = 80 çeviri, AI 1-2 saat içinde tamamlar).

İstersen sonradan toplu otomatik çeviri özelliği de ekleyebiliriz.
