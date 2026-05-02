# Google Scholar + Sosyal Profil Schema Güncellemesi

Schema.org Physician markup'ına 8 önemli profil bağlandı.
Bu, Google Knowledge Panel için en güçlü "akademisyen" sinyalidir.

## Eklenen sameAs profilleri

### Akademik (en güçlü Knowledge Panel sinyali)
- ✨ **Google Scholar** — `scholar.google.com.tr/citations?user=6y2ID6EAAAAJ` (362+ atıf)

### Resmi siteler
- ozgurkarakoyun.com (klinik web sitesi)
- osseointegra.com (osseointegrasyon uzmanlık sitesi)

### Türkiye doktor dizinleri (lokal SEO için kritik)
- Doktortakvimi.com profili
- Doktorsitesi.com profili

### Sosyal medya
- Facebook: drozgurkarakoyun
- Instagram: dr.ozgurkarakoyun
- Instagram (yeni): doc.dr.ozgurkarakoyun_md

## Hem schema'da hem GÖRÜNÜR sayfada

Google'ın kuralı: "schema'da yazdığın her şey sayfada da olmalı"
Bu yüzden hakkımda sayfasının her dilinde (TR/EN/AR):
- Akademik Çalışmalar bölümünde Google Scholar linki görünür
- İletişim bölümünde Türkiye doktor dizinleri görünür

## Değişen 2 dosya

```
templates/base.html              (Person schema sameAs - Google Scholar eklendi)
templates/public/about.html      (Physician schema sameAs - 8 link + görünür linkler)
```

## Kurulum

```bash
cd /yol/to/ortopedist
unzip ~/Downloads/scholar-patch.zip -d /tmp/

cp /tmp/scholar-patch/templates/base.html templates/base.html
cp /tmp/scholar-patch/templates/public/about.html templates/public/about.html

git add templates/base.html templates/public/about.html
git commit -m "feat: Google Scholar + 8 akademik/sosyal profil schema'ya bağlandı"
git push
```

## Doğrulama

1. **Sayfa kontrolü:** https://ortopedist.blog/hakkimda
   - "Akademik Çalışmalar" bölümünde "Google Scholar" linki olmalı
   - "Diğer profiller" satırında 3 link olmalı (Doktortakvimi, Doktorsitesi, Instagram)

2. **Google Rich Results Test:** https://search.google.com/test/rich-results
   - URL: https://ortopedist.blog/hakkimda
   - "Physician" + 8 sameAs link görünmeli

3. **Schema.org Validator:** https://validator.schema.org/
   - sameAs: 8 valid URL

## Bu Neden Önemli?

Google Knowledge Panel için 4 sinyal lazım:
1. ✅ **Net entity (kim olduğu)** — Physician schema yapıyor
2. ✅ **Akademik kanıt** — Google Scholar 362 atıf
3. ✅ **Lokal kanıt** — Doktor dizinleri (Tekirdağ + ortopedi)
4. ⏳ **Wikipedia / Wikidata** — Gelecek adım (bu hocaya hediye olarak yazılır)

Google Scholar bağlantısı tek başına Knowledge Panel garantilemez ama
Google'ın E-E-A-T (Experience, Expertise, Authority, Trust) algoritması için
*çok güçlü* bir sinyaldir. AI Overviews'lerde "cited source" olma ihtimalini
ciddi şekilde artırır.
