"""
PVL Parser — парсит "Каталог подбора PVL.xlsx" (Газпромнефть).

Структура файла (Row 0-2 заголовки, Row 3+ данные):
  - Row 0: пустая
  - Row 1: заголовки категорий (Легковые | Двигатель | ...)
  - Row 2: пустая (разделитель)
  - Row 3+: строки (бренды, модели, сноски, Diesel-секции)

Колонки (0-indexed):
  0-2:   Модель | Год | Объём двигателя (объём масла)
  3-7:   ДВИГАТЕЛЬ    (основное | альт1 | альт2 | маркер | объём)
  8-10:  МКПП         (основное | альт1 | маркер)
  11-14: АКПП         (основное | альт1 | маркер | объём)
  15-18: ДИФФЕРЕНЦИАЛ (основное | альт1 | маркер | объём)
  19-21: ОХЛАЖДЕНИЕ   (основное | альт1 | объём)
  22-24: ТОРМОЗА      (основное | альт1 | объём)
  25-27: ГУР          (основное | альт1 | объём)
  28-30: ПОДВЕСКА     (основное | альт1 | объём)
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================
# Data structures
# =============================================================

@dataclass
class PVLRecommendation:
    node_type: str
    fluid_name: str
    fluid_brand: Optional[str] = None
    viscosity_sae: Optional[str] = None
    recommendation_rank: int = 1
    is_oem: bool = False
    volume_liters: Optional[str] = None
    applicability_conditions: dict = field(default_factory=dict)


@dataclass
class PVLVehicle:
    brand: str
    model: str
    generation: Optional[str] = None
    sub_model: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    engine_volume: Optional[float] = None
    fuel_type: str = 'petrol'
    market: str = 'EU'
    attributes: dict = field(default_factory=dict)
    recommendations: list[PVLRecommendation] = field(default_factory=list)
    row_number: int = 0


# =============================================================
# Константы
# =============================================================

NODE_COLUMNS = {
    'ENGINE':              {'main': 3,  'alt1': 4,  'alt2': 5,  'volume': 7,  'marker': 6},
    'MANUAL_TRANSMISSION': {'main': 8,  'alt1': 9,  'alt2': None, 'volume': None, 'marker': 10},
    'AUTO_TRANSMISSION':   {'main': 11, 'alt1': 12, 'alt2': None, 'volume': 14, 'marker': 13},
    'FRONT_DIFF':          {'main': 15, 'alt1': 16, 'alt2': None, 'volume': 18, 'marker': 17},
    'COOLANT':             {'main': 19, 'alt1': 20, 'alt2': None, 'volume': 21, 'marker': None},
    'BRAKE':               {'main': 22, 'alt1': 23, 'alt2': None, 'volume': 24, 'marker': None},
    'STEERING':            {'main': 25, 'alt1': 26, 'alt2': None, 'volume': 27, 'marker': None},
    'SUSPENSION':          {'main': 28, 'alt1': 29, 'alt2': None, 'volume': 30, 'marker': None},
}

KNOWN_BRANDS = {
    'AUDI', 'BMW', 'MERCEDES-BENZ', 'HONDA', 'HONDA (RUS)', 'HONDA (USA)',
    'TOYOTA', 'NISSAN', 'NISSAN (USA)', 'MITSUBISHI', 'MAZDA', 'SUBARU',
    'LEXUS', 'LEXUS (USA)', 'INFINITI', 'HYUNDAI', 'HYUNDAI (RUS)', 'HYUNDAI (USA)',
    'KIA', 'LAND ROVER', 'JAGUAR', 'JEEP', 'CHRYSLER', 'DODGE',
    'DAIHATSU', 'DAIHATSU (RUS)', 'RENAULT', 'RENAULT (RUS)',
    'CITROËN', 'PEUGEOT', 'FORD', 'FORD (RUS)', 'FORD (USA)',
    'VOLVO', 'VW', 'VOLKSWAGEN', 'OPEL', 'SKODA', 'SEAT',
    'LADA (SHIGULI/VAZ)', 'LIFAN', 'GEELY', 'CHERY', 'TAGAZ',
    'MINI', 'FIAT', 'ALFA ROMEO', 'PORSCHE', 'SAAB',
}

FOOTNOTE_NODE_MAP = [
    (r'раздаточн', 'TRANSFER_CASE'),
    (r'передний\s+дифференциал', 'FRONT_DIFF'),
    (r'задний\s+дифференциал', 'REAR_DIFF'),
    (r'самоблок', 'FRONT_DIFF'),
    (r'передний\s+и\s+задний', 'FRONT_DIFF'),
    (r'дифференциал', 'FRONT_DIFF'),
    (r'вариатор', 'CVT'),
    (r'автоматическ', 'AUTO_TRANSMISSION'),
    (r'коробк[ау]\s+передач', 'MANUAL_TRANSMISSION'),
    (r'сцепление\s+haldex', 'TRANSFER_CASE'),
    (r'гидравлическ', 'STEERING'),
    (r'подвеск', 'SUSPENSION'),
]

GENERATION_PATTERNS = [
    re.compile(r'^[A-Z]\d+\s*-\s*\w+'),           # "E46 - 3 Series"
    re.compile(r'^[A-Z]+-Class\s*\([A-Z]\d+\)'),   # "A-Class (W168)"
    re.compile(r'^[A-Z]+\s*\([A-Z]\d+\)'),          # "X5 (E53)"
]

FOOTNOTE_PATTERN = re.compile(r'^([a-z]{1,2})\s{2,}(.+)')


# =============================================================
# Helpers
# =============================================================

def _clean(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() in ('nan', 'none', '-'):
        return None
    return s


def _normalize_brand(brand: str) -> str:
    if not brand:
        return ""
    brand = re.sub(r'\s*\([A-Z]+\)\s*', '', brand)
    brand = brand.replace('MERCEDES-BENZ', 'Mercedes-Benz')
    brand = brand.replace('CITROËN', 'Citroën')
    brand = brand.replace('SHIGULI/VAZ', 'Lada')
    return brand.strip().title().replace('Vw', 'VW').replace('Bmw', 'BMW')


def _parse_year_range(year_str: str) -> tuple[Optional[int], Optional[int]]:
    if not year_str:
        return None, None

    def _expand(y2: int) -> int:
        return 2000 + y2 if y2 <= 30 else 1900 + y2

    s = str(year_str).strip()

    m = re.match(r"^'(\d{2})\s*[-–]\s*$", s)
    if m:
        return _expand(int(m.group(1))), None

    m = re.match(r"^'(\d{2})\s*[-–]\s*'?(\d{2})\s*$", s)
    if m:
        return _expand(int(m.group(1))), _expand(int(m.group(2)))

    return None, None


def _parse_engine_displacement(model_name: str) -> Optional[float]:
    if not model_name:
        return None
    m = re.search(r'\b(\d+[.,]\d+)\s*(?:TFSI|TSI|FSI|TDI|d|i|V|T|CDI|CGI|GDI)?', model_name)
    if m:
        try:
            return float(m.group(1).replace(',', '.'))
        except ValueError:
            return None
    return None


def _parse_volume_numeric(v: Optional[str]) -> Optional[float]:
    """Парсит объём в литрах из PVL-значения. Возвращает первое число или None."""
    if not v:
        return None
    s = str(v).strip().replace(',', '.')
    s = re.sub(r'\s*[-–]\s*', '-', s)
    if s in ('-', '<', '< ', '·', ''):
        return None
    m = re.match(r'<+\s*([\d.]+)', s)
    if m:
        return float(m.group(1))
    m = re.match(r'([\d.]+)', s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _extract_viscosity(name: str) -> Optional[str]:
    if not name:
        return None
    m = re.search(r'(\d+[Ww]-?\d+)', name)
    return m.group(1).replace('W-', 'W-') if m else None


def _extract_brand(name: str) -> Optional[str]:
    if not name:
        return None
    for brand in ['G-Energy', 'Gazpromneft', 'G-Box', 'G-Truck', 'G-Force']:
        if name.startswith(brand):
            return brand
    return None


# =============================================================
# PVL Parser
# =============================================================

class PVLParser:
    def detect(self, file_path: str) -> bool:
        try:
            df = pd.read_excel(file_path, sheet_name=0, header=None, nrows=5)
            row1 = df.iloc[1].astype(str).str.strip().tolist()
            return any('Легковые автомобили' in v for v in row1 if v != 'nan')
        except Exception:
            return False

    def parse(
        self,
        file_path: str,
        df: Optional[pd.DataFrame] = None,
    ) -> list[PVLVehicle]:
        records: list[PVLVehicle] = []

        if df is None:
            df = pd.read_excel(file_path, sheet_name=0, header=None)

        current_brand: Optional[str] = None
        current_generation: Optional[str] = None
        in_diesel_section = False
        current_market = 'EU'

        for i in range(3, len(df)):
            row = df.iloc[i]
            col0 = _clean(row.iloc[0])

            if not col0:
                continue

            if col0 == 'Diesel':
                in_diesel_section = True
                continue

            if col0.upper().strip() in KNOWN_BRANDS:
                in_diesel_section = False
                current_brand = _normalize_brand(col0)
                current_generation = None
                if '(RUS)' in col0:
                    current_market = 'RU'
                elif '(USA)' in col0:
                    current_market = 'US'
                else:
                    current_market = 'EU'
                continue

            if any(p.match(col0) for p in GENERATION_PATTERNS):
                current_generation = col0
                continue

            footnote_m = FOOTNOTE_PATTERN.match(col0)
            if footnote_m:
                if records:
                    self._apply_footnote(records[-1], footnote_m)
                continue

            if not current_brand:
                continue

            model_name = col0
            if current_generation:
                model_name = f"{current_generation} {model_name}"

            year_str = _clean(row.iloc[1]) or ''
            year_start, year_end = _parse_year_range(year_str)
            engine_displacement = _parse_engine_displacement(model_name)

            engine_oil_volume_raw = _clean(row.iloc[2])

            veh = PVLVehicle(
                brand=current_brand,
                model=model_name,
                generation=current_generation,
                sub_model='Diesel' if in_diesel_section else None,
                year_start=year_start,
                year_end=year_end,
                engine_volume=engine_displacement,
                fuel_type='diesel' if in_diesel_section else 'petrol',
                market=current_market,
                attributes={
                    'engine_oil_volume_raw': engine_oil_volume_raw,
                },
                row_number=i,
            )

            for node_code, cols in NODE_COLUMNS.items():
                main_fluid = _clean(row.iloc[cols['main']]) if cols['main'] is not None and cols['main'] < len(row) else None
                alt1_fluid = _clean(row.iloc[cols['alt1']]) if cols['alt1'] is not None and cols['alt1'] < len(row) else None
                alt2_fluid = _clean(row.iloc[cols['alt2']]) if cols['alt2'] is not None and cols['alt2'] < len(row) else None
                col_vol = cols['volume']
                volume_raw = _clean(row.iloc[col_vol]) if col_vol is not None and col_vol < len(row) else None
                col_marker = cols['marker']
                marker = _clean(row.iloc[col_marker]) if col_marker is not None and col_marker < len(row) else None

                if main_fluid or alt1_fluid or alt2_fluid:
                    conditions = {}
                    if marker and marker not in (' ', '·'):
                        conditions['marker_code'] = marker
                    if in_diesel_section:
                        conditions['fuel_type'] = 'diesel'
                    if volume_raw and volume_raw not in ('-', '<', '< '):
                        conditions['volume_raw'] = volume_raw

                    if main_fluid and main_fluid not in ('-', '<', '< '):
                        veh.recommendations.append(PVLRecommendation(
                            node_type=node_code,
                            fluid_name=main_fluid,
                            fluid_brand=_extract_brand(main_fluid),
                            viscosity_sae=_extract_viscosity(main_fluid),
                            recommendation_rank=1,
                            is_oem=True,
                            volume_liters=volume_raw,
                            applicability_conditions=conditions.copy(),
                        ))

                    if alt1_fluid and alt1_fluid not in ('-',) and alt1_fluid != main_fluid:
                        veh.recommendations.append(PVLRecommendation(
                            node_type=node_code,
                            fluid_name=alt1_fluid,
                            fluid_brand=_extract_brand(alt1_fluid),
                            viscosity_sae=_extract_viscosity(alt1_fluid),
                            recommendation_rank=2,
                            is_oem=False,
                            volume_liters=volume_raw,
                            applicability_conditions=conditions.copy(),
                        ))

                    if alt2_fluid and alt2_fluid not in ('-',) and alt2_fluid != main_fluid and alt2_fluid != alt1_fluid:
                        veh.recommendations.append(PVLRecommendation(
                            node_type=node_code,
                            fluid_name=alt2_fluid,
                            fluid_brand=_extract_brand(alt2_fluid),
                            viscosity_sae=_extract_viscosity(alt2_fluid),
                            recommendation_rank=3,
                            is_oem=False,
                            volume_liters=volume_raw,
                            applicability_conditions=conditions.copy(),
                        ))

            if veh.recommendations:
                records.append(veh)

        return records

    def _apply_footnote(self, vehicle: PVLVehicle, footnote_match: re.Match) -> None:
        marker = footnote_match.group(1)
        body = footnote_match.group(2)

        node_code = None
        for pattern, code in FOOTNOTE_NODE_MAP:
            if re.search(pattern, body.lower()):
                node_code = code
                break
        if not node_code:
            return

        vol_match = re.search(r'([\d,\-\s]+)\s*л', body)
        volume_raw = vol_match.group(1).strip() if vol_match else None

        oil_part = body.split(':', 1)[-1] if ':' in body else body
        oils = [o.strip() for o in oil_part.split(';') if o.strip() and o.strip() not in ('-', '·')]
        if not oils:
            return

        existing_ranks = {r.recommendation_rank for r in vehicle.recommendations
                          if r.node_type == node_code}
        next_rank = max(existing_ranks) + 1 if existing_ranks else 1

        for oil_name in oils:
            vehicle.recommendations.append(PVLRecommendation(
                node_type=node_code,
                fluid_name=oil_name,
                fluid_brand=_extract_brand(oil_name),
                viscosity_sae=_extract_viscosity(oil_name),
                recommendation_rank=next_rank,
                is_oem=False,
                volume_liters=volume_raw,
                applicability_conditions={
                    'footnote_marker': marker,
                    'volume_raw': volume_raw,
                } if volume_raw else {'footnote_marker': marker},
            ))
            next_rank += 1


def flatten_to_raw_rows(vehicles: list[PVLVehicle]) -> list[dict]:
    """Конвертирует PVLVehicle в список dict[с полями для ETL.

    Каждая рекомендация становится одной строкой (как RawExcelRow).
    """
    rows: list[dict] = []
    for v in vehicles:
        for rec in v.recommendations:
            rows.append({
                'brand': v.brand,
                'model': v.model,
                'generation': v.generation,
                'sub_model': v.sub_model,
                'year_start': v.year_start,
                'year_end': v.year_end,
                'engine_volume': v.engine_volume,
                'fuel_type': v.fuel_type,
                'market': v.market,
                'attributes': v.attributes,
                'node_type': rec.node_type,
                'fluid_name': rec.fluid_name,
                'fluid_brand': rec.fluid_brand,
                'viscosity_sae': rec.viscosity_sae,
                'recommendation_rank': rec.recommendation_rank,
                'is_oem_recommendation': rec.is_oem,
                'volume_liters': rec.volume_liters,
                'applicability_conditions': rec.applicability_conditions,
                'source': 'pvl',
            })
    return rows


# =============================================================
# Тестовый блок (dry-run)
# =============================================================

if __name__ == '__main__':
    import json
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s | %(message)s',
    )

    path = sys.argv[1] if len(sys.argv) > 1 else '/home/z/my-project/upload/Каталог подбора PVL.xlsx'
    print(f"Файл: {path}")

    parser = PVLParser()
    if not parser.detect(path):
        print("❌ Не PVL-формат")
        sys.exit(1)

    print("✅ PVL-формат обнаружен\n")

    vehicles = parser.parse(path)
    print(f"✅ Транспортных средств: {len(vehicles)}")

    total_recs = sum(len(v.recommendations) for v in vehicles)
    print(f"✅ Рекомендаций: {total_recs}")

    brands = set(v.brand for v in vehicles)
    print(f"✅ Брендов: {len(brands)} — {', '.join(sorted(brands))}")

    nodes = {}
    for v in vehicles:
        for rec in v.recommendations:
            nodes[rec.node_type] = nodes.get(rec.node_type, 0) + 1
    print(f"\n🔧 По узлам:")
    for node, cnt in sorted(nodes.items(), key=lambda x: -x[1]):
        print(f"   {node:25s} {cnt}")

    ranks = {}
    for v in vehicles:
        for rec in v.recommendations:
            ranks[rec.recommendation_rank] = ranks.get(rec.recommendation_rank, 0) + 1
    print(f"\n🎖️ По рангам:")
    for rank in sorted(ranks):
        print(f"   rank {rank}: {ranks[rank]}")

    print(f"\n📋 Первые 3 записи:")
    for v in vehicles[:3]:
        print(f"\n  [{v.row_number}] {v.brand} {v.model} ({v.year_start or '?'}-{v.year_end or '?'})")
        print(f"      Market: {v.market}, Fuel: {v.fuel_type}, Volume: {v.engine_volume}")
        for rec in v.recommendations[:3]:
            cond = f" {rec.applicability_conditions}" if rec.applicability_conditions else ""
            vol = f" vol={rec.volume_liters}" if rec.volume_liters else ""
            print(f"        [{rec.node_type:20s}] rank={rec.recommendation_rank} {rec.fluid_name[:40]:40s}{vol}{cond}")

    print(f"\n{'=' * 60}")
    print(f"Flat rows: {len(flatten_to_raw_rows(vehicles))}")
    print(f"{'=' * 60}")

    # Сохраняем flat dump для отладки
    flat = flatten_to_raw_rows(vehicles)
    with open('/tmp/pvl_flat.json', 'w') as f:
        json.dump(flat[:100], f, ensure_ascii=False, indent=2)
    print("Первые 100 flat-строк сохранены в /tmp/pvl_flat.json")
