# Arama Motoru Doğrulama Patch'i

3 büyük arama motoru için sahiplik doğrulama meta tag'leri.
Tag'ler env var'dan okunur — kodu değiştirmeden, sadece Variables ile yönetilir.

## Desteklenen

- Google Search Console (`GOOGLE_SITE_VERIFICATION`)
- Bing Webmaster Tools (`BING_SITE_VERIFICATION`)
- Yandex Webmaster (`YANDEX_SITE_VERIFICATION`)

## Değişen 2 dosya

```
app.py                  (env var'dan token'ları okur)
templates/base.html     (head içine 3 meta tag, sadece dolu olanlar render edilir)
```

## Kurulum

```bash
cd /yol/to/ortopedist
unzip ~/Downloads/google-verify-patch.zip -d /tmp/

cp /tmp/google-verify-patch/app.py app.py
cp /tmp/google-verify-patch/templates/base.html templates/base.html

git add app.py templates/base.html
git commit -m "feat: search engine verification meta tags"
git push
```

## Railway Variables

Web service → Variables → +New:

```
GOOGLE_SITE_VERIFICATION=lzTJTuZeGb2ZSBvaDMiFFrbtxZJMUWGNxITVjY_emdg
```

Sonra (opsiyonel, bing/yandex ekleyince):
```
BING_SITE_VERIFICATION=...
YANDEX_SITE_VERIFICATION=...
```

## Doğrulama

Railway redeploy bittikten sonra:

1. https://ortopedist.blog → Sağ tık → "Sayfa kaynağını görüntüle"
2. Ctrl+F → "google-site-verification" ara
3. Tag'i görmeli:
   `<meta name="google-site-verification" content="lzTJTuZ...">`

Sonra Search Console'a dön → **VERIFY** butonuna bas → ✅
