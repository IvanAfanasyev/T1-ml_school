import re
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import pdfplumber
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import t1_cloud_config


# =========================
# Настройки
# =========================

_cfg = t1_cloud_config()
OUT_DIR = _cfg.RAW_DIR
PDF_PATH = OUT_DIR / "t1_current_tariff.pdf"
OUT_JSON = OUT_DIR / "t1_tariff_items_raw.json"
OUT_XLSX = OUT_DIR / "t1_tariff_items_raw.xlsx"
OUT_META = OUT_DIR / "t1_tariff_parser_meta.json"

PROVIDER_ID = _cfg.PROVIDER_ID


# =========================
# Базовые функции очистки
# =========================

def clean_text(value) -> str:
    """
    Базовая очистка текста из PDF.
    Важно: функция НЕ удаляет сноски 1/2 из названий,
    потому что можно случайно сломать vCPU a1, b2, T1 Cloud, H1, S3 и т.д.
    """
    if value is None:
        return ""

    value = str(value)
    value = value.replace("\n", " ")
    value = value.replace("\r", " ")
    value = value.replace("\u00a0", " ")
    value = value.replace("\ufffe", "-")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_price(value):
    """
    Преобразует цену из строки PDF в float.
    Пустые значения и '-' возвращает как None.
    """
    value = clean_text(value)

    if not value or value == "-":
        return None

    value = value.replace(" ", "").replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None


def is_number_cell(value) -> bool:
    """
    Проверяет, является ли первая ячейка номером позиции: 1, 1., 23.
    """
    value = clean_text(value)
    return bool(re.match(r"^\d+\.?$", value))


def safe_row(row, min_len=5):
    """
    Дополняет строку пустыми ячейками, чтобы не падать на коротких таблицах.
    """
    row = list(row or [])
    row = row + [""] * (min_len - len(row))
    return row


# =========================
# Заголовки групп
# =========================

GROUP_PATTERNS = [
    r"\d+\.\s*Группа услуг[^\n]+",
    r"\d+\.\s*Услуга[^\n]+",
    r"\d+\.\s*Программные услуги[^\n]+",
    r"\d+\.\s*Сетевые услуги",
]


def normalize_group_heading(group: str) -> str:
    group = clean_text(group)
    group = re.sub(r"\s+", " ", group)
    return group.strip()


def extract_all_groups_from_text(text: str) -> list[str]:
    """
    Достаёт все заголовки групп/услуг со страницы.

    Важно:
    raw_group_name — это только подсказка.
    На одной странице PDF может быть конец старой таблицы и начало новой.
    Финальный service_id должен определять нормализатор по raw_tariff_name.
    """
    if not text:
        return []

    groups = []

    for pattern in GROUP_PATTERNS:
        groups.extend(re.findall(pattern, text))

    cleaned = []
    seen = set()

    for group in groups:
        group = normalize_group_heading(group)
        if group and group not in seen:
            cleaned.append(group)
            seen.add(group)

    return cleaned


# =========================
# Тип таблицы
# =========================

def detect_table_type(table) -> str:
    """
    Определяет тип таблицы по заголовкам.

    minute_and_month:
        Есть цена за минуту и цена за месяц.

    month_only:
        Есть только цена за месяц.

    unknown:
        Заголовок не удалось понять.
    """
    if not table:
        return "unknown"

    header_rows = table[:4]
    header_text = " ".join(
        clean_text(cell).lower()
        for row in header_rows
        for cell in (row or [])
        if cell
    )

    has_minute = "минут" in header_text
    has_month = "месяц" in header_text or "месяч" in header_text

    if has_minute and has_month:
        return "minute_and_month"

    if has_month and not has_minute:
        return "month_only"

    return "unknown"


def infer_table_type_from_row_shape(row, table_type: str) -> str:
    """
    Уточняет тип таблицы, если заголовок не распознан.
    """
    if table_type != "unknown":
        return table_type

    non_empty = [clean_text(x) for x in row if clean_text(x)]

    if len(non_empty) == 4:
        return "month_only"

    if len(non_empty) >= 5:
        return "minute_and_month"

    return "unknown"


# =========================
# Сноски
# =========================

def detect_footnotes(name: str) -> dict:
    """
    Определяет возможные сноски 1/2.

    Это только подсказка. Мы НЕ удаляем эти цифры из raw_tariff_name.
    Финально чистить название должен нормализатор.

    Ограничение:
    Регулярки могут давать false positive для vCPU a1, b2, T1 и т.д.,
    поэтому has_footnote_* нельзя использовать как единственный источник истины.
    """
    raw = clean_text(name)

    return {
        "has_footnote_1": bool(re.search(r"(?<=[А-Яа-яA-Za-z\)])1(?=\s|$)", raw)),
        "has_footnote_2": bool(re.search(r"(?<=[А-Яа-яA-Za-z\)])2(?=\s|$)", raw)),
    }


# =========================
# Billing hints
# =========================

def detect_billing_hint(table_type: str, price_minute, price_month, footnotes: dict) -> str:
    """
    Даёт подсказку по типу тарификации.
    Это не финальная нормализация.
    """
    if table_type == "month_only":
        return "per_month"

    # Более надёжно смотреть на наличие цены в колонках.
    if price_minute is not None and price_month is not None:
        return "per_minute_with_month_reference"

    if price_minute is not None and price_month is None:
        return "per_minute"

    if price_minute is None and price_month is not None:
        if footnotes.get("has_footnote_2"):
            return "per_calendar_month"
        return "per_month"

    return "unknown"


# =========================
# Метаданные PDF
# =========================

def extract_pdf_version_from_first_page(pdf) -> dict:
    """
    Достаёт версию и дату вступления в силу из первой страницы.
    """
    result = {
        "pdf_version_text": "",
        "pdf_effective_text": "",
    }

    if not pdf.pages:
        return result

    text = pdf.pages[0].extract_text() or ""
    text = clean_text(text)

    version_match = re.search(r"Версия от\s+([^,]+)", text)
    effective_match = re.search(r"вступает в силу с\s+([^\.]+)", text)

    if version_match:
        result["pdf_version_text"] = clean_text(version_match.group(0))

    if effective_match:
        result["pdf_effective_text"] = clean_text(effective_match.group(0))

    return result


# =========================
# Извлечение строк
# =========================

def parse_table_row(row, table_type: str):
    """
    Преобразует одну строку таблицы в raw item.

    В v3 нет tariff_name_cleaned.
    Главный текст услуги — raw_tariff_name.
    """
    row = safe_row(row, min_len=5)

    raw_position = clean_text(row[0])
    raw_tariff_name = clean_text(row[1])
    unit = clean_text(row[2])

    table_type = infer_table_type_from_row_shape(row, table_type)

    if table_type == "month_only":
        price_per_minute = None
        price_per_month = parse_price(row[3])
    else:
        price_per_minute = parse_price(row[3])
        price_per_month = parse_price(row[4])

    footnotes = detect_footnotes(raw_tariff_name)

    return {
        "position_number": raw_position.replace(".", ""),
        "raw_tariff_name": raw_tariff_name,
        "unit": unit,
        "price_per_minute_rub_no_vat": price_per_minute,
        "price_per_month_rub_no_vat": price_per_month,
        "has_footnote_1": footnotes["has_footnote_1"],
        "has_footnote_2": footnotes["has_footnote_2"],
        "billing_hint": detect_billing_hint(
            table_type=table_type,
            price_minute=price_per_minute,
            price_month=price_per_month,
            footnotes=footnotes,
        ),
        "table_type": table_type,
        "raw_row": [clean_text(x) for x in row],
    }


def should_skip_row(row) -> bool:
    """
    Отсекает строки-заголовки и пустые строки.
    """
    if not row:
        return True

    first = clean_text(row[0])

    if not first:
        return True

    if not is_number_cell(first):
        return True

    return False


def parse_pdf(pdf_path: Path) -> tuple[list[dict], dict]:
    """
    Основной парсинг PDF.
    """
    items = []
    pages_info = []

    current_group_hint = ""

    with pdfplumber.open(str(pdf_path)) as pdf:
        pdf_meta = extract_pdf_version_from_first_page(pdf)

        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            page_groups = extract_all_groups_from_text(page_text)

            if page_groups:
                current_group_hint = page_groups[-1]

            tables = page.extract_tables() or []

            pages_info.append({
                "page": page_num,
                "groups_found": page_groups,
                "tables_found": len(tables),
            })

            for table_index, table in enumerate(tables, start=1):
                table_type = detect_table_type(table)

                for row_index, row in enumerate(table, start=1):
                    if should_skip_row(row):
                        continue

                    parsed = parse_table_row(row, table_type)

                    item = {
                        "provider_id": PROVIDER_ID,
                        "source_file": str(pdf_path),
                        "source_page": page_num,
                        "source_table_index": table_index,
                        "source_row_index": row_index,

                        # Только подсказка. Финальный service_id определяет нормализатор.
                        "raw_group_name": current_group_hint,
                        "raw_page_groups": page_groups,

                        **parsed,

                        "source_quality": {
                            "group_confidence": "low" if len(page_groups) > 1 else "medium",
                            "price_confidence": "high" if (
                                parsed["price_per_minute_rub_no_vat"] is not None
                                or parsed["price_per_month_rub_no_vat"] is not None
                            ) else "low",
                            "needs_llm_normalization": True,
                        },
                    }

                    items.append(item)

    meta = {
        "provider_id": PROVIDER_ID,
        "source_file": str(pdf_path),
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "total_items": len(items),
        "pages": pages_info,
        **pdf_meta,
        "notes": [
            "This is raw extraction, not final normalization.",
            "raw_group_name is only a hint and may be wrong on pages with multiple groups.",
            "tariff_name_cleaned was removed in v3 to avoid corrupting names like vCPU a1, b2, T1 Cloud, H1, S3.",
            "Use raw_tariff_name for LLM/code normalization.",
            "Prices are extracted from PDF tables and should not be changed by LLM.",
        ],
    }

    return items, meta


# =========================
# Сохранение
# =========================

def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def save_xlsx(items: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(items)

    preferred_columns = [
        "provider_id",
        "source_file",
        "source_page",
        "source_table_index",
        "source_row_index",
        "raw_group_name",
        "raw_page_groups",
        "position_number",
        "raw_tariff_name",
        "unit",
        "price_per_minute_rub_no_vat",
        "price_per_month_rub_no_vat",
        "table_type",
        "billing_hint",
        "has_footnote_1",
        "has_footnote_2",
        "source_quality",
        "raw_row",
    ]

    existing_columns = [col for col in preferred_columns if col in df.columns]
    other_columns = [col for col in df.columns if col not in existing_columns]
    df = df[existing_columns + other_columns]

    df.to_excel(path, index=False)


def main():
    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"Не найден PDF: {PDF_PATH}\n"
            f"Сначала запусти collector, чтобы скачать актуальный тарифный PDF."
        )

    items, meta = parse_pdf(PDF_PATH)

    save_json(items, OUT_JSON)
    save_json(meta, OUT_META)
    save_xlsx(items, OUT_XLSX)

    month_only_count = sum(1 for item in items if item["table_type"] == "month_only")
    minute_month_count = sum(1 for item in items if item["table_type"] == "minute_and_month")
    unknown_count = sum(1 for item in items if item["table_type"] == "unknown")

    low_group_count = sum(
        1 for item in items
        if item.get("source_quality", {}).get("group_confidence") == "low"
    )

    print("Готово")
    print(f"PDF: {PDF_PATH}")
    print(f"Всего тарифных строк: {len(items)}")
    print(f"minute_and_month: {minute_month_count}")
    print(f"month_only: {month_only_count}")
    print(f"unknown: {unknown_count}")
    print(f"Строк с низкой уверенностью группы: {low_group_count}")
    print()
    print(f"JSON: {OUT_JSON}")
    print(f"Excel: {OUT_XLSX}")
    print(f"Meta: {OUT_META}")


if __name__ == "__main__":
    main()
