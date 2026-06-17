"""
Парсер сложных Excel-каталогов японских авто (Honda, Toyota, Nissan и т.д.).

Структура файла (katalog_gsm.xlsx):
- Row 0: верхний уровень заголовков (группы: идентификаторы + узлы)
- Row 1: нижний уровень заголовков (поля внутри узлов)
- Row 2+: данные

MultiIndex колонок:
  [0-4]   Идентификаторы: Модель, Годы, Объём, Кузов, Двигатель
  [5-10]  Узел "Масло для двигателя"     → ENGINE
  [11]    Идентификатор: Тип коробки передач
  [12-13] Узел "Масло для МКП"           → MANUAL_TRANSMISSION
  [14-15] Узел "Масло для АКП/вариатор"  → AUTO_TRANSMISSION / CVT
  [16-17] Узел "Масло для переключателя" → TRANSFER_CASE
  [18-19] Узел "Дифференциал передний"   → FRONT_DIFF
  [20-21] Узел "Дифференциал задний"     → REAR_DIFF

Каждая строка Excel порождает несколько RawExcelRow (по одному на узел).
"""

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================
# Схема строки (дубликат RawExcelRow для независимости)
# =============================================================

@dataclass
class RawExcelRow:
    """Сырая строка из Excel-файла до обработки и нормализации."""
    brand: Optional[str] = None
    model: Optional[str] = None
    years: Optional[str] = None
    body: Optional[str] = None
    engine: Optional[str] = None
    engine_volume: Optional[str] = None
    node_type: Optional[str] = None
    fluid_name: Optional[str] = None
    volume: Optional[str] = None
    volume_with_filter: Optional[str] = None
    viscosity: Optional[str] = None
    api_class: Optional[str] = None
    oem_spec: Optional[str] = None


# =============================================================
# Константы
# =============================================================

NODE_TYPE_MAP: Dict[str, str] = {
    "масло для двигателя": "ENGINE",
    "мкп": "MANUAL_TRANSMISSION",
    "акп": "AUTO_TRANSMISSION",
    "вариатор": "CVT",
    "переключател": "TRANSFER_CASE",
    "дифференциала (передний": "FRONT_DIFF",
    "дифференциала (задний": "REAR_DIFF",
}

IDENTIFIER_KEYWORDS = [
    "модель", "дата выпуска", "объем", "номер кузова",
    "тип двигателя", "тип коробки",
]

EMPTY_VALUES = {"-", "—", "t/m", "a/t", "н/д", "n/a", "", " ", "*"}

FIELD_MAP = {
    "объем масла": "volume",
    "объем масла с фильтром": "volume_with_filter",
    "класс масла sae": "viscosity",
    "класс масла api": "api_class",
    "моторное масло": "fluid_name",
    "объем": "volume",
    "масло": "fluid_name",
    "тип": "fluid_name",
}


# =============================================================
# Санитайзер
# =============================================================

def cleanse_value(value) -> Optional[str]:
    """Очищает значение ячейки:
    - NaN → None
    - "—", "-", "T/M", пусто → None
    - "10W-30(5W-30)" → "10W-30"
    - "SH(SJ/GF-2)" → "SH"
    - "4.2(4.5)" → "4.2"
    """
    if pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s.lower() in EMPTY_VALUES:
        return None

    # "10W-30(5W-30)" → "10W-30"
    m = re.match(r'^(\d+[Ww]-\d+)', s)
    if m and m.group(1) != s:
        return m.group(1)

    # "SH(SJ/GF-2)" → "SH"
    m = re.match(r'^([A-Z]{2,3}(?:-\d+)?)', s)
    if m and m.group(1) != s and '(' in s:
        return m.group(1)

    # "4.2(4.5)" → "4.2"
    m = re.match(r'^(\d+\.?\d*)', s)
    if m and m.group(1) != s and '(' in s:
        return m.group(1)

    # Схлопываем множественные пробелы
    s = re.sub(r' {2,}', ' ', s)

    # Удаляем дублирование текста (например "G-Box ATF  G-Box ATF" → "G-Box ATF")
    parts = s.split('  ')
    if len(parts) == 2 and parts[0].strip() == parts[1].strip():
        return parts[0].strip()

    return s


# =============================================================
# Детектор структуры колонок
# =============================================================

@dataclass
class ColumnGroup:
    upper_header: str
    col_indices: List[int] = field(default_factory=list)
    lower_headers: List[str] = field(default_factory=list)
    is_identifier: bool = False
    node_type: Optional[str] = None


def detect_column_groups(df: pd.DataFrame) -> List[ColumnGroup]:
    """Группирует колонки — идентификаторы и узлы."""
    upper = df.columns.get_level_values(0)
    lower = df.columns.get_level_values(1)

    groups: List[ColumnGroup] = []
    current: Optional[ColumnGroup] = None

    for i in range(len(upper)):
        u = str(upper[i]).strip()
        l = str(lower[i]).strip()

        if current is None or current.upper_header != u:
            current = ColumnGroup(upper_header=u)
            groups.append(current)
        current.col_indices.append(i)
        current.lower_headers.append(l)

    for g in groups:
        ul = g.upper_header.lower()
        if "unnamed" in ul or "моторное масло.1" in ul:
            continue
        if any(kw in ul for kw in IDENTIFIER_KEYWORDS):
            g.is_identifier = True
            continue
        for kw, nt in NODE_TYPE_MAP.items():
            if kw in ul:
                g.node_type = nt
                break
    return groups


def lower_to_field(lower_header: str) -> str:
    key = lower_header.lower().strip()
    if key in FIELD_MAP:
        return FIELD_MAP[key]
    if key.startswith("моторное масло"):
        return "_skip"
    return "_skip"


# =============================================================
# Основной парсер
# =============================================================

@dataclass
class ParseResult:
    rows: List[RawExcelRow] = field(default_factory=list)
    total_excel_rows: int = 0
    skipped_rows: int = 0
    errors: List[dict] = field(default_factory=list)


def parse_japanese_catalog(
    file_path: str,
    sheet_name: Optional[str] = None,
    max_rows: Optional[int] = None,
    brand_override: Optional[str] = None,
) -> ParseResult:
    """Парсит Excel-каталог. Возвращает ParseResult с RawExcelRow.

    Args:
        file_path: путь к .xlsx
        sheet_name: имя листа (по умолчанию первый)
        max_rows: ограничение строк (для отладки)
        brand_override: марка авто (по умолчанию из имени листа)
    """
    result = ParseResult()

    xls = pd.ExcelFile(file_path)
    if sheet_name is None:
        sheet_name = xls.sheet_names[0]
    if sheet_name not in xls.sheet_names:
        raise ValueError(f"Лист '{sheet_name}' не найден. Доступны: {xls.sheet_names}")

    brand = brand_override or sheet_name

    # Читаем с двухуровневыми заголовками
    df = pd.read_excel(file_path, header=[0, 1], sheet_name=sheet_name)
    result.total_excel_rows = len(df)

    # Forward-fill верхних заголовков
    filled_upper = pd.Series(df.columns.get_level_values(0)).ffill().values
    df.columns = pd.MultiIndex.from_arrays([
        filled_upper, df.columns.get_level_values(1)
    ])

    groups = detect_column_groups(df)

    # Собираем индексы идентификаторов и узлов
    id_indices: List[int] = []
    node_groups: List[ColumnGroup] = []
    for g in groups:
        if g.is_identifier:
            id_indices.extend(g.col_indices)
        elif g.node_type:
            node_groups.append(g)

    if not id_indices:
        logger.warning("Лист '%s' не содержит распознаваемых идентификаторов — пропущен", sheet_name)
        return result

    limit = min(max_rows, len(df)) if max_rows else len(df)

    for idx in range(limit):
        row = df.iloc[idx]
        v = row.values

        try:
            model = cleanse_value(v[0]) if len(v) > 0 else None
            years = cleanse_value(v[1]) if len(v) > 1 else None
            displacement = cleanse_value(v[2]) if len(v) > 2 else None
            body = cleanse_value(v[3]) if len(v) > 3 else None
            engine_code = cleanse_value(v[4]) if len(v) > 4 else None
            transmission = cleanse_value(v[11]) if len(v) > 11 else None

            if not model:
                result.skipped_rows += 1
                continue

            any_data = False
            for ng in node_groups:
                node_row = _build_node(v, ng, brand, model, years, displacement, body, engine_code, transmission)
                if node_row:
                    result.rows.append(node_row)
                    any_data = True

            if not any_data:
                result.skipped_rows += 1

        except Exception as exc:
            result.errors.append({
                "excel_row": idx + 2,
                "error": str(exc),
                "type": type(exc).__name__,
            })
            result.skipped_rows += 1
            logger.warning("Row %d skipped: %s", idx + 2, exc)

    return result


def _build_node(
    values,
    node_group: ColumnGroup,
    brand: str,
    model: str,
    years: Optional[str],
    displacement: Optional[str],
    body: Optional[str],
    engine_code: Optional[str],
    transmission: Optional[str],
) -> Optional[RawExcelRow]:
    """Собирает RawExcelRow для одного узла."""
    data: dict = {}
    has_data = False

    for ci, lh in zip(node_group.col_indices, node_group.lower_headers):
        if ci >= len(values):
            continue
        field_name = lower_to_field(lh)
        if field_name == "_skip":
            continue
        cleaned = cleanse_value(values[ci])
        if cleaned is not None:
            has_data = True
        data[field_name] = cleaned

    if not has_data:
        return None

    nt = node_group.node_type or "UNKNOWN"

    # "T/M" в объёме → узел неприменим
    vol = data.get("volume")
    if vol and vol.strip().upper() == "T/M":
        return None

    return RawExcelRow(
        brand=brand,
        model=model,
        years=years,
        body=body,
        engine=engine_code,
        engine_volume=displacement,
        node_type=nt,
        fluid_name=data.get("fluid_name"),
        volume=data.get("volume"),
        volume_with_filter=data.get("volume_with_filter"),
        viscosity=data.get("viscosity"),
        api_class=data.get("api_class"),
    )


def list_sheets(file_path: str) -> List[str]:
    """Список листов в Excel."""
    return pd.ExcelFile(file_path).sheet_names


# =============================================================
# Тестовый блок (dry-run)
# =============================================================

if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    path = sys.argv[1] if len(sys.argv) > 1 else "/home/g/gsm/katalog_gsm.xlsx"
    print(f"Файл: {path}")

    sheets = list_sheets(path)
    print(f"Листы ({len(sheets)}): {', '.join(sheets)}\n")

    sheet = sheets[0]
    print(f"Парсинг листа: {sheet} (макс 10 строк)...")

    result = parse_japanese_catalog(path, sheet_name=sheet, max_rows=10)

    print(f"\nСтатистика:")
    print(f"  Строк в Excel:     {result.total_excel_rows}")
    print(f"  RawExcelRow создано: {len(result.rows)}")
    print(f"  Строк пропущено:   {result.skipped_rows}")
    print(f"  Ошибок:             {len(result.errors)}")

    print(f"\n{'=' * 70}")
    print(f"Первые {len(result.rows)} распарсенных строк:")
    print(f"{'=' * 70}")

    for i, r in enumerate(result.rows, 1):
        print(f"\n--- Row #{i} ---")
        d = asdict(r)
        # Убираем None поля для читаемости
        compact = {k: v for k, v in d.items() if v is not None}
        print(json.dumps(compact, ensure_ascii=False, indent=2))

    if result.errors:
        print(f"\n⚠️  Ошибки ({len(result.errors)}):")
        for e in result.errors[:5]:
            print(f"  Excel строка {e['excel_row']}: {e['type']} — {e['error']}")
