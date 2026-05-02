# Toplu Çeviri Patch'i

Tek tıkla 40 yazının EN ve AR çevirilerini AI ile üretir.

## Sayfalar

### 🌍 Toplu Çeviri (yeni sayfa: /admin/translations)
- Mevcut durumu gösterir (TR/EN/AR sayıları)
- "Eksik EN Çevirilerini Üret" butonu
- "Eksik AR Çevirilerini Üret" butonu
- "Yayına Al" toplu butonu

### 📋 Onay Bekleyenler (eski sayfa, yeniden adlandırıldı: /admin/translations/review)
- Tek tek inceleme arayüzü
- Sayfa içeriği değişmedi, sadece URL değişti

## Akış

1. **Üret:** Buton → AI tüm eksik çevirileri TASLAK olarak oluşturur
2. **Gözden geçir:** Her çeviri "Onay Bekleyen" durumda. Birkaç tanesini incele
3. **Yayına al:** Toplu yayın butonu veya tek tek admin panelden

## Güvenlik

- Çeviriler **otomatik yayına alınmaz** (`is_published=False`)
- `ai_review_pending=True` olarak işaretlenir
- Bu önemli — özellikle tıbbi terimlerin doğruluğu için manuel kontrol gerek
- Çeviri kaydı, mevcut tek-tek çeviri endpoint'iyle aynı `Translator` servisini kullanır

## Maliyet ve Süre

| | Birim | 40 yazı × 2 dil = 80 |
|---|---|---|
| Maliyet | ~$0.04-0.06 / çeviri | ~$3.20-4.80 |
| Süre | ~10-15 sn / çeviri (+1.5 sn rate limit) | ~15-20 dk |

## Değişen 4 dosya

```
routes/admin.py                            (4 yeni endpoint)
templates/admin/base.html                  (sidebar linki güncellendi)
templates/admin/translations.html          (YENİ - toplu çeviri arayüzü)
templates/admin/translations_review.html   (YENİDEN ADLANDIRILDI - eski tek-tek inceleme)
```

## Kurulum

```bash
cd /yol/to/ortopedist
unzip ~/Downloads/bulk-translate-patch.zip -d /tmp/

# Eski translations.html'i yeniden adlandır (eğer hâlâ duruyorsa)
[ -f templates/admin/translations_review.html ] || mv templates/admin/translations.html templates/admin/translations_review.html.bak 2>/dev/null

# Yeni dosyaları kopyala
cp /tmp/bulk-translate-patch/routes/admin.py routes/admin.py
cp /tmp/bulk-translate-patch/templates/admin/base.html templates/admin/base.html
cp /tmp/bulk-translate-patch/templates/admin/translations.html templates/admin/translations.html
cp /tmp/bulk-translate-patch/templates/admin/translations_review.html templates/admin/translations_review.html

git add routes/admin.py templates/admin/
git commit -m "feat: toplu çeviri sayfası (EN/AR), onay bekleyen yeni URL"
git push
```

## Kullanım

1. Admin'e gir → Sol menü → **🌍 Toplu Çeviri**
2. **🇬🇧 Eksik EN Çevirilerini Üret** butonuna bas
3. ~10 dakika bekle (yazı başına ~10-15 sn × 40 yazı)
4. Sırayla her yazının ✅ olduğunu gör
5. Bitince aynı şeyi **🇸🇦 AR** için de yap
6. **İncele** linkleriyle birkaç çeviriyi gözden geçir
7. **✅ Yayına Al** butonuyla toplu yayın

## ÖNEMLİ: Önce Anthropic kredi yükle

Mevcut hata "credit balance too low" diyor. Çevirilerin başlamadan önce:

https://console.anthropic.com/settings/billing → minimum $10 yükle

40 yazı × 2 dil = 80 çeviri tahmini $4-5 arası tutacak.
