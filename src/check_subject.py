import os
import logging
from typing import Tuple
TARGET_KEYWORDS = (
    "семян", "удобрен", "карбамид", "агро", "сельхоз", "сельскохозяйств",
    "трактор", "посев", "пшениц", "подсолнечн", "продукц"
)

# Тяжелые зависимости далее, поэтому загружаем их один раз при импорте модуля
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    from pydantic import BaseModel, Field

    class TargetCheck(BaseModel):
        matches: bool = Field(description="True, если предмет относится к целевому агрокредитованию, иначе False")
        confidence: float = Field(description="Степень уверенности от 0.0 до 1.0")
        reason: str = Field(description="Краткое объяснение принятого решения")

    _LLM_PARSER = JsonOutputParser(pydantic_object=TargetCheck)
    
    _LLM_TEMPLATE = """Вы - строгий банковский аудитор. Ваша задача - определить, подходит ли предмет оплаты под условия целевого агрокредитования.
    Целевые расходы: покупка семян, удобрений, сельхозтехники, оплата агрохимических работ.
    Нецелевые расходы: смартфоны, мебель, маркетинговые услуги, легковые автомобили, аренда офиса.

    Примеры (Few-shot):
    Предмет: "Карбамид марки Б, ГОСТ 2081-2010"
    Ответ: {{"matches": true, "confidence": 0.99, "reason": "Карбамид является азотным удобрением, что относится к целевым расходам."}}

    Предмет: "Оплата услуг маркетингового агентства по договору"
    Ответ: {{"matches": false, "confidence": 0.95, "reason": "Маркетинговые услуги не связаны с сельскохозяйственным производством."}}

    {format_instructions}

    Предмет: "{subject}"
    Ответ:"""

    _LLM_PROMPT = PromptTemplate(
        template=_LLM_TEMPLATE,
        input_variables=["subject"],
        partial_variables={"format_instructions": _LLM_PARSER.get_format_instructions()}
    )
    
    LLM_DEPENDENCIES_LOADED = True
except ImportError:
    LLM_DEPENDENCIES_LOADED = False


def check_subject_fallback(subject: str) -> tuple[bool, float, str]:
    """
    Резервный алгоритм проверки целевого использования через Keyword Matching.
    Запускается, если нет ключа OPENAI_API_KEY или API недоступно.
    """
    subject_lower = subject.lower()
    
    if any(keyword in subject_lower for keyword in TARGET_KEYWORDS):
        return True, 0.85, "[Fallback] Обнаружены маркеры сельскохозяйственной номенклатуры."
    
    return False, 0.60, "[Fallback] Не найдено ключевых слов целевого использования."


def check_subject_llm(subject: str) -> tuple[bool, float, str]:
    """Основной алгоритм с использованием LangChain и OpenAI API."""
    if not LLM_DEPENDENCIES_LOADED:
        raise ImportError("Библиотеки LangChain или Pydantic не установлены.")

    # Инициализируем LLM здесь на случай, если ключ был задан в os.environ динамически
    llm = ChatOpenAI(temperature=0.0, model="gpt-3.5-turbo")
    chain = _LLM_PROMPT | llm | _LLM_PARSER
    
    result = chain.invoke({"subject": subject})
    
    return result["matches"], result["confidence"], result["reason"]


def check_subject(subject: str) -> tuple[bool, float, str]:
    """
    Проверяет предмет оплаты на целевое использование.
    Автоматически переключается на Fallback, если нет доступа к API или произошла ошибка.
    """
    if not subject or not subject.strip():
        return False, 0.0, "Пустая строка предмета оплаты."

    if LLM_DEPENDENCIES_LOADED and os.environ.get("OPENAI_API_KEY"):
        try:
            return check_subject_llm(subject)
        except Exception as e:
            # Лог ошибки
            logging.warning(f"Ошибка LLM (переход на Fallback): {e}")
            return check_subject_fallback(subject)
    return check_subject_fallback(subject)