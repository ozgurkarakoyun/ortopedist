"""
SEOGenerator: Yazı için SEO meta verisi üretir (title, description, keywords).
"""
import json
import re
from typing import Dict, Any, Optional
from anthropic import Anthropic


class SEOGenerator:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY tanımlanmamış")
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate(self, title: str, content: str, lang: str = "tr") -> Dict[str, Any]:
        lang_name = {"tr": "Türkçe", "en": "English", "ar": "العربية"}.get(lang, "Türkçe")

        system = (
            "Sen, tıbbi/ortopedi içerikleri için SEO uzmanı olan bir asistansın. "
            "Google için optimize meta verisi üret. Tıklama oranını artıracak ama "
            "yanıltıcı olmayacak şekilde başlık ve açıklama hazırla."
        )
        user = (
            f"Dil: {lang_name}\n"
            f"BAŞLIK: {title}\n\nİÇERİK (özet):\n{content[:3000]}\n\n"
            "SADECE JSON döndür:\n"
            "{\n"
            '  "meta_title": "50-60 karakter",\n'
            '  "meta_description": "140-160 karakter, davetkar",\n'
            '  "meta_keywords": "5-8 anahtar kelime, virgülle",\n'
            '  "og_title": "Open Graph başlığı",\n'
            '  "og_description": "Open Graph açıklaması",\n'
            '  "h1_suggestion": "Daha iyi H1 önerisi (varsa)",\n'
            '  "structured_summary": "Google snippet için 2-3 cümle"\n'
            "}"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join([b.text for b in response.content if hasattr(b, "text")])
        data = _extract_json(text) or {}
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
    except Exception:
        return None
