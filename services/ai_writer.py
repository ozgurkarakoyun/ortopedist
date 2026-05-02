"""
AIWriter: Doç. Dr. Özgür Karakoyun'un blog yazım tarzında içerik üretir.

Yazım tarzının çıkarılan özellikleri (mevcut blog yazılarından):
- Sade, hasta dostu, eğitici Türkçe
- Markdown başlık yapısı: H1 (başlık) -> kısa giriş paragrafı -> H3 numaralı alt başlıklar
- Her bölüm 1-3 paragraf
- Sonunda "Sonuç" bölümü
- Her yazının sonunda standart tıbbi feragatname:
  "Bu yazı, genel bilgilendirme amaçlıdır ve profesyonel tıbbi tavsiyenin
   yerini alamaz. Lütfen tedavi sürecinizle ilgili herhangi bir sorunuz
   için doktorunuza danışın."
- Ortopedi/travmatoloji uzmanlık alanı (boy uzatma, kemik kırıkları, deformite, vs.)
- Kelime sayısı: ortalama 600-1200
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)


STYLE_GUIDE = """
Yazım stili kılavuzu (Doç. Dr. Özgür Karakoyun):

1. DİL VE TON
- Sade, anlaşılır, hasta dostu Türkçe
- Tıbbi terimleri açıklayarak kullan ("genu varum (parantez bacak)" gibi)
- Profesyonel ama samimi bir doktor tonu
- "Biz", "siz" hitabı; özellikle "doktorunuz", "vücudunuz" gibi
- Korkutmadan bilgilendirici

2. YAPI (Markdown)
- # Başlık (sadece bir tane H1)
- 1-2 paragraf giriş (konunun ne olduğunu, neden önemli olduğunu açıklar)
- ### 1. Alt Başlık (numaralı, H3)
- ### 2. Alt Başlık
- ...
- ### Sonuç (her zaman olmalı)
- En altta tıbbi feragatname (aşağıdaki standart cümleyi olduğu gibi kullan)

3. PARAGRAF YAPISI
- Her bölüm 1-3 kısa paragraf (1 paragraf = 2-5 cümle)
- Cümleler kısa ve net
- Liste kullanımı seyrek; gerektiğinde markdown bullet (-)

4. KAPSAM
- Tanım / Nedir
- Belirtileri / nedenleri
- Tanı yöntemleri
- Tedavi seçenekleri (cerrahi/non-cerrahi)
- İyileşme süreci / dikkat edilmesi gerekenler
- Sonuç

5. STANDART FERAGATNAME (yazının sonuna ekle, aynen)
"---

Bu yazı, genel bilgilendirme amaçlıdır ve profesyonel tıbbi tavsiyenin yerini alamaz. Lütfen tedavi sürecinizle ilgili herhangi bir sorunuz için doktorunuza danışın."

6. UZMANLIK ALANI VURGUSU
- Boy uzatma, deformite düzeltme, kaynamayan kırık, osseointegrasyon hocanın özel ilgi alanı
- Konuyla ilgiliyse, hocanın deneyimine atıfta bulunabilirsin
- ÖNEMLİ: Asla yalan istatistik veya kaynak uydurma. Sadece genel kabul gören tıbbi bilgileri sun.
"""


class AIWriter:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY tanımlanmamış")
        self.client = Anthropic(api_key=api_key)
        self.model = model

    # -------- Blog yazma -------------------------------------------------

    def write_post(
        self,
        topic: str,
        target_words: int = 800,
        tone_examples: Optional[List[Dict[str, str]]] = None,
        author_name: str = "Doç. Dr. Özgür Karakoyun",
    ) -> Dict[str, Any]:
        """
        Verilen konuda, yazarın tarzında bir blog yazısı üretir.
        Returns: { "title", "slug", "excerpt", "content", "meta_title",
                   "meta_description", "meta_keywords", "input_tokens", "output_tokens" }
        """
        # Tarz örneklerini formatla
        examples_text = ""
        if tone_examples:
            examples_text = "\n\n--- TARZ ÖRNEKLERİ (yazarın önceki yazıları, aynen kopyalama, sadece tarzı yakala) ---\n"
            for i, ex in enumerate(tone_examples[:4], 1):
                examples_text += f"\n[Örnek {i}] BAŞLIK: {ex.get('title','')}\n{ex.get('content','')[:2000]}\n"

        system_prompt = (
            f"Sen, ortopedi ve travmatoloji uzmanı {author_name} adına blog yazısı "
            "yazan bir yardımcısın. Kesinlikle aşağıdaki yazım stilini takip etmelisin.\n"
            f"\n{STYLE_GUIDE}\n"
        )

        user_prompt = (
            f"Aşağıdaki konuda yazara ait tarzda bir blog yazısı yaz.\n\n"
            f"KONU: {topic}\n"
            f"HEDEF KELİME SAYISI: {target_words} (±%15)\n"
            f"DİL: Türkçe\n"
            f"{examples_text}\n\n"
            "Çıktıyı SADECE geçerli bir JSON nesnesi olarak ver, başka hiçbir metin ekleme:\n"
            "{\n"
            '  "title": "Yazının başlığı (60 karakter altı tercih)",\n'
            '  "slug": "url-uyumlu-baslik",\n'
            '  "excerpt": "1-2 cümlelik özet (150-200 karakter)",\n'
            '  "content": "Markdown formatında tam yazı (# başlık, ### alt başlıklar, sonunda feragatname)",\n'
            '  "meta_title": "SEO başlığı 50-60 karakter",\n'
            '  "meta_description": "SEO açıklaması 140-160 karakter",\n'
            '  "meta_keywords": "virgülle ayrılmış 5-8 anahtar kelime"\n'
            "}\n\n"
            "ÖNEMLİ:\n"
            "- content alanı tam markdown olmalı; yazının sonunda standart feragatname BULUNMALI\n"
            "- JSON içinde çift tırnak kullanırken kaçış (\\\") yapmayı unutma\n"
            "- Asla istatistik, sayı, yıl uydurma; emin değilsen genel ifade kullan\n"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = "".join([(b.text or "") for b in response.content if hasattr(b, "text")])
        data = _extract_json(text)
        if not data:
            raise ValueError("AI geçerli JSON döndürmedi")

        result = {
            "title": data.get("title", topic),
            "slug": data.get("slug", ""),
            "excerpt": data.get("excerpt", ""),
            "content": data.get("content", ""),
            "meta_title": data.get("meta_title", ""),
            "meta_description": data.get("meta_description", ""),
            "meta_keywords": data.get("meta_keywords", ""),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return result

    # -------- Görsel önerisi ---------------------------------------------

    def suggest_images(self, title: str, content: str) -> Dict[str, Any]:
        """Yazı için görsel arama anahtar kelimeleri ve alt-text önerir."""
        system_prompt = (
            "Tıbbi/orthopedik blog yazısı için görsel önerileri üreten bir asistansın. "
            "Hassas/grafik/zarar verici görseller önerme; sadece eğitici, anatomik şema veya "
            "rehabilitasyon/ortopedi temalı stok fotoğraf konseptleri öner."
        )
        user_prompt = (
            f"BAŞLIK: {title}\n\nİÇERİK (özet):\n{content[:1500]}\n\n"
            "3-5 görsel önerisi üret. Her biri için:\n"
            "- query: stok fotoğraf araması için İngilizce kısa sorgu\n"
            "- alt_text_tr: Türkçe alt metin\n"
            "- alt_text_en: English alt text\n"
            "- placement: 'hero' (kapak), 'inline' (içerik içi), 'diagram' (anatomik şema)\n\n"
            "SADECE JSON döndür: {\"suggestions\": [{...}, ...]}"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join([(b.text or "") for b in response.content if hasattr(b, "text")])
        data = _extract_json(text) or {"suggestions": []}
        return {
            "suggestions": data.get("suggestions", []),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }


# -------- Yardımcı: AI yanıtından JSON çıkarma ---------------------------

def _extract_json(text: str) -> Optional[dict]:
    """AI metninden JSON nesnesini güvenli biçimde çıkarır."""
    if not text:
        return None
    # Direkt JSON olabilir
    text = text.strip()
    # ```json ... ``` bloğu
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        candidate = fence.group(1)
    else:
        # İlk { ... son } kapsamı
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Sıkça karşılaşılan hatalar için onarım denemesi
        cleaned = candidate.replace("\n", "\\n").replace("\r", "")
        try:
            return json.loads(cleaned)
        except Exception:
            logger.warning("JSON parse failed; returning None")
            return None
