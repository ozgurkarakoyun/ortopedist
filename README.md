# İçerik Migrasyonu Patch'i

Bu paket, admin paneline tek tıkla WordPress'ten içerik aktarımı butonu ekler.

## Değişen 4 dosya

```
routes/admin.py              (genişletildi - 2 yeni endpoint)
templates/admin/base.html    (sidebar'a "İçerik Aktar" linki)
templates/admin/dashboard.html (dashboard'a migrasyon kartı)
templates/admin/migrate.html (YENİ - migrasyon arayüzü)
```

## Kurulum

Mevcut projende, bu zip'i açıp dosyaları aynı yollara kopyala (üzerine yaz):

```bash
cd /yol/to/ortopedist-blog
unzip ~/Downloads/migrate-patch.zip -d .
# routes/admin.py, templates/admin/base.html, dashboard.html, migrate.html güncellenecek

git add routes/admin.py templates/admin/
git commit -m "feat: tek tık WordPress içerik migrasyonu"
git push
```

## Kullanım

1. Railway otomatik yeni deploy eder (~1-2 dk)
2. https://ortopedist.blog/admin → Giriş yap
3. Sol menüden **📥 İçerik Aktar** veya dashboard'daki **WordPress'ten Aktar →**
4. **▶ Aktarımı Başlat** → 1-3 dk bekle
5. Sonuç: 40 yazı aktarıldı. "→ Yazıları Görüntüle" linkiyle kontrol et.

İlk önce **Dry-run** kutusunu işaretleyip 5 yazılık limit ile preview alabilirsin.

## Özellikler

- **Idempotent:** Aynı slug zaten varsa atlar; tekrar tekrar çalıştırılabilir
- **Rate limit:** Saatte 3 kez (yanlışlıkla spam'a karşı)
- **Dry-run:** Sadece önizleme, kaydetme
- **Limit:** Test için ilk N yazıyı dene (0 = tümü)
- **Anlık geri bildirim:** Her yazı için ✅/⏭️/❌ durumu gözükür
- **Login gerekli:** Sadece admin görür
