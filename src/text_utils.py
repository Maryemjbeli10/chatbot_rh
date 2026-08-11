"""
Normalisation robuste des questions utilisateur.
"""

import re
import unicodedata
from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0


def normalize_text(text: str) -> str:
    if not text:
        return text
    text = text.strip()
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([!?.])\1{1,}", r"\1", text)
    text = re.sub(r"([a-zA-Zàâäéèêëïîôöùûüç])\1{2,}", r"\1\1", text)
    return text.strip()


def detect_language(text: str) -> str:
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    if arabic_chars > 0 and arabic_chars / max(len(text), 1) > 0.3:
        return "ar"
    try:
        lang = detect(text)
        if lang.startswith("ar"):
            return "ar"
        if lang.startswith("fr"):
            return "fr"
        if lang.startswith("en"):
            return "en"
        return lang
    except LangDetectException:
        return "unknown"


def strip_accents_lower(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


LANGUAGE_INSTRUCTIONS = {
    "fr": "Réponds UNIQUEMENT en français, de façon claire et professionnelle. N'utilise aucun mot d'une autre langue (pas de chinois, russe, anglais...).",
    "ar": "أجب باللغة العربية الفصحى فقط، بشكل واضح ومهني. ممنوع منعاً باتاً استخدام أي حرف أو كلمة صينية أو روسية أو إنجليزية. اكتب فقط بالأحرف العربية.",
    "en": "Answer ONLY in English, clearly and professionally. Do not mix in any other language or script.",
    "unknown": "Réponds dans la même langue que la question posée par l'utilisateur, sans mélanger avec aucune autre langue ou écriture.",
}


def get_language_instruction(lang_code: str) -> str:
    return LANGUAGE_INSTRUCTIONS.get(lang_code, LANGUAGE_INSTRUCTIONS["unknown"])
