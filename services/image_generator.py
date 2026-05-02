"""
ImageGenerator: AI ile blog kapak görseli üretir.

İki adım:
1. Claude: Türkçe başlık + özeti -> güvenli İngilizce image prompt'a çevirir.
   Tıbbi içerik filtresi (kan, grafik anatomi, korkutucu görüntü ENGELLI).
2. OpenAI: Prompt'tan görsel üretir, /static/images/uploads/ altına kaydeder.
"""
import base64
import io
import logging
import os
import time
from typing import Dict, Any, Optional

from anthropic import Anthropic
from PIL import Image

log = logging.getLogger(__name__)

# Görseller için "ev stili" — tüm üretimlerde uygulanır
SAFE_STYLE_HINT = (
    "Professional medical/healthcare blog hero image. Clean, modern editorial "
    "illustration style. Soft, muted color palette (teals, sage greens, warm "
    "neutrals, subtle gold accents). Minimalist composition with generous "
    "negative space. No text, no logos, no graphic blood, no exposed surgical "
    "anatomy, no distressed patients, no syringes pointing at viewer. "
    "Calm, reassuring, suitable for a respected orthopedic surgeon's blog. "
    "Wide landscape aspect ratio."
)


class ImageGenerator:
    def __init__(
        self,
        anthropic_key: str,
        openai_key: str,
        claude_model: str = "claude-sonnet-4-5",
        image_model: str = "gpt-image-1",
        image_quality: str = "medium",
        image_size: str = "1536x1024",
    ):
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY tanımlanmamış")
        if not openai_key:
            raise ValueError(
                "OPENAI_API_KEY tanımlanmamış. Görsel üretimi için OpenAI API "
                "anahtarı gerekli (https://platform.openai.com/api-keys)."
            )
        # OpenAI lazy import
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai Python paketi kurulu değil. requirements.txt'ye 'openai' "
                "ekleyip yeniden deploy edin."
            )

        self.claude = Anthropic(api_key=anthropic_key)
        self.openai = OpenAI(api_key=openai_key)
        self.claude_model = claude_model
        self.image_model = image_model
        self.image_quality = image_quality
        self.image_size = image_size

    def craft_prompt(self, title: str, excerpt: str = "") -> str:
        """Türkçe başlığı güvenli İngilizce image prompt'a çevirir."""
        system = (
            "You craft image-generation prompts for a Turkish orthopedic surgeon's "
            "patient-friendly blog. Each prompt must be ENGLISH, 50-80 words.\n\n"
            "AVOID at all costs:\n"
            "- Graphic anatomy, blood, exposed bone or muscle, surgical scenes\n"
            "- Distressed, crying, or suffering patients\n"
            "- Sharp instruments pointed at the viewer\n"
            "- Text, words, letters, numbers, logos, watermarks\n"
            "- Anything alarming or unprofessional\n\n"
            "PREFER:\n"
            "- Abstract concepts (healing, balance, movement, support)\n"
            "- Clean modern medical illustrations (textbook style, simplified)\n"
            "- Modern medical equipment in clean clinical settings\n"
            "- Active healthy people (post-recovery vibe, walking, exercise)\n"
            "- Anatomical line art (skeletal/joint structures, simplified)\n"
            "- Calm clinical environments, soft natural light\n\n"
            "Style: professional, clean, modern, minimalist, soft palette, editorial.\n\n"
            "Return ONLY the prompt text. No quotes, no preamble, no explanation."
        )
        user = (
            f"TURKISH TITLE: {title}\n"
            f"EXCERPT: {(excerpt or '')[:400]}\n\n"
            "Write the image generation prompt now."
        )
        r = self.claude.messages.create(
            model=self.claude_model,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        crafted = "".join((b.text or "") for b in r.content if hasattr(b, "text")).strip()
        # Style hint'i ekle (bütünleşik tarz için)
        return f"{crafted}\n\nStyle requirements: {SAFE_STYLE_HINT}"

    def generate(
        self,
        title: str,
        excerpt: str = "",
        upload_dir: str = "./static/images/uploads",
    ) -> Dict[str, Any]:
        """
        Görsel üretir, kaydeder ve URL döner.
        Returns: { url, prompt, filename, size_bytes, model }
        """
        prompt = self.craft_prompt(title, excerpt)
        log.info(f"Generated prompt for '{title[:40]}': {prompt[:100]}...")

        # Görseli oluştur
        try:
            result = self.openai.images.generate(
                model=self.image_model,
                prompt=prompt,
                size=self.image_size,
                quality=self.image_quality,
                n=1,
            )
        except Exception as e:
            # OpenAI hatalarını anlamlı hale getir
            msg = str(e)
            if "billing" in msg.lower() or "quota" in msg.lower():
                raise RuntimeError(
                    "OpenAI hesabınızda kredi yok. "
                    "https://platform.openai.com/settings/organization/billing → Add credit"
                )
            if "moderation" in msg.lower() or "safety" in msg.lower():
                raise RuntimeError(
                    "Üretilen prompt OpenAI içerik filtresini geçemedi. "
                    "Genelde tıbbi/cerrahi konular için olur. Manuel görsel ekleyin."
                )
            raise

        # Base64'ten dosyaya
        if not result.data or not result.data[0].b64_json:
            raise RuntimeError("OpenAI yanıtında görsel verisi bulunamadı.")

        img_bytes = base64.b64decode(result.data[0].b64_json)

        # PIL ile aç, JPEG olarak kaydet (boyut tasarrufu)
        try:
            img = Image.open(io.BytesIO(img_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            # Çok büyükse küçült
            img.thumbnail((1600, 1200), Image.LANCZOS)
        except Exception as e:
            raise RuntimeError(f"Görsel açılamadı: {e}")

        os.makedirs(upload_dir, exist_ok=True)
        filename = f"ai_cover_{int(time.time())}.jpg"
        path = os.path.join(upload_dir, filename)
        img.save(path, "JPEG", quality=88, optimize=True)
        size_bytes = os.path.getsize(path)

        return {
            "url": f"/static/images/uploads/{filename}",
            "filename": filename,
            "prompt": prompt,
            "size_bytes": size_bytes,
            "model": self.image_model,
        }
