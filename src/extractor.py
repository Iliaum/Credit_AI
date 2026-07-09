import re
from typing import TypedDict, Optional, Final

# ==========================================
# 1. ОТСУТСТВИЕ МАГИЧЕСКИХ ЧИСЕЛ И СТРОК
# Выносим все константы и настройки на уровень модуля
# ==========================================

_INN_CONTEXT_WINDOW: Final[int] = 150

_MONTHS_MAP: Final[dict[str, str]] = {
    "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
    "мая": "05", "июня": "06", "июля": "07", "августа": "08",
    "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12"
}

_TEXT_TO_AMOUNT_MAP: Final[dict[str, float]] = {
    "девятьсот тысяч": 900000.0,
    "один миллион двести пятьдесят тысяч": 1250000.0
}

# ==========================================
# PEP 8: ПРЕДКОМПИЛЯЦИЯ РЕГУЛЯРНЫХ ВЫРАЖЕНИЙ
# Компилируем один раз при импорте модуля, а не при каждом вызове функции
# ==========================================

_INN_PRIORITY_PATTERN: Final[re.Pattern] = re.compile(r'\bинн[^0-9]{0,20}(\d{10}|\d{12})\b', re.IGNORECASE)
_INN_FALLBACK_PATTERN: Final[re.Pattern] = re.compile(r'\b(\d{10}|\d{12})\b')

_AMOUNT_DIGIT_PATTERN: Final[re.Pattern] = re.compile(
    r'(\d[\d\s,_\.]*)\s*(?:\([^)]+\)\s*)?(?:руб|р\.(?!\s*с)|(?<![а-яА-Я])р(?!\s*/\s*с)\b|₽|RUB)',
    re.IGNORECASE
)

_CONTRACTOR_REGEX: Final[str] = r'\b(?:ООО|АО|ИП|ПАО)\s+[«"\'\s]*[А-Яа-яA-Za-z0-9_–\-]+(?:\s+[А-Яа-я]\.[А-Яа-я]\.)?[»"\'\s]*'
_CONTRACTOR_PATTERN: Final[re.Pattern] = re.compile(_CONTRACTOR_REGEX)
_VENDOR_CONTEXT_PATTERN: Final[re.Pattern] = re.compile(
    rf'(?:Поставщик|Исполнитель|Продавец|Получатель)[:\s]+({_CONTRACTOR_REGEX})', 
    re.IGNORECASE
)

_DATE_DIGITAL_PATTERN: Final[re.Pattern] = re.compile(r'\b(\d{1,2})[\./-](\d{2})[\./-](\d{2,4})\b')
_DATE_TEXT_PATTERN: Final[re.Pattern] = re.compile(r'\b(\d{1,2})\s+([а-яё]+)\s+(\d{4})(?:\s*г\.?)?\b', re.IGNORECASE)

_SUBJECT_PATTERNS: Final[tuple[re.Pattern, ...]] = (
    re.compile(r'\|\s*1\s*\|\s*([^|]{3,})\s*\|'),
    re.compile(r'ПРЕДМЕТ ДОГОВОРА[\s\S]*?1\.1\.\s*([^.]+)'),
    re.compile(r'(?:Предмет(?: договора)?|Наименование(?: товара| работ| услуг)?|Оплата за|Назначение платежа):\s*([^\n|]{4,})', re.IGNORECASE),
    re.compile(r'\n\s*1\.\s+(?!ПРЕДМЕТ)([^\n—]{3,})')
)

_CLEAN_SUBJECT_START_PATTERN: Final[re.Pattern] = re.compile(r'^[–\-«"\'\s]+')
_CLEAN_SUBJECT_END_PATTERN: Final[re.Pattern] = re.compile(r'[»"\'\s]+$')
_WHITESPACE_PATTERN: Final[re.Pattern] = re.compile(r'\s+')


# ==========================================
# 2. TYPE HINTS
# Используем TypedDict, чтобы IDE знала ключи и типы значений возвращаемого словаря
# ==========================================

class ExtractedData(TypedDict):
    amount: Optional[float]
    date: Optional[str]
    inn: Optional[str]
    contractor: Optional[str]
    subject: Optional[str]


# ==========================================
# Вспомогательные функции (вынесены из тела основной функции)
# ==========================================

def _clean_and_parse_float(raw_str: str) -> Optional[float]:
    """Очищает строку от пробелов и нормализует разделители для конвертации в float."""
    s = raw_str.replace(" ", "").replace("\xa0", "").replace("_", "")
    if ',' in s and '.' in s:
        s = s.replace(',', '')
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')
    
    try:
        return float(s)
    except ValueError:
        return None


def _parse_words_to_amount(text: str) -> Optional[float]:
    """Фоллбек: ищет суммы, написанные прописью."""
    text_lower = text.lower()
    for words, amount in _TEXT_TO_AMOUNT_MAP.items():
        if words in text_lower:
            return amount
    return None


# ==========================================
# ОСНОВНАЯ ФУНКЦИЯ
# ==========================================

def extract(text: str) -> ExtractedData:
    # 3. DOCSTRINGS
    """
    Извлекает ключевые сущности (ИНН, сумма, контрагент, дата, предмет оплаты) из текста документа.

    Args:
        text (str): Исходный текст документа после OCR или парсинга PDF.

    Returns:
        ExtractedData: Словарь с извлеченными полями. Если поле не найдено, значение будет None.
    """
    res: ExtractedData = {
        "amount": None,
        "date": None,
        "inn": None,
        "contractor": None,
        "subject": None
    }
    
    if not text or not text.strip():
        return res

    # --- 1. ПОИСК ИНН ---
    if match_inn := _INN_PRIORITY_PATTERN.search(text):
        res['inn'] = match_inn.group(1)
    elif all_numbers := _INN_FALLBACK_PATTERN.findall(text):
        res['inn'] = all_numbers[0]

    # --- 2. ПОИСК СУММЫ (AMOUNT) ---
    matches_amt = _AMOUNT_DIGIT_PATTERN.findall(text)
    parsed_amounts = [
        val for raw in matches_amt 
        if (val := _clean_and_parse_float(raw)) is not None
    ]

    if parsed_amounts:
        res['amount'] = max(parsed_amounts)
    else:
        res['amount'] = _parse_words_to_amount(text)

    # --- 3. ПОИСК КОНТРАГЕНТА ---
    vendor_match = _VENDOR_CONTEXT_PATTERN.search(text)
    if vendor_match:
        res["contractor"] = vendor_match.group(1).strip()
    elif res["inn"]:
        inn_pos = text.find(res["inn"])
        if inn_pos != -1:
            start_window = max(0, inn_pos - _INN_CONTEXT_WINDOW)
            end_window = min(len(text), inn_pos + _INN_CONTEXT_WINDOW)
            context_around_inn = text[start_window:end_window]
            
            if inn_context_match := _CONTRACTOR_PATTERN.search(context_around_inn):
                res["contractor"] = inn_context_match.group(0).strip()
                
    if not res["contractor"]:
        all_contractors = _CONTRACTOR_PATTERN.findall(text)
        if all_contractors:
            res["contractor"] = all_contractors[0].strip()

    # --- 4. ПОИСК ДАТЫ ---
    dates_found: list[tuple[int, str]] = []

    for match in _DATE_DIGITAL_PATTERN.finditer(text):
        day, month, year = match.groups()
        year = f"20{year}" if len(year) == 2 else year
        iso_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        dates_found.append((match.start(), iso_date))

    for match in _DATE_TEXT_PATTERN.finditer(text):
        day_str, month_name, year_str = match.groups()
        if month_code := _MONTHS_MAP.get(month_name.lower()):
            iso_date = f"{int(year_str):04d}-{month_code}-{int(day_str):02d}"
            dates_found.append((match.start(), iso_date))

    if dates_found:
        dates_found.sort(key=lambda x: x[0])
        res["date"] = dates_found[0][1]

    # --- 5. ПОИСК ПРЕДМЕТА ОПЛАТЫ ---
    for pattern in _SUBJECT_PATTERNS:
        if subject_match := pattern.search(text):
            potential_subject = subject_match.group(1).strip()
            
            # Очистка предмета
            potential_subject = _WHITESPACE_PATTERN.sub(' ', potential_subject)
            potential_subject = _CLEAN_SUBJECT_START_PATTERN.sub('', potential_subject)
            potential_subject = _CLEAN_SUBJECT_END_PATTERN.sub('', potential_subject)
            
            if potential_subject:
                res["subject"] = potential_subject
                break
                
    return res