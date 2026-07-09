import pytest
from pathlib import Path
from typing import Dict, Any
from src.extractor import extract
from src.classifier import classify
from src.check_subject import check_subject, check_subject_fallback

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "tests_ds_credit"

# Эталонные Данные
EXPECTED_DATA = [
    ("contract_001.txt", {"amount": 1250000.0, "date": "2025-03-01", "inn": "7701234567", "contractor": "ООО «ТехАгро»"}),
    ("invoice_001.txt",  {"amount": 1250000.0, "date": "2025-03-03", "inn": "7701234567", "contractor": "ООО «ТехАгро»"}),
    ("invoice_002.txt",  {"amount": 900000.0,  "date": "2025-02-15", "inn": "5047123456", "contractor": "АО «АгроСнаб»"}),
    ("act_001.txt",      {"amount": 1250000.0, "date": "2025-03-24", "inn": "7701234567", "contractor": "ООО «ТехАгро»"}),
    ("act_002.txt",      {"amount": 500000.0,  "date": "2025-04-01", "inn": "504712345678", "contractor": "ИП Смирнов В.А."}),
]

@pytest.fixture
def get_file_content():
    """Фикстура-фабрика: возвращает функцию для чтения текста из файла датасета."""
    def _read_file(file_name: str) -> str:
        file_path = DATASET_DIR / file_name
        assert file_path.exists(), f"Файл {file_name} не найден в папке {DATASET_DIR}"
        return file_path.read_text(encoding="utf-8")
    return _read_file


class TestExtractor:
    """Группа тестов для модуля extract"""
    
    @pytest.mark.parametrize("file_name, expected", EXPECTED_DATA)
    def test_extract_dataset(self, get_file_content, file_name: str, expected: Dict[str, Any]):
        text_content = get_file_content(file_name)
        result = extract(text_content)
        
        assert result["inn"] == expected["inn"], f"Ошибка ИНН в файле {file_name}"
        assert result["amount"] == expected["amount"], f"Ошибка суммы в файле {file_name}"
        assert result["date"] == expected["date"], f"Ошибка даты в файле {file_name}"
        assert expected["contractor"] in result["contractor"], f"Ошибка контрагента в {file_name}"

    def test_mandatory_cases(self):
        assert extract("Сумма: 1 250 000,00 руб.")["amount"] == 1250000.0
        assert extract("ИНН 7701234567")["inn"] == "7701234567"
        assert extract("без цифр").get("amount") is None

class TestClassifier:
    """Группа тестов для модуля classify"""
    
    # Символ '_' используется для переменной expected, так как в этом тесте нам нужно только имя файла
    @pytest.mark.parametrize("file_name, _", EXPECTED_DATA)
    def test_classify_dataset(self, get_file_content, file_name: str, _):
        text_content = get_file_content(file_name)
        expected_doc_type = file_name.split("_")[0]
        
        doc_type, confidence = classify(text_content)
        
        assert doc_type in (expected_doc_type, 'unknown'), \
            f"Ожидали '{expected_doc_type}' или 'unknown', получили '{doc_type}'"
        assert confidence >= 0.5 or confidence == 0.0, \
            f"Уверенность {confidence} не подходит"


class TestSubjectChecker:
    """Группа тестов для модуля check_subject"""
    
    def test_schema(self):
        result = check_subject("Поставка семян пшеницы")
        
        assert isinstance(result, tuple) and len(result) == 3, "Ответ должен быть кортежем из 3 элементов"
        matches, confidence, reason = result
        
        assert isinstance(matches, bool), "matches должен быть bool"
        assert isinstance(confidence, float), "confidence должен быть float"
        assert isinstance(reason, str), "reason должен быть str"

    def test_empty_string(self):
        matches, confidence, reason = check_subject("   ")
        
        assert matches is False
        assert confidence == 0.0
        assert reason == "Пустая строка предмета оплаты."

    @pytest.mark.parametrize("file_name, _", EXPECTED_DATA)
    def test_dataset(self, get_file_content, file_name: str, _):
        text_content = get_file_content(file_name)
        subject_text = extract(text_content).get("subject", "")
        
        matches, _, reason = check_subject(subject_text)
        assert matches is True, f"Ошибка в {file_name}: алгоритм посчитал покупку нецелевой. Причина: {reason}"


class TestSubjectCheckerFallback:
    """Группа тестов для fallback-функции проверки предмета оплаты."""
    
    def test_positive_target(self):
        matches, confidence, _ = check_subject_fallback("Карбамид марки Б, ГОСТ 2081-2010")
        assert matches is True
        assert confidence > 0.0

    def test_negative_target(self):
        matches, _, _ = check_subject_fallback("Офисная мебель и кресла")
        assert matches is False

    @pytest.mark.parametrize("file_name, _", EXPECTED_DATA)
    def test_dataset(self, get_file_content, file_name: str, _):
        text_content = get_file_content(file_name)
        subject_text = extract(text_content).get("subject", "")
            
        matches, _, reason = check_subject_fallback(subject_text)
        assert matches is True, f"Fallback ошибся в {file_name}: не распознал целевую покупку. Причина: {reason}"


def test_extract_complex_ocr_file():
    """Тест для намеренно сложного файла scan_ocr_001.txt."""
    file_path = DATASET_DIR / "scan_ocr_001.txt"
    
    with open(file_path, "r", encoding="utf-8") as f:
        text_content = f.read()
        
    result = extract(text_content)
    
    # Проверяем, что функция вернула словарь (не упала)
    assert isinstance(result, dict)
    
    # Проверяем, что поля присутствуют (даже если они None)
    expected_keys = ["amount", "date", "inn", "contractor", "subject"]
    for key in expected_keys:
        assert key in result, f"Поле {key} должно быть в ответе даже для сложного файла"