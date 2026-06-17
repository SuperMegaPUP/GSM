import hashlib
import re
from typing import Optional

from app.models.models import FluidType

# =============================================================
# Константы для нормализатора
# =============================================================

SAE_PATTERN = re.compile(r'(\d{1,2}[Ww]-\d{1,2})')

API_CLASS_PATTERN = re.compile(r'^([A-Z]{2,3}(?:-\d+)?)')

OIL_BRANDS = [
    "Gazpromneft", "G-Energy", "G-Box", "G-Profy", "Mobil", "Shell",
    "Castrol", "Motul", "Liqui Moly", "Total", "Elf", "BP", "Rosneft",
    "Lukoil", "TNK", "Kixx", "ZIC", "Idemitsu", "Eneos", "Petro-Canada",
    "Exxon", "Esso", "Valvoline", "Fuchs", "Ravenol", "Addinol", "Xado",
    "Sintec", "Revolux", "GT-Oil",
]

NODE_TO_FLUID_TYPE: dict[str, FluidType] = {
    "ENGINE": FluidType.engine_oil,
    "MANUAL_TRANSMISSION": FluidType.manual_transmission,
    "AUTO_TRANSMISSION": FluidType.auto_transmission,
    "CVT": FluidType.cvt,
    "TRANSFER_CASE": FluidType.transfer_case,
    "FRONT_DIFF": FluidType.differential,
    "REAR_DIFF": FluidType.differential,
}


# =============================================================
# Нормализатор жидкости
# =============================================================

class FluidNormalizer:
    @staticmethod
    def make_hash(
        brand: Optional[str],
        product_line: Optional[str],
        viscosity: Optional[str],
        api_class: Optional[str],
    ) -> str:
        raw = "|".join(str(v or "") for v in [brand, product_line, viscosity, api_class])
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def extract_viscosity(text: str) -> tuple[Optional[str], str]:
        m = SAE_PATTERN.search(text)
        if m:
            vis = m.group(1)
            remainder = text.replace(m.group(0), "").strip()
            return vis, re.sub(r' {2,}', ' ', remainder).strip()
        return None, text

    @staticmethod
    def extract_brand(text: str) -> tuple[Optional[str], str]:
        lower = text.lower()
        for brand in sorted(OIL_BRANDS, key=len, reverse=True):
            if lower.startswith(brand.lower()):
                remainder = text[len(brand):].strip()
                return brand, remainder
        m = re.match(r'^([A-Za-z\u00C0-\u024f][\w\-.]{1,30}?)\s', text)
        if m:
            return m.group(1), text[m.end():].strip()
        return None, text

    @staticmethod
    def normalize(
        fluid_name: Optional[str],
        viscosity_from_parser: Optional[str],
        api_class_from_parser: Optional[str],
        node_type: Optional[str],
    ) -> dict:
        brand: Optional[str] = None
        product_line: Optional[str] = None
        viscosity = viscosity_from_parser
        api_class = api_class_from_parser

        if fluid_name:
            raw = fluid_name

            extracted_vis, remainder = FluidNormalizer.extract_viscosity(raw)
            if extracted_vis and not viscosity:
                viscosity = extracted_vis

            extracted_brand, remainder = FluidNormalizer.extract_brand(remainder)
            if extracted_brand:
                brand = extracted_brand

            product_line = remainder if remainder else None

            if not api_class:
                m = API_CLASS_PATTERN.search(remainder)
                if m:
                    api_class = m.group(1)
        else:
            raw = ""

        parts = []
        if brand:
            parts.append(brand)
        if product_line:
            parts.append(product_line)
        if not parts:
            if fluid_name:
                parts.append(fluid_name)
            else:
                type_label = (node_type or "ENGINE").replace("_", " ").title()
                label = f"{type_label} Oil"
                if viscosity:
                    label += f" {viscosity}"
                if api_class:
                    label += f" ({api_class})"
                parts.append(label)
        canonical_name = " ".join(parts)

        fluid_type = NODE_TO_FLUID_TYPE.get(node_type or "", FluidType.engine_oil)

        hash_sig = FluidNormalizer.make_hash(brand, product_line, viscosity, api_class)

        return {
            "canonical_name": canonical_name,
            "brand": brand,
            "product_line": product_line,
            "viscosity_sae": viscosity,
            "api_class": api_class,
            "fluid_type": fluid_type,
            "hash_signature": hash_sig,
        }


# =============================================================
# Парсер годов выпуска
# =============================================================

def normalize_years(years_str: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    if not years_str:
        return None, None

    year_start: Optional[int] = None
    year_end: Optional[int] = None

    m = re.match(r'(\d{2,4})\.\d{2}[ -]*(\d{2,4})\.\d{2}', years_str)
    if m:
        y1 = _normalize_year(m.group(1))
        y2 = _normalize_year(m.group(2))
        if y1:
            year_start = y1
        if y2:
            year_end = y2
    else:
        m = re.match(r'(\d{2,4})', years_str)
        if m:
            year_start = _normalize_year(m.group(1))

    return year_start, year_end


def _normalize_year(y: str) -> Optional[int]:
    try:
        val = int(y)
        if val < 100:
            val += 2000 if val <= 50 else 1900
        return val if 1960 <= val <= 2030 else None
    except (ValueError, TypeError):
        return None


# =============================================================
# Общие хэш-функции
# =============================================================

def compute_variant_hash(
    model_id: str, engine_code: Optional[str],
    body_type: Optional[str], engine_volume: Optional[str],
) -> str:
    raw = "|".join(str(v or "") for v in [model_id, engine_code, body_type, engine_volume])
    return hashlib.sha256(raw.encode()).hexdigest()
