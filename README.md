# Ortopedist Blog

> Doç. Dr. Özgür Karakoyun'un kişisel blog ve içerik yönetim platformu.
> Flask + Jinja, PostgreSQL, Claude API, çoklu dil (TR/EN/AR) ve AI destekli admin paneli ile.

## Özellikler

**Public:**
- Sunucu render (SEO dostu), hızlı yüklenme
- 3 dil: Türkçe (varsayılan), İngilizce, Arapça (RTL desteği)
- Kategori, arama, sayfalama, sitemap.xml, robots.txt, RSS feed
- Open Graph + JSON-LD (`MedicalScholarlyArticle`) yapılandırılmış veri
- Hreflang alternatifleri ile çoklu dil SEO

**Admin paneli:**
- Bcrypt şifreleme, CSRF koruması, rate limiting
- Markdown editör, kapak görseli yükleme, kategori yönetimi
- Çoklu dil sekme yapısı (TR/EN/AR), her dilde bağımsız yayın kontrolü

**AI özellikleri (Claude API):**
1. **Konu keşfi** — Web search ile güncel ortopedi konularını bulur
2. **Tarzında yazma** — Önceki yazılarını örnek alarak yeni yazı taslağı üretir
3. **Geliştirme** — Mevcut yazıları improve / expand / modernize / shorten modlarında günceller
4. **Çeviri** — TR'den EN/AR'a çeviri (her zaman taslak; admin onaylayana kadar yayınlanmaz)
5. **SEO meta** — Otomatik meta title, description, keywords, Open Graph
6. **Görsel önerisi** — Stok fotoğraf arama sorguları + alt-text

---

## Hızlı Başlangıç (Lokal)

```bash
git clone <repo-url> ortopedist-blog
cd ortopedist-blog

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# .env dosyasını düzenle, en azından ANTHROPIC_API_KEY ve SECRET_KEY ekle

# Veritabanını başlat
flask --app app init-db

# Admin kullanıcı oluştur (interaktif)
flask --app app create-admin

# Çalıştır
python app.py
# veya: flask --app app run
```

Sonra http://localhost:5000 ve http://localhost:5000/admin

---

## Railway'de Deployment

1. **Yeni proje oluştur**
   - https://railway.app → New Project → Deploy from GitHub Repo
   - Bu repository'yi seç

2. **PostgreSQL ekle**
   - Add Service → Database → PostgreSQL
   - Otomatik olarak `DATABASE_URL` ortam değişkeni eklenir

3. **Çevre değişkenlerini ekle (Variables sekmesi)**
   ```
   SECRET_KEY=<rastgele-uzun-string>
   FLASK_ENV=production
   SITE_URL=https://ortopedist.blog
   ANTHROPIC_API_KEY=sk-ant-...
   AI_MODEL=claude-sonnet-4-5
   AUTHOR_NAME=Doç. Dr. Özgür Karakoyun
   ```

4. **Domain bağla**
   - Settings → Domains → Custom Domain → ortopedist.blog
   - DNS'te CNAME kaydı ekle (Railway'in verdiği target'a)

5. **İlk deploy bitince**
   ```bash
   # Railway CLI ile (npm install -g @railway/cli)
   railway login
   railway link
   railway run flask --app app init-db
   railway run flask --app app create-admin
   ```

   **Veya:** Railway dashboard'da "..." menüden Console → komutları çalıştır.

---

## İçerik Migrasyonu (Mevcut WordPress'ten)

Mevcut `ortopedist.blog` içeriğini yeni platforma aktarmak için:

```bash
# Önce küçük bir test (5 yazı, dry-run)
python scripts/migrate_content.py --limit 5 --dry-run

# Sonra gerçek aktarım
python scripts/migrate_content.py
```

Script şunları yapar:
- WordPress sitemap.xml veya RSS'inden tüm yazı URL'lerini bulur
- Her yazıyı indirir, başlık + içerik + kapak görseli + kategori bilgisini çıkarır
- HTML'i Markdown'a çevirir
- Aynı slug zaten varsa atlar (idempotent)
- Yazıları `published` durumda + Türkçe çeviriyle ekler

Migrasyon sonrası: yazıları admin panelinden gözden geçirebilir, AI ile EN/AR çevirilerini üretebilir, SEO meta verisini yenileyebilirsiniz.

**Railway üzerinde migrasyon çalıştırma:**
```bash
railway run python scripts/migrate_content.py
```

---

## Admin Paneli — AI Özelliklerinin Kullanımı

### 1) Konu keşfi
- Panel → "AI Konular" → "Yeni Keşfet"
- 30-90 sn içinde 5 güncel konu önerisi gelir (relevance score, anahtar kelimeler, kaynaklar)
- Beğendiğin konuda **"Bu Konuda Yaz"** → AI senin tarzında bir taslak hazırlar
- Editöre düşer; gözden geçirir, kaydeder, yayınlarsın

### 2) Yeni yazı oluşturma
- "Yeni Yazı" → en üstteki AI panelinde konu yaz, kelime sayısını seç → "✨ Yaz"
- Son 4 yayınlanmış TR yazı tarz örneği olarak otomatik kullanılır
- Standart tıbbi feragatname yazının sonuna eklenir

### 3) Mevcut yazıyı geliştirme
- Yazı düzenleme sayfasındaki "AI İşlemleri" panelinden:
  - **Geliştir** — akıcılık ve dil
  - **Genişlet** — eksik konuları ekler
  - **Güncelle** — eski referansları yenisiyle değiştirir
  - **Kısalt** — özetler

### 4) Çeviri (TR → EN / AR)
- Yazıda "→ English" veya "→ العربية" tıkla
- AI çeviriyi yapar ve **taslak** olarak kaydeder (`ai_review_pending=True`)
- Çeviri sayfasında gözden geçir, "Bu dilde yayında" kutusunu işaretle, kaydet
- **Onaylanana kadar public site'da görünmez** (güvenlik için)

### 5) SEO meta üretimi
- Yazı düzenleme → SEO Meta detayını aç → "AI ile SEO Üret"
- Meta başlık, açıklama, anahtar kelimeler otomatik dolar

### 6) Görsel önerisi
- Yazı düzenleme → "Görsel Önerisi"
- 3-5 stok fotoğraf arama sorgusu (İngilizce) + Türkçe/İngilizce alt-text gelir
- Bu sorguları Unsplash, Pexels gibi platformlarda kullanabilirsiniz

---

## Proje Yapısı

```
ortopedist-blog/
├── app.py                      # Flask uygulama factory'si
├── config.py                   # Yapılandırma
├── extensions.py               # SQLAlchemy, Login, Babel vb.
├── models.py                   # User, Post, PostTranslation, Category, ...
├── requirements.txt
├── Procfile
├── railway.json
├── routes/
│   ├── public.py               # Public route'lar (TR/EN/AR)
│   ├── admin.py                # Admin paneli
│   └── api.py                  # AI endpoint'leri (JSON)
├── services/
│   ├── ai_writer.py            # Tarzında yazma + görsel önerisi
│   ├── topic_finder.py         # Web search ile konu keşfi
│   ├── translator.py           # Çeviri (taslak)
│   ├── seo.py                  # SEO meta üretimi
│   └── enhancer.py             # Mevcut yazıyı geliştirme
├── templates/
│   ├── base.html               # Public layout
│   ├── public/                 # Ana sayfa, yazı, hakkımda, iletişim, arama, 404
│   └── admin/                  # Admin layout, dashboard, editör, konular, çeviri
├── static/
│   ├── css/main.css            # Public CSS (RTL destekli)
│   ├── css/admin.css           # Admin CSS
│   └── images/uploads/         # Yüklenen görseller
└── scripts/
    └── migrate_content.py      # WordPress'ten içerik aktarımı
```

---

## Veritabanı Şeması (Özet)

- **users** — Admin kullanıcıları (bcrypt şifreli)
- **categories** — Kategoriler (tr/en/ar isimler)
- **posts** — Yazı (slug, durum, kategori, kapak)
- **post_translations** — Yazının her dildeki içeriği (`is_published`, `ai_review_pending` flag'leri)
- **topic_suggestions** — AI'nin önerdiği konular
- **ai_logs** — AI çağrı kayıtları (token tüketimi, hatalar)

---

## Geliştirme Notları

**Markdown render:** `markdown` paketi kullanılır; `extra, sane_lists, smarty, toc, tables, nl2br` extension'ları aktif.

**Hız sınırları (`Flask-Limiter`):**
- Genel: 300 istek/saat
- Login: 10/dakika
- AI çağrıları: 10–60/saat (endpoint'e göre)

**CSRF:** API blueprint'i hariç tüm POST formları CSRF korumalıdır. API endpoint'leri `login_required` ile korunur.

**Çeviri güvenliği:** AI çevirileri her zaman `is_published=False, ai_review_pending=True` olarak kaydedilir. Admin manuel olarak "Bu dilde yayında" kutusunu işaretleyene kadar görünmez.

**Tarz yakalama:** AI yazma sırasında, son 4 yayınlanmış TR yazı tarz örneği olarak system prompt'a eklenir. Bu sayede zaman içinde daha tutarlı tarzla yazar (yazılarınız çoğaldıkça daha iyi olur).

---

## Lisans

© 2026 Doç. Dr. Özgür Karakoyun. Kişisel kullanım için geliştirilmiştir.
