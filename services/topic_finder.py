"""
TopicFinder: Güncel ortopedi konularını web search ile keşfeder ve
yazar için öneri listesi üretir.

Anthropic'in built-in `web_search_20250305` tool'unu kullanır.
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class TopicFinder:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY tanımlanmamış")
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def discover(
        self,
        focus: str = "ortopedi, travmatoloji, boy uzatma, deformite, kırık",
        count: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Web search yaparak güncel konular önerir.
        Returns: [
          {
            "title": "Önerilen başlık",
            "description": "Neden ilginç?",
            "relevance_score": 0.0-1.0,
            "keywords": ["..."],
            "sources": ["url1", "url2"]
          }, ...
        ]
        """
        system = (
            "Sen, ortopedi ve travmatoloji uzmanı bir Türk doktor için blog konu "
            "araştırması yapan bir asistansın. Web search kullanarak güncel "
            "tıbbi gelişmeleri, yeni cerrahi teknikleri, hasta sıkça merak ettiği "
            "konuları araştır ve Türk hasta kitlesi için anlamlı blog konuları öner."
        )

        user = (
            f"Aşağıdaki uzmanlık alanlarına odaklan: {focus}.\n\n"
            "Web search yaparak son 6-12 ay içindeki güncel gelişmeleri, "
            "tıbbi araştırmaları ve hasta merak ettiği konuları araştır. "
            f"En değerli {count} blog konusu öner.\n\n"
            "Araştırmayı tamamladıktan sonra, SADECE şu JSON formatında cevap ver "
            "(başka açıklama ekleme):\n"
            "{\n"
            '  "topics": [\n'
            "    {\n"
            '      "title": "Türkçe blog başlığı (60 karakter civarı)",\n'
            '      "description": "Bu konunun neden değerli olduğunu açıklayan 2-3 cümle",\n'
            '      "relevance_score": 0.85,\n'
            '      "keywords": ["anahtar1", "anahtar2", "anahtar3"],\n'
            '      "sources": ["https://...", "https://..."]\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

        # Web search tool ile çağır
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=system,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": user}],
            )
        except Exception as e:
            logger.warning(f"Web search tool unavailable, fallback: {e}")
            # Web search desteklenmiyorsa, sadece model bilgisiyle öneri üret
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system,
                messages=[{
                    "role": "user",
                    "content": user + "\n\nNot: Web search erişimin yoksa, "
                    "genel tıbbi bilgine dayanarak öner. sources alanını boş bırak."
                }],
            )

        # Tüm text bloklarını birleştir
        text = ""
        for block in response.content:
            block_text = getattr(block, "text", None)
            if block_text:  # None ve "" değilse
                text += block_text + "\n"

        data = _extract_json(text)
        if not data or "topics" not in data:
            logger.error("Topic finder JSON çıkarma başarısız: %s", text[:500])
            return []
        return data["topics"]


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
        return None
