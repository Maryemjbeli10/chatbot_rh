"""
Garde-fous avancés pour le RAG.
"""

import re
import requests

INJECTION_PATTERNS = [
    r"ignore (les|tes|toutes les) (instructions|consignes)",
    r"tu es maintenant",
    r"system prompt",
    r"forget (previous|all) instructions",
    r"nouvelle personnalité",
    r"réponds uniquement",
]


def sanitize_chunk(text: str) -> str:
    cleaned = text
    for pattern in INJECTION_PATTERNS:
        cleaned = re.sub(pattern, "[contenu neutralisé]", cleaned, flags=re.IGNORECASE)
    return cleaned


COHERENCE_PROMPT = """Tu es un vérificateur strict. Voici un CONTEXTE et une REPONSE générée par un autre assistant.
Réponds uniquement par "OUI" si chaque information factuelle de la réponse est bien présente ou déductible
du contexte, ou par "NON" si la réponse contient une information absente du contexte (invention/hallucination).
Ne réponds rien d'autre que OUI ou NON.

CONTEXTE:
{context}

REPONSE A VERIFIER:
{answer}
"""


def check_coherence(answer: str, context: str, ollama_url: str, ollama_model: str, timeout: int = 180) -> bool:
    prompt = COHERENCE_PROMPT.format(context=context, answer=answer)
    try:
        response = requests.post(
            ollama_url,
            json={
                "model": ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        verdict = response.json()["message"]["content"].strip().upper()
        return verdict.startswith("OUI")
    except Exception:
        return True  # fail-open : on ne bloque pas si le vérificateur est indisponible


def is_ambiguous(chunks: list, distance_gap_threshold: float = 0.05, confident_distance: float = 0.55) -> bool:
    """
    Détecte une vraie ambiguïté entre deux sujets différents.
    - Si le meilleur résultat est déjà confiant, on ne redemande pas de précision.
    - faq_generale.md est exclu de la comparaison (duplique volontairement les autres docs).
    """
    if len(chunks) < 2:
        return False
    if chunks[0]["distance"] < confident_distance:
        return False

    relevant = [c for c in chunks[:3] if c["source"] != "faq_generale.md"]
    if len(relevant) < 2:
        return False

    sources = {c["source"] for c in relevant[:2]}
    gap = abs(relevant[0]["distance"] - relevant[1]["distance"])
    return len(sources) > 1 and gap < distance_gap_threshold


EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_RE = re.compile(r"\b(\+?\d[\d \-\.]{7,}\d)\b")


def scrub_pii(text: str) -> str:
    text = EMAIL_RE.sub("[email masqué]", text)
    text = PHONE_RE.sub("[téléphone masqué]", text)
    return text
