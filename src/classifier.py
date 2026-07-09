import enum
from typing import Final

class DocType(str, enum.Enum):
    CONTRACT = "contract"
    SPEC = "spec"
    INVOICE = "invoice"
    ACT = "act"
    UNKNOWN = "unknown"

CONFIDENCE_MARGIN_THRESHOLD: Final[float] = 0.20
DEFAULT_CONFIDENCE: Final[float] = 0.0
KEYWORD_MARKERS: Final[dict[DocType, tuple[str, ...]]] = {
    DocType.CONTRACT: (
        "договор", "предмет договора", "права и обязанности", 
        "настоящий договор", "ответственность сторон"
    ),
    DocType.SPEC: (
        "спецификация", "приложение к договору", "номенклатура", 
        "товарная позиция", "итого по спецификации"
    ),
    DocType.INVOICE: (
        "счёт на оплату", "счет №", "плательщик", "получатель", "к оплате"
    ),
    DocType.ACT: (
        "универсальный передаточный документ", "упд", "акт выполненных работ", 
        "работы выполнены", "услуги оказаны"
    ),
}

def classify(text: str) -> tuple[DocType, float]:
    """
    Классифицирует документ по тексту на основе частотности ключевых слов.
    """
    if not text or not text.strip():
        return DocType.UNKNOWN, DEFAULT_CONFIDENCE

    text_lower = text.lower()
    raw_scores: dict[DocType, int] = {}
    total_matches = 0

    for doc_type, words in KEYWORD_MARKERS.items():
        matches = sum(word in text_lower for word in words)
        raw_scores[doc_type] = matches
        total_matches += matches

    if total_matches == 0:
        return DocType.UNKNOWN, DEFAULT_CONFIDENCE

    sorted_scores = sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)
    top1_type, top1_raw = sorted_scores[0]
    _, top2_raw = sorted_scores[1]

    top1_confidence = top1_raw / total_matches
    top2_confidence = top2_raw / total_matches

    if (top1_confidence - top2_confidence) < CONFIDENCE_MARGIN_THRESHOLD:
        return DocType.UNKNOWN, DEFAULT_CONFIDENCE

    return top1_type, round(top1_confidence, 2)