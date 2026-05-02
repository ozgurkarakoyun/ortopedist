# AI Servisleri NoneType Düzeltmesi

## Sorun

"AI Konu Keşfet" butonu hata veriyordu:
`unsupported operand type(s) for +: 'NoneType' and 'str'`

Sebep: Anthropic API'sinin web search tool'u veya bazı yanıt türleri,
`block.text` alanı olan ama içi `None` olan blok döndürüyor.
Eski kod `block.text + "string"` yapıyordu → patlıyor.

Aynı bug 6 servisde tekrar ediyordu — hepsi düzeltildi.

## Düzeltme

`b.text` None olduğunda boş string olarak kabul edilir:
- `b.text or ""` ile fallback
- `getattr(block, "text", None)` ile güvenli erişim

## Değişen 6 dosya

```
services/topic_finder.py          (Konu Keşfet özelliği — asıl bug burada)
services/ai_writer.py              (AI yazı yazma)
services/enhancer.py               (Yazı geliştirme)
services/translator.py             (TR→EN/AR çeviri)
services/seo.py                    (SEO meta üretimi)
services/image_generator.py        (Kapak görseli prompt'u)
```

## Kurulum

```bash
cd /yol/to/ortopedist
unzip ~/Downloads/none-fix-patch.zip -d /tmp/

cp /tmp/none-fix-patch/services/*.py services/

git add services/
git commit -m "fix: NoneType handling in all AI services"
git push
```

Railway redeploy bekle (~1-2 dk).

## Test

Admin → AI Konu Keşfet butonu → çalışmalı
Admin → Bir yazıyı düzenle → AI Geliştir → çalışmalı
Admin → Çevir (EN/AR) → çalışmalı

Sonuçta tüm AI özellikleri artık None text bloklarına karşı dayanıklı.
