"""
Enhancer: Mevcut blog yazılarını geliştirir (improve, expand, modernize, shorten).
"""
import json
import re
from typing import Dict, Any, Optional
from anthropic import Anthropic


MODE_INSTRUCTIONS = {
    "improve": (
        "Yazıyı geliştir: Akıcılığı artır, tıbbi doğruluğu koru, "
        "anlaşılırlığı yükselt. Yazarın tonunu KORU."
    ),
    "expand": (
        "Yazıyı genişlet: Eksik kalmış konuları (tanı, tedavi, iyileşme süreci, "
        "sıkça sorulan sorular) ekle. Mevcut bölümleri zenginleştir."
    ),
    "modernize": (
        "Yazıyı güncelle: Eski referansları çıkar, güncel tıbbi yaklaşımları "
        "ve yeni cerrahi teknikleri ekle. Tarihi atıflar varsa düzelt."
    ),
    "shorten": (
        "Yazıyı kısalt: Aynı bilgiyi daha öz biçimde ver, tekrarları çıkar. "
        "Asıl mesajları koru."
    ),
}


class Enhancer:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY tanımlanmamış")
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def enhance(self, title: str, content: str, mode: str = "improve") -> Dict[str, Any]:
        instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["improve"])

        system = (
            "Sen, ortopedi ve travmatoloji uzmanı Doç. Dr. Özgür Karakoyun'un "
            "blog yazılarını geliştiren bir editörsün. Yazarın hasta dostu, sade, "
            "eğitici Türkçe tonunu KORU. Markdown yapısını koru. "
            "Tıbbi feragatname her zaman yazının sonunda olmalı."
        )

        user = (
            f"GÖREV: {instruction}\n\n"
            f"BAŞLIK: {title}\n\n"
            f"MEVCUT İÇERİK (markdown):\n{content}\n\n"
            "SADECE JSON döndür:\n"
            "{\n"
            '  "title": "Güncellenmiş başlık (gerekiyorsa)",\n'
            '  "content": "Güncellenmiş tüm markdown içerik",\n'
            '  "summary_of_changes": "Yapılan değişikliklerin özeti (Türkçe)"\n'
            "}"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=12000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join([b.text for b in response.content if hasattr(b, "text")])
        data = _extract_json(text)
        if not data:
            raise ValueError("Geliştirme yanıtı çözülemedi")
        data["input_tokens"] = response.usage.input_tokens
        data["output_tokens"] = response.usage.output_tokens
        return data


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else text[text.find("{") : text.rfind("}") + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        try:
            return json.loads(candidate.replace("\n", "\\n"))
        except Exception:
            return None
