"""
GSM PVL Catalog Importer — STANDALONE SCRIPT
==============================================

Готовый скрипт для запуска на проекте. Делает всё:
  1. Парсит "Каталог подбора PVL.xlsx"
  2. Показывает детальный отчёт по тому, что распарсилось
  3. Заливает в БД (vehicles + vehicle_recommendations)
  4. Делает дедупликацию и валидацию

Запуск:
  pip install openpyxl pandas psycopg2-binary sqlalchemy-asyncio asyncpg
  python import_pvl.py --dry-run    # только отчёт, без записи в БД
  python import_pvl.py              # с записью в БД

Перед запуском:
  - Применена миграция migration_vehicles_v2.sql
  - В .env указан DATABASE_URL=postgresql+asyncpg://gsm:gsm@localhost:5432/gsm
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import UUID

import pandas as pd
from openpyxl import load_workbook

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


# ============================================================================
# 1. DATA MODELS (унифицированные с catalog_parsers.py)
# ============================================================================

@dataclass
class FluidRecommendation:
    node_code: str
    fluid_name: str
    fluid_brand: Optional[str] = None
    viscosity_sae: Optional[str] = None
    recommendation_rank: int = 1
    is_oem: bool = False
    volume_liters: Optional[str] = None
    applicability_conditions: dict = field(default_factory=dict)
    notes: Optional[str] = None


@dataclass
class VehicleRecord:
    vehicle_type: str = 'passenger_car'
    brand: str = ''
    model: str = ''
    generation: Optional[str] = None
    sub_model: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    market: Optional[str] = None
    attributes: dict = field(default_factory=dict)
    external_codes: dict = field(default_factory=dict)
    source: str = 'pvl'
    recommendations: list[FluidRecommendation] = field(default_factory=list)
    row_number: int = 0  # для отладки

    def source_hash(self) -> str:
        key = f"{self.vehicle_type}|{self.brand}|{self.model}|{self.generation or ''}|{self.sub_model or ''}|{self.year_start or ''}|{self.year_end or ''}"
        for code, val in sorted(self.external_codes.items()):
            key += f"|{code}:{val}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


# ============================================================================
# 2. PVL PARSER — детальная реализация с отладкой
# ============================================================================

class PVLParser:
    """
    Парсер "Каталог подбора PVL.xlsx" (Газпромнефть).

    Структура файла:
      - Row 0: пустая
      - Row 1: заголовки категорий (Легковые | Двигатель | Ручная трансмиссия | ...)
      - Row 2: пустая (разделитель)
      - Row 3: бренд (merged, AUDI)
      - Row 4+: модели с характеристиками
      - Diesel-секции: merged row 'Diesel' внутри бренда
      - Сноски: merged rows типа 'a  Раздаточная коробка: 0,36-0,38 л ...'
      - Подзаголовки поколений: 'E46 - 3 Series', 'A-Class (W168)', и т.д.

    Колонки (31 шт):
      0-2: Идентификация (Модель | Год | Объём двигателя)
      3-7: ДВИГАТЕЛЬ (основное | альт1 | альт2 | маркер | объём)
      8-10: МКПП (основное | альт1 | маркер)
      11-14: АКПП (основное | альт1 | маркер | объём)
      15-18: ДИФФЕРЕНЦИАЛ (основное | альт1 | маркер | объём)
      19-21: ОХЛАЖДЕНИЕ (основное | альт1 | объём)
      22-24: ТОРМОЗА (основное | альт1 | объём)
      25-27: ГУР (основное | альт1 | объём)
      28-30: ПОДВЕСКА (основное | альт1 | объём)
    """

    NODE_COLUMNS = {
        'ENGINE':              {'main': 3,  'alt1': 4,  'alt2': 5,  'volume': 7,  'marker': 6},
        'MANUAL_TRANSMISSION': {'main': 8,  'alt1': 9,  'alt2': None, 'volume': None, 'marker': 10},
        'AUTO_TRANSMISSION':   {'main': 11, 'alt1': 12, 'alt2': None, 'volume': 14, 'marker': 13},
        'DIFFERENTIAL':        {'main': 15, 'alt1': 16, 'alt2': None, 'volume': 18, 'marker': 17},
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
        'MINI', 'FIAT', 'ALFA ROMEO', 'PORSCHE', 'SAAB', 'JAGUAR',
    }

    # ─── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _clean(v) -> Optional[str]:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip()
        if not s or s.lower() in ('nan', 'none', '-'):
            return None
        return s

    @staticmethod
    def _normalize_brand(brand: str) -> str:
        if not brand:
            return ""
        brand = re.sub(r'\s*\([A-Z]+\)\s*', '', brand)
        # Особые случаи
        brand = brand.replace('MERCEDES-BENZ', 'Mercedes-Benz')
        brand = brand.replace('CITROËN', 'Citroën')
        brand = brand.replace('SHIGULI/VAZ', 'Lada')
        return brand.strip().title().replace('Vw', 'VW').replace('Bmw', 'BMW')

    @staticmethod
    def _parse_year_range(year_str: str) -> tuple[Optional[int], Optional[int]]:
        """Парсит диапазон лет. PVL использует апостроф: '10- или '00-'05 или '95-'99.

        ВАЖНО: 2-значный год > 30 → 19xx, иначе 20xx.
        (Текущий год 2026, так что '30 → 2030, '31 → 1931)
        """
        if not year_str:
            return None, None
        s = str(year_str).strip()

        def expand_year(y2: int) -> int:
            """2-значный год → 4-значный: '30 → 2030, '31 → 1931, '95 → 1995."""
            return 2000 + y2 if y2 <= 30 else 1900 + y2

        # '10-  →  2010 - настоящее время
        m = re.match(r"^'(\d{2})\s*[-–]\s*$", s)
        if m:
            return expand_year(int(m.group(1))), None

        # '00-'05  →  2000 - 2005  (второй апостроф опционален)
        m = re.match(r"^'(\d{2})\s*[-–]\s*'?(\d{2})\s*$", s)
        if m:
            y1, y2 = m.groups()
            return expand_year(int(y1)), expand_year(int(y2))

        return None, None

    @staticmethod
    def _parse_engine_displacement_from_model(model_name: str) -> Optional[float]:
        """Извлекает объём двигателя из названия модели.

        Примеры:
          'A1 1.2 TFSI' → 1.2
          'A3 1.6, 1.8 20V, Turbo' → 1.6 (берём первый)
          '118d, 120d' → None (объём не указан в названии)
          'X5 3.0d' → 3.0
        """
        if not model_name:
            return None
        # Ищем число вида X.Y или X,Y в начале названия (после букв)
        m = re.search(r'\b(\d+[.,]\d+)\s*(?:TFSI|TSI|FSI|TDI|d|i|V|T|CDI|CGI|GDI)?', model_name)
        if m:
            try:
                return float(m.group(1).replace(',', '.'))
            except ValueError:
                return None
        return None

    @staticmethod
    def _safe_displacement(d: Optional[str]) -> Optional[float]:
        if not d:
            return None
        s = str(d).strip().replace(',', '.')
        s = re.sub(r'[^\d.\-/*]', '', s)
        if not s or s in ('-', '*', '/'):
            return None
        m = re.match(r'^([\d.]+)', s)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _normalize_volume(v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        s = str(v).strip().replace(',', '.')
        s = re.sub(r'\s*-\s*', '-', s)
        if s in ('-', '<', '< ', '·', ''):
            return None
        # "<" значит "less than" — сохраняем как есть
        if s.startswith('<'):
            return s
        return s

    @staticmethod
    def _parse_viscosity(name: str) -> Optional[str]:
        if not name:
            return None
        m = re.search(r'(\d+W-?\d+)', name)
        return m.group(1).replace('W-', 'W-') if m else None

    @staticmethod
    def _extract_brand(name: str) -> Optional[str]:
        if not name:
            return None
        for brand in ['G-Energy', 'Gazpromneft', 'G-Box', 'G-Truck', 'G-Force']:
            if name.startswith(brand):
                return brand
        return None

    # ─── Detection ─────────────────────────────────────────────

    def detect(self, file_path: str) -> bool:
        try:
            df = pd.read_excel(file_path, sheet_name=0, header=None, nrows=5)
            row1 = df.iloc[1].astype(str).str.strip().tolist()
            return any('Легковые автомобили' in v for v in row1 if v != 'nan')
        except Exception:
            return False

    # ─── Main parse ────────────────────────────────────────────

    def parse(self, file_path: str) -> list[VehicleRecord]:
        records: list[VehicleRecord] = []
        warnings: list[str] = []
        df = pd.read_excel(file_path, sheet_name=0, header=None)

        current_brand: Optional[str] = None
        current_generation: Optional[str] = None  # для BMW E46, Mercedes W168
        in_diesel_section = False
        current_market = 'EU'

        # Статистика для отчёта
        stats = {
            'total_rows': len(df),
            'skipped_empty': 0,
            'skipped_no_brand': 0,
            'skipped_no_recs': 0,
            'footnotes_applied': 0,
            'diesel_sections': 0,
            'generation_headers': 0,
            'brands_seen': [],
        }

        for i in range(3, len(df)):
            row = df.iloc[i]
            col0 = self._clean(row.iloc[0])

            if not col0:
                stats['skipped_empty'] += 1
                continue

            # Diesel-секция
            if col0 == 'Diesel':
                in_diesel_section = True
                stats['diesel_sections'] += 1
                continue

            # Сброс Diesel при смене бренда
            if col0.upper().strip() in self.KNOWN_BRANDS:
                in_diesel_section = False
                current_brand = self._normalize_brand(col0)
                current_generation = None  # сброс поколения
                if '(RUS)' in col0:
                    current_market = 'RU'
                elif '(USA)' in col0:
                    current_market = 'US'
                else:
                    current_market = 'EU'
                if current_brand not in stats['brands_seen']:
                    stats['brands_seen'].append(current_brand)
                continue

            # Подзаголовок поколения BMW: "E46 - 3 Series"
            if re.match(r'^[A-Z]\d+\s*-\s*\w+', col0) and len(col0) < 60:
                current_generation = col0
                stats['generation_headers'] += 1
                continue

            # Mercedes-Benz: "A-Class (W168)" / "B-Class (W245)"
            if re.match(r'^[A-Z]+-Class\s*\([A-Z]\d+\)', col0):
                current_generation = col0
                stats['generation_headers'] += 1
                continue

            # Сноска (начинается с 1-2 букв + 2+ пробела)
            if re.match(r'^[a-z]{1,2}\s{2,}', col0):
                if records:
                    self._apply_footnote(records[-1], col0)
                    stats['footnotes_applied'] += 1
                continue

            # Если текущий бренд не задан — пропускаем
            if not current_brand:
                stats['skipped_no_brand'] += 1
                continue

            # Это строка модели
            model_name = col0
            if current_generation:
                model_name = f"{current_generation} {model_name}"

            year_str = self._clean(row.iloc[1]) or ''
            year_start, year_end = self._parse_year_range(year_str)

            # col 2 — это объём масла двигателя (например "3,5/4,5" = без/с фильтром),
            # а НЕ объём самого двигателя. Объём двигателя парсим из названия модели.
            engine_oil_volume_raw = self._clean(row.iloc[2])
            engine_displacement = self._parse_engine_displacement_from_model(model_name)

            rec = VehicleRecord(
                vehicle_type='passenger_car',
                brand=current_brand,
                model=model_name,
                generation=current_generation,
                sub_model='Diesel' if in_diesel_section else None,
                year_start=year_start,
                year_end=year_end,
                market=current_market,
                attributes={
                    'displacement_liters': engine_displacement,
                    'fuel_type': 'diesel' if in_diesel_section else 'petrol',
                    'engine_oil_volume_raw': engine_oil_volume_raw,  # "3,5/4,5" — сохраняем как есть
                },
                source='pvl',
                row_number=i,
            )

            # Парсим все 8 узлов
            for node_code, cols in self.NODE_COLUMNS.items():
                main_fluid = self._clean(row.iloc[cols['main']]) if cols['main'] is not None and cols['main'] < len(row) else None
                alt1_fluid = self._clean(row.iloc[cols['alt1']]) if cols['alt1'] is not None and cols['alt1'] < len(row) else None
                alt2_fluid = self._clean(row.iloc[cols['alt2']]) if cols['alt2'] is not None and cols['alt2'] < len(row) else None
                volume = self._normalize_volume(
                    self._clean(row.iloc[cols['volume']]) if cols['volume'] is not None and cols['volume'] < len(row) else None
                )
                marker = self._clean(row.iloc[cols['marker']]) if cols['marker'] is not None and cols['marker'] < len(row) else None

                if main_fluid or alt1_fluid or alt2_fluid:
                    conditions = {}
                    if marker and marker not in (' ', '·'):
                        conditions['marker_code'] = marker
                    if in_diesel_section:
                        conditions['fuel_type'] = 'diesel'

                    # Основное масло
                    if main_fluid and main_fluid not in ('-', '<', '< '):
                        rec.recommendations.append(FluidRecommendation(
                            node_code=node_code,
                            fluid_name=main_fluid,
                            fluid_brand=self._extract_brand(main_fluid),
                            viscosity_sae=self._parse_viscosity(main_fluid),
                            recommendation_rank=1,
                            is_oem=True,
                            volume_liters=volume,
                            applicability_conditions=conditions.copy(),
                        ))
                    # Альтернатива 1
                    if alt1_fluid and alt1_fluid not in ('-',) and alt1_fluid != main_fluid:
                        rec.recommendations.append(FluidRecommendation(
                            node_code=node_code,
                            fluid_name=alt1_fluid,
                            fluid_brand=self._extract_brand(alt1_fluid),
                            viscosity_sae=self._parse_viscosity(alt1_fluid),
                            recommendation_rank=2,
                            is_oem=False,
                            volume_liters=volume,
                            applicability_conditions=conditions.copy(),
                        ))
                    # Альтернатива 2
                    if alt2_fluid and alt2_fluid not in ('-',) and alt2_fluid != main_fluid and alt2_fluid != alt1_fluid:
                        rec.recommendations.append(FluidRecommendation(
                            node_code=node_code,
                            fluid_name=alt2_fluid,
                            fluid_brand=self._extract_brand(alt2_fluid),
                            viscosity_sae=self._parse_viscosity(alt2_fluid),
                            recommendation_rank=3,
                            is_oem=False,
                            volume_liters=volume,
                            applicability_conditions=conditions.copy(),
                        ))

            if rec.recommendations:
                records.append(rec)
            else:
                stats['skipped_no_recs'] += 1

        self._stats = stats
        self._warnings = warnings
        return records

    def _apply_footnote(self, record: VehicleRecord, footnote: str) -> None:
        """Применяет сноску типа 'a  Раздаточная коробка: 0,36-0,38 л G-Box GL-5 75W-90;...'"""
        m = re.match(r'^([a-z]{1,2})\s{2,}(.+)$', footnote)
        if not m:
            return
        marker, body = m.groups()

        # Определяем узел
        node_label_map = [
            (r'раздаточн', 'TRANSFER_CASE'),
            (r'передний\s+дифференциал', 'DIFFERENTIAL'),
            (r'задний\s+дифференциал', 'DIFFERENTIAL'),
            (r'самоблок', 'DIFFERENTIAL'),
            (r'передний\s+и\s+задний', 'DIFFERENTIAL'),
            (r'дифференциал', 'DIFFERENTIAL'),
            (r'вариатор', 'CVT'),
            (r'автоматическ', 'AUTO_TRANSMISSION'),
            (r'коробк[ау]\s+передач', 'MANUAL_TRANSMISSION'),
            (r'сцепление\s+haldex', 'TRANSFER_CASE'),
            (r'pto', 'PTO'),
            (r'гидравлическ', 'STEERING'),
        ]
        node_code = None
        for pattern, code in node_label_map:
            if re.search(pattern, body.lower()):
                node_code = code
                break
        if not node_code:
            return

        # Объём
        vol_match = re.search(r'([\d,\-\s]+)\s*л', body)
        volume = self._normalize_volume(vol_match.group(1)) if vol_match else None

        # Масла (после двоеточия, разделены ';')
        oil_part = body.split(':', 1)[-1] if ':' in body else body
        oils = [o.strip() for o in oil_part.split(';') if o.strip() and o.strip() != '-']
        if not oils:
            return

        existing_ranks = {r.recommendation_rank for r in record.recommendations
                          if r.node_code == node_code}
        next_rank = max(existing_ranks) + 1 if existing_ranks else 1

        for oil_name in oils:
            record.recommendations.append(FluidRecommendation(
                node_code=node_code,
                fluid_name=oil_name,
                fluid_brand=self._extract_brand(oil_name),
                viscosity_sae=self._parse_viscosity(oil_name),
                recommendation_rank=next_rank,
                is_oem=False,
                volume_liters=volume,
                applicability_conditions={'footnote_marker': marker, 'source': 'pvl_footnote'},
            ))
            next_rank += 1

    @property
    def stats(self) -> dict:
        return getattr(self, '_stats', {})


# ============================================================================
# 3. REPORT — детальная статистика для проверки качества
# ============================================================================

def print_report(records: list[VehicleRecord], parser_stats: dict):
    print("\n" + "=" * 70)
    print("📊 ОТЧЁТ ПО ПАРСИНГУ PVL-КАТАЛОГА")
    print("=" * 70)

    print(f"\nСтатистика строк:")
    print(f"  Всего строк в файле:        {parser_stats.get('total_rows', 0)}")
    print(f"  Пустых (пропущено):         {parser_stats.get('skipped_empty', 0)}")
    print(f"  Без бренда (пропущено):     {parser_stats.get('skipped_no_brand', 0)}")
    print(f"  Без рекомендаций (пропущено): {parser_stats.get('skipped_no_recs', 0)}")
    print(f"  Diesel-секций:              {parser_stats.get('diesel_sections', 0)}")
    print(f"  Заголовков поколений:       {parser_stats.get('generation_headers', 0)}")
    print(f"  Сносок применено:           {parser_stats.get('footnotes_applied', 0)}")

    print(f"\n✅ Успешно распарсено: {len(records)} транспортных средств")

    # По брендам
    by_brand = Counter(r.brand for r in records)
    print(f"\n🏷️  Брендов найдено: {len(by_brand)}")
    print(f"   Топ-10 по количеству:")
    for brand, count in by_brand.most_common(10):
        print(f"   {brand:25s} {count:4d} авто")
    print(f"   ...и ещё {len(by_brand) - 10} брендов" if len(by_brand) > 10 else "")

    # По рынкам
    by_market = Counter(r.market for r in records)
    print(f"\n🌍 По рынкам:")
    for market, count in by_market.most_common():
        print(f"   {market or 'не указан':15s} {count:4d} авто")

    # По типу топлива (sub_model = Diesel)
    diesel_count = sum(1 for r in records if r.sub_model == 'Diesel')
    print(f"\n⛽ Diesel-модификаций: {diesel_count} ({100*diesel_count/len(records):.1f}%)")

    # По годам
    years_with_data = [r.year_start for r in records if r.year_start]
    if years_with_data:
        print(f"\n📅 Диапазон лет: {min(years_with_data)} - {max(years_with_data)}")
        decades = Counter(y // 10 * 10 for y in years_with_data)
        print(f"   По десятилетиям:")
        for decade in sorted(decades):
            print(f"   {decade}-{decade+9}: {decades[decade]:4d} авто")

    # По узлам
    by_node = Counter()
    for r in records:
        for rec in r.recommendations:
            by_node[rec.node_code] += 1
    print(f"\n🔧 Рекомендаций по узлам:")
    for node, count in by_node.most_common():
        print(f"   {node:25s} {count:5d}")

    # По рангам
    by_rank = Counter()
    for r in records:
        for rec in r.recommendations:
            by_rank[rec.recommendation_rank] += 1
    print(f"\n🎖️  По рангам рекомендаций:")
    rank_labels = {1: 'primary (основное)', 2: 'alt1 (первая альтернатива)', 3: 'alt2 (вторая альтернатива)', 4: 'footnote', 5: 'footnote'}
    for rank, count in sorted(by_rank.items()):
        print(f"   Rank {rank} ({rank_labels.get(rank, 'доп.')}): {count:5d}")

    # Уникальные масла
    unique_fluids = set()
    for r in records:
        for rec in r.recommendations:
            unique_fluids.add(rec.fluid_name)
    print(f"\n🛢️  Уникальных масел/жидкостей: {len(unique_fluids)}")
    print(f"   Топ-10 самых частых:")
    fluid_counter = Counter()
    for r in records:
        for rec in r.recommendations:
            fluid_counter[rec.fluid_name] += 1
    for name, count in fluid_counter.most_common(10):
        print(f"   {name[:50]:50s} {count:5d}")

    # Проблемы
    print(f"\n⚠️  Потенциальные проблемы:")
    no_year = sum(1 for r in records if not r.year_start)
    no_displacement = sum(1 for r in records if not r.attributes.get('displacement_liters'))
    only_one_rec = sum(1 for r in records if len(r.recommendations) == 1)
    print(f"   Без года:                  {no_year} ({100*no_year/len(records):.1f}%)")
    print(f"   Без объёма двигателя:      {no_displacement} ({100*no_displacement/len(records):.1f}%)")
    print(f"   С только одной рекомендацией: {only_one_rec} ({100*only_one_rec/len(records):.1f}%)")

    # Примеры
    print(f"\n📋 Примеры первых 5 записей:")
    for r in records[:5]:
        print(f"\n  [{r.row_number}] {r.brand} {r.model} ({r.year_start or '?'}-{r.year_end or '?'})")
        print(f"      Market: {r.market}, Sub: {r.sub_model or '-'}, Displacement: {r.attributes.get('displacement_liters')}")
        print(f"      Hash: {r.source_hash()}")
        print(f"      Рекомендаций: {len(r.recommendations)}")
        for rec in r.recommendations[:3]:
            cond = f" {rec.applicability_conditions}" if rec.applicability_conditions else ""
            print(f"        [{rec.node_code:20s}] rank={rec.recommendation_rank} {rec.fluid_name[:40]:40s} vol={rec.volume_liters or '-'}{cond}")

    print("\n" + "=" * 70)


# ============================================================================
# 4. DB IMPORTER — заливка в PostgreSQL
# ============================================================================

async def import_to_db(records: list[VehicleRecord], db_url: str, tenant_id: str = "00000000-0000-0000-0000-000000000000"):
    """Заливает распарсенные записи в БД."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text

    engine = create_async_engine(db_url, echo=False)
    stats = {
        'inserted_vehicles': 0,
        'skipped_duplicates': 0,
        'inserted_recommendations': 0,
        'errors': [],
    }

    async with AsyncSession(engine) as db:
        for i, record in enumerate(records, 1):
            try:
                source_hash = record.source_hash()

                # Проверяем дубль
                existing = await db.execute(
                    text("""
                        SELECT id FROM vehicles
                        WHERE tenant_id = :tid AND source_hash = :h
                    """),
                    {"tid": tenant_id, "h": source_hash}
                )
                if existing.first():
                    stats['skipped_duplicates'] += 1
                    continue

                # Вставляем ТС
                result = await db.execute(
                    text("""
                        INSERT INTO vehicles
                            (tenant_id, vehicle_type, brand, model, generation,
                             sub_model, year_start, year_end, market, attributes,
                             external_codes, source, source_hash)
                        VALUES
                            (:tid, :vtype, :brand, :model, :gen,
                             :sub, :ys, :ye, :market, :attrs::jsonb,
                             :ext::jsonb, :source, :hash)
                        RETURNING id
                    """),
                    {
                        "tid": tenant_id,
                        "vtype": record.vehicle_type,
                        "brand": record.brand,
                        "model": record.model,
                        "gen": record.generation,
                        "sub": record.sub_model,
                        "ys": record.year_start,
                        "ye": record.year_end,
                        "market": record.market,
                        "attrs": json.dumps(record.attributes),
                        "ext": json.dumps(record.external_codes),
                        "source": record.source,
                        "hash": source_hash,
                    }
                )
                vehicle_id = str(result.scalar())

                # Вставляем рекомендации
                for rec in record.recommendations:
                    # Ищем fluid
                    fluid_result = await db.execute(
                        text("SELECT id FROM fluids WHERE canonical_name ILIKE :name LIMIT 1"),
                        {"name": f"%{rec.fluid_name[:50]}%"}
                    )
                    fluid_row = fluid_result.first()
                    fluid_id = str(fluid_row.id) if fluid_row else None

                    await db.execute(
                        text("""
                            INSERT INTO vehicle_recommendations
                                (tenant_id, vehicle_id, node_code, fluid_id,
                                 fluid_name_override, recommendation_rank,
                                 is_oem_recommendation, volume_liters,
                                 applicability_conditions, notes, source)
                            VALUES
                                (:tid, :vid, :node, :fid, :foverride, :rank,
                                 :oem, :vol, :cond::jsonb, :notes, :source)
                            ON CONFLICT (vehicle_id, node_code, fluid_id, recommendation_rank)
                                DO NOTHING
                        """),
                        {
                            "tid": tenant_id,
                            "vid": vehicle_id,
                            "node": rec.node_code,
                            "fid": fluid_id,
                            "foverride": rec.fluid_name if not fluid_id else None,
                            "rank": rec.recommendation_rank,
                            "oem": rec.is_oem,
                            "vol": rec.volume_liters,
                            "cond": json.dumps(rec.applicability_conditions),
                            "notes": rec.notes,
                            "source": "pvl",
                        }
                    )
                    stats['inserted_recommendations'] += 1

                stats['inserted_vehicles'] += 1

                # Прогресс каждые 500
                if i % 500 == 0:
                    await db.commit()
                    logger.info(f"  Progress: {i}/{len(records)} (inserted {stats['inserted_vehicles']})")

            except Exception as e:
                stats['errors'].append({
                    'row': record.row_number,
                    'vehicle': f"{record.brand} {record.model}",
                    'error': str(e),
                })

        await db.commit()

    await engine.dispose()
    return stats


# ============================================================================
# 5. MAIN
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description='GSM PVL Catalog Importer')
    parser.add_argument('--file', default='/home/z/my-project/upload/Каталог подбора PVL.xlsx',
                        help='Path to PVL Excel file')
    parser.add_argument('--dry-run', action='store_true',
                        help='Parse only, do not write to DB')
    parser.add_argument('--db-url', default=None,
                        help='Database URL (e.g. postgresql+asyncpg://gsm:gsm@localhost:5432/gsm)')
    parser.add_argument('--tenant-id', default='00000000-0000-0000-0000-000000000000',
                        help='Tenant UUID (default: global seed)')
    args = parser.parse_args()

    file_path = args.file
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    logger.info(f"📂 Loading: {file_path}")
    start = time.monotonic()

    # 1. Detect
    p = PVLParser()
    if not p.detect(file_path):
        logger.error("❌ File not detected as PVL catalog")
        sys.exit(1)
    logger.info("✅ PVL format detected")

    # 2. Parse
    records = p.parse(file_path)
    parse_time = time.monotonic() - start
    logger.info(f"⚡ Parsed {len(records)} vehicles in {parse_time:.1f}s")

    # 3. Print report
    print_report(records, p.stats)

    # 4. DB import (если не dry-run)
    if args.dry_run:
        logger.info("🛑 Dry-run mode: skip DB import")
        return

    if not args.db_url:
        logger.warning("⚠️  No --db-url provided, skipping DB import")
        return

    logger.info(f"💾 Importing to DB: {args.db_url}")
    db_start = time.monotonic()
    stats = await import_to_db(records, args.db_url, args.tenant_id)
    db_time = time.monotonic() - db_start

    print("\n" + "=" * 70)
    print("💾 ИМПОРТ В БД ЗАВЕРШЁН")
    print("=" * 70)
    print(f"  Inserted vehicles:        {stats['inserted_vehicles']}")
    print(f"  Skipped duplicates:       {stats['skipped_duplicates']}")
    print(f"  Inserted recommendations: {stats['inserted_recommendations']}")
    print(f"  Errors:                   {len(stats['errors'])}")
    print(f"  Time:                     {db_time:.1f}s")

    if stats['errors']:
        print(f"\n⚠️  Первые 5 ошибок:")
        for e in stats['errors'][:5]:
            print(f"  Row {e['row']}: {e['vehicle']} — {e['error']}")

    print("\n" + "=" * 70)
    print("✅ Готово! Теперь можно проверить:")
    print("  psql -d gsm -c \"SELECT source, COUNT(*) FROM vehicles GROUP BY source;\"")
    print("  psql -d gsm -c \"SELECT COUNT(*) FROM vehicle_recommendations;\"")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(main())
