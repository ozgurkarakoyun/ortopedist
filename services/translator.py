"""
Translator: TR -> EN/AR çeviri (taslak; admin onaylayana kadar yayında değil).
"""
import json
import logging
import re
from typing import Dict, Any, Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)


LANG_NAMES = {
    "en": "İngilizce (English)",
    "ar": "Arapça (العربية, RTL)",
}


class Translator:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY tanımlanmamış")
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def translate(
        self,
        title: str,
        content: str,
        excerpt: str = "",
        meta_title: str = "",
        meta_description: str = "",
        target_lang: str = "en",
    ) -> Dict[str, Any]:
        if target_lang not in LANG_NAMES:
            raise ValueError(f"Desteklenmeyen dil: {target_lang}")

        target_label = LANG_NAMES[target_lang]
        rtl_note = (
            "\n- Arapça çıktı RTL (sağdan sola) olacak; markdown yapısını koru."
            if target_lang == "ar" else ""
        )

        system = (
            "Sen, tıbbi içerik (ortopedi & travmatoloji) çevirmeni olan bir asistansın. "
            "Aşağıdaki kurallara KESİNLİKLE uyacaksın:\n"
            "- Tıbbi terimleri doğru çevir; gerektiğinde parantez içinde Latince/İngilizce karşılığını ekle.\n"
            "- Markdown yapısını birebir koru (# ## ### başlıklar, listeler, vurgu).\n"
            "- Hasta dostu, eğitici, profesyonel tonu koru.\n"
            "- Yorum ekleme, sadece çevir.\n"
            "- Standart tıbbi feragatnameyi de hedef dile çevirerek ekle.\n"
            f"{rtl_note}\n"
        )

        user = (
            f"Aşağıdaki Türkçe blog yazısını {target_label} diline çevir.\n\n"
            f"BAŞLIK: {title}\n"
            f"ÖZET: {excerpt}\n"
            f"META BAŞLIK: {meta_title}\n"
            f"META AÇIKLAMA: {meta_description}\n\n"
            f"İÇERİK (markdown):\n{content}\n\n"
            "Çıktıyı SADECE şu JSON formatında ver:\n"
            "{\n"
            '  "title": "...",\n'
            '  "excerpt": "...",\n'
            '  "meta_title": "...",\n'
            '  "meta_description": "...",\n'
            '  "content": "tüm markdown içerik"\n'
            "}\n"
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
            raise ValueError("Çeviri yanıtı çözülemedi")

        return {
            "title": data.get("title", title),
            "excerpt": data.get("excerpt", ""),
            "meta_title": data.get("meta_title", ""),
            "meta_description": data.get("meta_description", ""),
            "content": data.get("content", ""),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        candidate = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None
        candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        try:
            return json.loads(candidate.replace("\n", "\\n"))
        except Exception:
            return None
