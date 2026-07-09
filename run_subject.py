import logging
from pathlib import Path
from typing import Iterator, Tuple

from src.check_subject import check_subject

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FILE_PATH = BASE_DIR / "tests_ds_credit" / "subjects_test.txt"


def iter_test_cases(file_path: Path) -> Iterator[Tuple[str, str]]:
    """
    Читает файл и возвращает пары (ожидаемый_результат, предмет).
    Игнорирует пустые строки и комментарии.
    """
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "|" in line:
                expected, subject = line.split("|", 1)
            else:
                expected, subject = "N/A", line

            yield expected.strip(), subject.strip()


def run_subject(file_path: Path = DEFAULT_FILE_PATH) -> None:
    """
    Запускает проверку предметов оплаты и выводит результаты в виде выровненной таблицы.
    """
    if not file_path.is_file():
        logging.error(f"Файл не найден: {file_path}")
        return

    print(f"\nРезультаты проверки предметов оплаты ({file_path.name})\n")

    # Форматирование заголовка таблицы с фиксированной шириной колонок
    header = f"| {'Предмет оплаты':<48} | {'Ожидалось':<10} | {'Результат':<10} | {'Уверенность':<11} | {'Причина (Reason)':<53} |"
    separator = f"|{'-'*50}|{'-'*12}|{'-'*11}|{'-'*13}|{'-'*55}|"
    
    print(header)
    print(separator)

    for expected, subject in iter_test_cases(file_path):
        # Обработка возможных исключений при вызове внешней функции
        try:
            matches, confidence, reason = check_subject(subject)
            our_result = "PASS" if matches else "FAIL"
        except Exception as e:
            our_result = "ERROR"
            confidence = 0.0
            reason = f"Exception: {str(e)}"

        # Обрезка строк для сохранения ровной структуры таблицы
        short_subject = f"{subject[:45]}..." if len(subject) > 48 else subject
        short_reason = f"{reason[:50]}..." if len(reason) > 53 else reason

        print(f"| {short_subject:<48} | {expected:<10} | {our_result:<10} | {confidence:<11.2f} | {short_reason:<53} |")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_subject()