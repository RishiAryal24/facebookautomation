import io
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class GraphicCardService:
    """Generates high-resolution 1080x1080 branded marketing cards with zero external API dependencies."""

    def __init__(self):
        self._font_cache: Dict[Tuple[str, int], ImageFont.ImageFont] = {}

    def _get_font(self, font_type: str, size: int) -> ImageFont.ImageFont:
        key = (font_type, size)
        if key in self._font_cache:
            return self._font_cache[key]

        font_candidates = {
            "bold": ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "arial.ttf"],
            "regular": ["segoeui.ttf", "arial.ttf", "calibri.ttf"],
        }.get(font_type, ["segoeui.ttf", "arial.ttf"])

        for candidate in font_candidates:
            try:
                font = ImageFont.truetype(candidate, size)
                self._font_cache[key] = font
                return font
            except Exception:
                continue

        font = ImageFont.load_default()
        self._font_cache[key] = font
        return font

    def _extract_theme_info(self, prompt: str, topic: Optional[str] = None) -> Dict[str, Any]:
        text = f"{topic or ''} {prompt}".lower()

        # Product detection
        if "insight360" in text:
            return {
                "product": "INSIGHT360",
                "category": "BUSINESS INTELLIGENCE & TELEMETRY",
                "h1_line1": "Transform Complex Data",
                "h1_line2": "Into Actionable Growth",
                "tagline": "Automated real-time analytics designed for modern enterprise scaling.",
                "kpis": [
                    ("REVENUE GROWTH", "+42.8%", "#10B981"),
                    ("TIME SAVED", "-65%", "#F59E0B"),
                    ("DATA ACCURACY", "99.9%", "#06B6D4"),
                ],
                "chart_title": "REAL-TIME PERFORMANCE MONITORING",
                "chart_points": [(130, 770), (240, 730), (360, 690), (480, 715), (600, 620), (720, 580), (840, 530), (950, 510)],
                "website": "insight360.pyloomtech.com",
                "cta": "EXPLORE INSIGHT360 →",
            }

        if any(w in text for w in ("ai", "automation", "workflow", "bot")):
            return {
                "product": "PYLOOM AUTOMATION",
                "category": "ENTERPRISE WORKFLOW ENGINE",
                "h1_line1": "Automate Complex Tasks",
                "h1_line2": "With Intelligent Precision",
                "tagline": "High-speed AI automation that scales operations with zero downtime.",
                "kpis": [
                    ("TASKS AUTOMATED", "50,000+", "#10B981"),
                    ("RESPONSE TIME", "< 1 SEC", "#06B6D4"),
                    ("MANUAL WORK", "-80%", "#F59E0B"),
                ],
                "chart_title": "AUTOMATION THROUGHPUT VELOCITY",
                "chart_points": [(130, 790), (240, 760), (360, 710), (480, 670), (600, 610), (720, 560), (840, 520), (950, 490)],
                "website": "pyloomtech.com",
                "cta": "START AUTOMATING →",
            }

        if any(w in text for w in ("hospital", "hms", "clinic", "health", "doctor")):
            return {
                "product": "PYLOOM HMS",
                "category": "CLINICAL & HOSPITAL OS",
                "h1_line1": "Unified Hospital Management",
                "h1_line2": "For Better Patient Care",
                "tagline": "Seamless digital appointments, billing, OPD, and medical records.",
                "kpis": [
                    ("PATIENT WAIT TIME", "-70%", "#10B981"),
                    ("RECORD ACCURACY", "100%", "#06B6D4"),
                    ("OPERATING EFFICIENCY", "+45%", "#F59E0B"),
                ],
                "chart_title": "CLINICAL CAPACITY & CARE TELEMETRY",
                "chart_points": [(130, 760), (240, 710), (360, 670), (480, 690), (600, 620), (720, 570), (840, 540), (950, 520)],
                "website": "pyloomtech.com/hms",
                "cta": "EXPLORE HMS →",
            }

        # Default SaaS / Business Technology
        return {
            "product": "PYLOOM TECHNOLOGIES",
            "category": "NEXT-GEN ENTERPRISE SOLUTIONS",
            "h1_line1": "Scale Your Business",
            "h1_line2": "With Digital Innovation",
            "tagline": "Modern cloud tools engineered to accelerate efficiency and customer trust.",
            "kpis": [
                ("BUSINESS EFFICIENCY", "+55%", "#10B981"),
                ("COST REDUCTION", "-35%", "#F59E0B"),
                ("SYSTEM RELIABILITY", "99.9%", "#06B6D4"),
            ],
            "chart_title": "BUSINESS VELOCITY & SCALING TRAJECTORY",
            "chart_points": [(130, 780), (240, 740), (360, 710), (480, 680), (600, 620), (720, 590), (840, 530), (950, 510)],
            "website": "pyloomtech.com",
            "cta": "LEARN MORE →",
        }

    def generate_card_image(self, prompt: str, topic: Optional[str] = None) -> bytes:
        info = self._extract_theme_info(prompt, topic)

        img = Image.new("RGB", (1080, 1080), color="#070D18")

        # Fonts
        font_badge = self._get_font("bold", 20)
        font_h1 = self._get_font("bold", 52)
        font_tagline = self._get_font("regular", 22)
        font_kpi_lbl = self._get_font("bold", 16)
        font_kpi_val = self._get_font("bold", 38)
        font_chart_lbl = self._get_font("bold", 18)
        font_axis = self._get_font("regular", 15)
        font_footer = self._get_font("bold", 20)
        font_cta = self._get_font("bold", 20)

        # 1. Subtle Background Grid
        draw = ImageDraw.Draw(img)
        for y in range(0, 1080, 54):
            draw.line([(0, y), (1080, y)], fill="#0E192D", width=1)
        for x in range(0, 1080, 54):
            draw.line([(x, 0), (x, 1080)], fill="#0E192D", width=1)

        # Ambient Glow Layer
        glow_overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_overlay)
        for r in range(400, 0, -20):
            alpha = int((400 - r) / 25)
            glow_draw.ellipse([850 - r, 180 - r, 850 + r, 180 + r], fill=(0, 210, 255, alpha))
            glow_draw.ellipse([150 - r, 850 - r, 150 + r, 850 + r], fill=(99, 102, 241, alpha))
        img = Image.alpha_composite(Image.new("RGBA", (1080, 1080), (7, 13, 24, 255)), glow_overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 2. Header Badge
        badge_text = f"{info['product']}  •  {info['category']}"
        draw.rounded_rectangle([70, 60, 560, 106], radius=22, fill="#0D223A", outline="#00D2FF", width=2)
        draw.text((95, 73), badge_text, font=font_badge, fill="#00F0FF")

        # 3. Main Headline & Subtitle
        draw.text((70, 130), info["h1_line1"], font=font_h1, fill="#FFFFFF")
        draw.text((70, 192), info["h1_line2"], font=font_h1, fill="#00F0FF")
        draw.text((70, 260), info["tagline"], font=font_tagline, fill="#94A3B8")

        # 4. KPI Metric Cards
        kpi_cards = [(info["kpis"][0], 70), (info["kpis"][1], 400), (info["kpis"][2], 730)]
        for (lbl, val, col), cx in kpi_cards:
            draw.rounded_rectangle([cx, 310, cx + 280, 435], radius=16, fill="#0B1628", outline="#1E3354", width=2)
            draw.rounded_rectangle([cx + 20, 320, cx + 70, 324], radius=2, fill=col)
            draw.text((cx + 20, 340), lbl, font=font_kpi_lbl, fill="#8EACC8")
            draw.text((cx + 20, 370), val, font=font_kpi_val, fill=col)

        # 5. Telemetry Chart Box
        chart_box = [70, 465, 1010, 895]
        draw.rounded_rectangle(chart_box, radius=20, fill="#091426", outline="#1E3354", width=2)
        draw.text((105, 490), info["chart_title"], font=font_chart_lbl, fill="#00F0FF")
        draw.text((820, 490), "● LIVE TELEMETRY", font=font_axis, fill="#10B981")

        for cy in [560, 640, 720, 800]:
            draw.line([(105, cy), (975, cy)], fill="#132742", width=1)

        pts = info["chart_points"]

        # Gradient Fill Under Curve
        fill_overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
        fill_draw = ImageDraw.Draw(fill_overlay)
        poly = [(pts[0][0], 840)] + pts + [(pts[-1][0], 840)]
        fill_draw.polygon(poly, fill=(0, 240, 255, 35))
        img = Image.alpha_composite(img.convert("RGBA"), fill_overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Glowing Line & Data Nodes
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill="#00F0FF", width=5)
        for px, py in pts:
            draw.ellipse([px - 7, py - 7, px + 7, py + 7], fill="#FFFFFF", outline="#00F0FF", width=3)

        x_labels = [("Q1", 130), ("Q2", 380), ("Q3", 640), ("Q4", 950)]
        for x_txt, px in x_labels:
            draw.text((px - 10, 850), x_txt, font=font_axis, fill="#637D9E")

        # 6. Footer Brand & CTA
        draw.text((70, 955), f"PyLoom Technologies  •  {info['website']}", font=font_footer, fill="#94A3B8")
        cta_box = [720, 935, 1010, 995]
        draw.rounded_rectangle(cta_box, radius=14, fill="#00F0FF")
        draw.text((745, 953), info["cta"], font=font_cta, fill="#070D18")

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()


graphic_card_service = GraphicCardService()
