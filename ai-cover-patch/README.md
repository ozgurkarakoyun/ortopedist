# AI Kapak Görseli Üretimi

OpenAI'ın görsel API'sini kullanarak yazı için kapak görseli üretir.
Claude önce başlığı güvenli İngilizce prompt'a çevirir (tıbbi içerik filtresiyle),
OpenAI gerçek görseli üretir, sistem otomatik olarak yazıya kapak yapar.

## Yeni / Değişen Dosyalar

```
services/image_generator.py             (YENİ — Claude + OpenAI köprüsü)
routes/api.py                           (yeni endpoint: /api/posts/<id>/generate-cover)
templates/admin/post_editor.html        ("AI Kapak Üret" butonu)
requirements.txt                        (openai==1.54.4 eklendi)
config.py                               (OPENAI_API_KEY okunması)
```

## Kurulum

### 1. OpenAI API anahtarı al

https://platform.openai.com/signup → hesap aç
→ Settings → Billing → Add credit ($5-10 yeter)
→ API Keys → Create new key → kopyala

### 2. Railway Variables'a ekle

```
OPENAI_API_KEY=sk-proj-...
IMAGE_MODEL=gpt-image-1          # opsiyonel, varsayılan
IMAGE_QUALITY=medium              # low | medium | high
```

Maliyet (40 yazılık blog için tahmini):
| Quality | Tek görsel | 40 yazı |
|---------|-----------|---------|
| low     | ~$0.011   | ~$0.44  |
| medium  | ~$0.042   | ~$1.68  |
| high    | ~$0.167   | ~$6.68  |

`medium` kalite çoğu durumda yeterli. `low` daha basit/illüstratif görsellerde iyi.

### 3. Patch'i uygula

```bash
cd /yol/to/ortopedist-blog
unzip ~/Downloads/ai-cover-patch.zip -d /tmp/

cp /tmp/ai-cover-patch/services/image_generator.py services/
cp /tmp/ai-cover-patch/routes/api.py routes/
cp /tmp/ai-cover-patch/templates/admin/post_editor.html templates/admin/
cp /tmp/ai-cover-patch/requirements.txt requirements.txt
cp /tmp/ai-cover-patch/config.py config.py

git add services/ routes/ templates/admin/ requirements.txt config.py
git commit -m "feat: AI kapak görseli üretimi"
git push
```

Railway redeploy (`openai` paketi de kurulacağı için ~2-3 dk).

## Kullanım

1. Admin → bir yazıyı düzenle
2. Sağ panelde **🎨 AI Kapak Üret** butonu
3. Onayla → 30-60 sn bekle
4. Görsel otomatik olarak yazıya kapak olarak atanır
5. **Yazıyı KAYDET** (üretim tamam ama veritabanına kaydetmek için form'u submit et)

Üretilen prompt'u "Üretim prompt'unu göster" detay'ından görebilirsin.
Beğenmezsen butona tekrar bas, yeni bir görsel üretir.

## Güvenlik / İçerik Filtresi

Claude prompt'u oluştururken şunları **kesinlikle** engelliyor:
- Grafik anatomi, kan, açık cerrahi sahne
- Acı çeken/kederli hastalar
- Viewer'a doğrultulmuş enjeksiyon/bıçak
- Yazı, logo, watermark

Tercih edilen stil: temiz editöriyel illüstrasyon, sakin renk paleti, iyileşme/hareket/denge gibi soyut konseptler, modern tıbbi ekipman, sağlıklı insanlar (iyileşme sonrası).

## Önemli: Railway dosya kalıcılığı

Railway containerleri **ephemeral** (geçici) — yeniden deploy'da `static/images/uploads/`
silinebilir. Üretilen görsellerin kalıcı olması için ya:

- Railway'de **Volume** ekle ve `/app/static/images/uploads/`'a mount et, veya
- (Sonradan) S3/Cloudinary entegrasyonu yapılır

İlk birkaç görseli üretip test et, sonra kalıcı çözüme karar verirsin.
