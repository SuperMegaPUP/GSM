# Импорт PVL-каталога в GSM — практическое руководство

> **Цель:** Загрузить «Каталог подбора PVL.xlsx» (Газпромнефть, 36 брендов, 2929 авто, 21 762 рекомендации) в существующую БД GSM.

## 📊 Что внутри PVL-файла

| Параметр | Значение |
|---|---|
| Строк | 3 667 (после очистки: **2 929 авто**) |
| Колонок | 31 |
| Брендов | **36** (BMW 202, Fiat 189, Toyota 189, Mercedes 177, Nissan 164, Audi 152, Citroën 152, Peugeot 136, Opel 129, ...) |
| Рынков | 3 (EU 2753, US 139, RU 37) |
| Diesel-модификаций | 1305 (44.6%) |
| Период выпуска | **1971 - 2013** |
| Узлов | 8 (Двигатель, МКПП, АКПП, Дифференциал, Охлаждение, Тормоза, ГУР, Подвеска) |
| Рекомендаций | **21 762** (11 604 primary + 6 903 alt1 + 1 395 alt2 + 860 сносок) |
| Уникальных масел | 247 |
| Сносок (footnotes) | 455 (merged rows с детальными спецификациями) |

## 🔑 Ключевые отличия от JDM-каталога

| Параметр | JDM | PVL |
|---|---|---|
| Брендов | 8 | 36 |
| Записей | 3 125 | 2 929 |
| Рекомендаций | 5 805 | 21 762 |
| Масел на узел | 1 (только основное) | **3** (основное + 2 альтернативы) |
| Дизельные секции | Нет | 38 (отдельные подмодели "Diesel") |
| Сноски | Нет | 455 (детальные спецификации по комплектации) |
| Маркеры комплектации | Нет | Есть (u, a, c, d, ...) |
| Года | `02.10-03.12` (мм.гг) | `'10-` или `'00-'05` (гг) |
| Поколения | Не выделены | 73 заголовка (E46, W168, и т.д.) |

## 🏗️ Структура 31 колонки PVL

```
col 0:    Модель                    "A1 1.2 TFSI"
col 1:    Год выпуска               "'10-" или "'00-'05"
col 2:    Объём масла двигателя     "3,5/4,5" (без/с фильтром)
───────── ДВИГАТЕЛЬ (cols 3-7) ─────────
col 3:    Основное масло            "G-Energy F Synth 5W-40"
col 4:    Альтернатива 1            "Gazpromneft Premium N 5W-40"
col 5:    Альтернатива 2            "G-Energy F Synth 5W-30"
col 6:    Маркер комплектации       "u" / "a" / "c" / "d" ...
col 7:    Объём масла               "2,1" (с фильтром)
───────── МКПП (cols 8-10) ─────────
col 8:    Основное + col 9: Альт1 + col 10: Маркер
───────── АКПП (cols 11-14) ─────────
col 11: Основное + col 12: Альт1 + col 13: Маркер + col 14: Объём
───────── ДИФФЕРЕНЦИАЛ (cols 15-18) ─────────
col 15: Основное + col 16: Альт1 + col 17: Маркер + col 18: Объём
───────── ОХЛАЖДЕНИЕ (cols 19-21) ─────────
col 19: Основное + col 20: Альт1 + col 21: Объём
───────── ТОРМОЗА (cols 22-24) ─────────
col 22: Основное + col 23: Альт1 + col 24: Объём
───────── ГУР (cols 25-27) ─────────
col 25: Основное + col 26: Альт1 + col 27: Объём
───────── ПОДВЕСКА (cols 28-30) ─────────
col 28: Основное + col 29: Альт1 + col 30: Объём
```

## 🚀 Как запустить импорт

### Вариант 1: Standalone скрипт (быстро, без правки кода проекта)

```bash
# 1. Примени миграцию (создаст таблицы vehicles + vehicle_recommendations)
psql -d gsm -f /home/g/gsm/vehicle-architecture/migration_vehicles_v2.sql

# 2. Установи зависимости
pip install openpyxl pandas psycopg2-binary sqlalchemy-asyncio asyncpg

# 3. Сначала dry-run (без записи в БД — посмотри отчёт)
python /home/g/gsm/vehicle-architecture/import_pvl.py --dry-run

# 4. Если отчёт нравится — запускай с заливкой в БД
python /home/g/gsm/vehicle-architecture/import_pvl.py \
  --db-url "postgresql+asyncpg://gsm:gsm@localhost:5432/gsm" \
  --tenant-id "00000000-0000-0000-0000-000000000000"
```

### Вариант 2: Через API (после интеграции в проект)

```bash
# После шагов из PROMPT_FOR_LOCAL_LLM.md
curl -X POST http://localhost:8000/api/v2/vehicles/import \
  -H "Authorization: Bearer $JWT" \
  -F "file=@Каталог подбора PVL.xlsx"
```

## ✅ Что делает скрипт (детально)

1. **Автоопределение формата** — проверяет row 1 на наличие "Легковые автомобили"
2. **Парсинг построчно** — пропускает пустые строки, бренды, заголовки поколений, Diesel-секции, сноски
3. **Для каждой строки модели:**
   - Извлекает brand, model, generation, year_start/end, market
   - Извлекает объём двигателя **из названия модели** (например "A1 1.2 TFSI" → 1.2)
   - Парсит 8 узлов, для каждого до 3 масел (rank 1/2/3)
   - Сохраняет маркеры комплектации в `applicability_conditions`
   - Сохраняет объёмы (включая "<" и диапазоны "0.8-1.2")
4. **Сноски** (например "a  Раздаточная коробка: 0,36-0,38 л G-Box GL-5 75W-90"):
   - Парсятся отдельно, применяются к **последней** записи
   - Добавляются как rank 4+ (альтернативные рекомендации)
5. **Дедупликация** — `source_hash` от `brand|model|generation|sub_model|year_start|year_end`
6. **Заливка в БД** — батчами по 500 записей с commit

## 🎯 Что попадёт в БД (пример)

Для **Audi A1 1.2 TFSI (2010-)**:

```json
// vehicles
{
  "vehicle_type": "passenger_car",
  "brand": "Audi",
  "model": "A1 1.2 TFSI",
  "year_start": 2010,
  "year_end": null,
  "market": "EU",
  "attributes": {
    "displacement_liters": 1.2,    // из названия модели
    "fuel_type": "petrol",
    "engine_oil_volume_raw": null  // col 2 был "-"
  },
  "source": "pvl",
  "source_hash": "9c073f5d5d0ccb1c"
}

// vehicle_recommendations (3 штуки)
[
  {
    "node_code": "ENGINE",
    "fluid_name_override": "G-Energy F Synth 5W-40",
    "recommendation_rank": 1,
    "is_oem_recommendation": true,
    "volume_liters": "2.1",
    "applicability_conditions": {"marker_code": "u"}
  },
  {
    "node_code": "ENGINE",
    "fluid_name_override": "Gazpromneft Premium N 5W-40",
    "recommendation_rank": 2,
    "is_oem_recommendation": false,
    "volume_liters": "2.1",
    "applicability_conditions": {"marker_code": "u"}
  },
  {
    "node_code": "ENGINE",
    "fluid_name_override": "G-Energy F Synth 5W-30",
    "recommendation_rank": 3,
    "is_oem_recommendation": false,
    "volume_liters": "2.1",
    "applicability_conditions": {"marker_code": "u"}
  }
]
```

## ⚠️ Нюансы и ограничения

### Что парсер обрабатывает правильно:
- ✅ Бренды с суффиксами (RUS), (USA) → отдельные рынки
- ✅ Diesel-секции внутри бренда → `sub_model: "Diesel"`, `fuel_type: "diesel"`
- ✅ Заголовки поколений BMW/Mercedes (E46, W168) → добавляются в `generation`
- ✅ Сноски (455 штук) → применяются к последней модели как rank 4+
- ✅ Маркеры комплектации (u, a, c, d, ...) → `applicability_conditions.marker_code`
- ✅ Года с апострофом: `'10-` → 2010+, `'00-'05` → 2000-2005, `'95-'99` → 1995-1999
- ✅ Объёмы с запятой и диапазоны: `2,1` → "2.1", `1-1,2` → "1-1.2", `<` → "<"
- ✅ Объём двигателя извлекается из названия модели ("A1 1.2 TFSI" → 1.2)

### Что НЕ парсится (намеренно):
- ❌ col 2 "Объём масла двигателя" — сохраняется как `engine_oil_volume_raw` в attributes, но не используется как основной объём. Для объёма масла используется col 7 (из секции "Двигатель").
- ❌ Сноски применяются к последней записи — иногда это может быть неточно (если сноска относится к конкретной модификации, а не ко всему модельному ряду). Это компромисс из-за структуры файла.

### Потенциальные проблемы:
- ⚠️ **21.8% записей без объёма двигателя** (638 авто) — для моделей типа "118d, 120d" объём не указан в названии. Это нормально, но поиск по объёму не сработает.
- ⚠️ **3.6% записей без года** (104 авто) — это модели, для которых в файле год указан нестандартно или отсутствует.
- ⚠️ **2-значные года > 30 → 19xx** — это эвристика. Если в файле будут годы типа '32, они станут 1932, что может быть неправильно. Но в текущем файле такой проблемы нет.

## 📋 Чек-лист после импорта

```bash
# 1. Проверить количество ТС по типам
psql -d gsm -c "SELECT vehicle_type, source, COUNT(*) FROM vehicles GROUP BY vehicle_type, source;"

# Ожидаемый результат:
# passenger_car | japan_catalog | 3125
# passenger_car | pvl           | 2929

# 2. Проверить количество рекомендаций
psql -d gsm -c "SELECT COUNT(*) FROM vehicle_recommendations;"
# Ожидаемый результат: ~27500 (5800 JDM + 21762 PVL)

# 3. Проверить бренды из PVL
psql -d gsm -c "SELECT brand, COUNT(*) FROM vehicles WHERE source='pvl' GROUP BY brand ORDER BY count DESC LIMIT 10;"

# 4. Проверить распределение по рангам
psql -d gsm -c "SELECT recommendation_rank, COUNT(*) FROM vehicle_recommendations GROUP BY recommendation_rank ORDER BY recommendation_rank;"
# Ожидаемый результат:
# 1 | 17409  (primary)
# 2 | 6903   (alt1)
# 3 | 1395   (alt2)
# 4+ | 860   (footnotes)

# 5. Проверить Diesel-модификации
psql -d gsm -c "SELECT COUNT(*) FROM vehicles WHERE sub_model='Diesel';"
# Ожидаемый результат: 1305

# 6. Тестовый поиск
psql -d gsm -c "SELECT * FROM search_vehicles('passenger_car'::vehicle_type, 'Audi', 'A1', 2011, NULL, 'EU', 10);"
```

## 🎨 Что увидит менеджер в UI

После интеграции (см. `preview.html`):

1. **Tabs**: Легковые (6049 авто) / Грузовые (скоро) / Спецтехника (скоро) / Мото (скоро) / Бензопилы (скоро)
2. **Форма подбора** для Audi A1 1.2 TFSI 2011:
   - Марка: Audi
   - Модель: A1 1.2 TFSI
   - Год: 2011
   - Объём двигателя: 1.2 (извлечён из названия)
3. **Результаты** в FluidCard с рангом:
   - 🟢 Rank 1 (★ Основное): G-Energy F Synth 5W-40, объём 2.1 L
   - 🔵 Rank 2 (Alt 1): Gazpromneft Premium N 5W-40, объём 2.1 L
   - ⚪ Rank 3 (Alt 2): G-Energy F Synth 5W-30, объём 2.1 L
4. **Applicability chip**: маркер "u" (если применимо)

## 🛣️ Следующие шаги

1. **Запусти standalone скрипт** — `import_pvl.py --dry-run` → посмотри отчёт → `import_pvl.py --db-url ...`
2. **Передай локальной модели** `PROMPT_FOR_LOCAL_LLM.md` для интеграции UI и API
3. **Протестируй поиск** через новый UI: Audi A1 1.2 TFSI 2011 → 3 варианта масла
4. **Когда дадут каталог тяжелой техники** — добавь `HeavyEquipmentParser` по аналогии с `PVLCatalogParser`
