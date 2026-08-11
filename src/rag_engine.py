"""
Moteur RAG : recherche vectorielle + appel Ollama + garde-fous anti-hallucination + citations.

Version avec logs de diagnostic (print) à chaque étape, pour identifier précisément
où un traitement bloque ou ralentit. Les logs s'affichent dans le terminal PowerShell
où tourne `streamlit run app.py` (pas dans le navigateur).
"""

import os
import time
import requests
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# Charge automatiquement le fichier .env à la racine du projet, quel que soit le
# terminal utilisé (cmd, PowerShell...) ou si l'utilisateur a oublié de définir
# les variables d'environnement manuellement. C'est la source de configuration
# permanente : plus besoin de taper "set" ou "$env:" à chaque lancement.
load_dotenv()

from .text_utils import normalize_text, detect_language, get_language_instruction
from .ingest import DB_DIR, COLLECTION_NAME, EMBEDDING_MODEL
from .guardrails import sanitize_chunk, check_coherence, is_ambiguous

# Valeurs par défaut alignées sur la configuration validée comme fonctionnelle
# (qwen2.5:3b : rapide sur CPU, bon support de l'arabe) — même en l'absence
# totale de fichier .env ou de variable d'environnement, le système démarre
# avec une configuration correcte plutôt qu'avec l'ancien défaut lent (llama3.1).
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))

DISTANCE_THRESHOLD = 1.1
TOP_K = 4
SKIP_COHERENCE_CHECK = os.environ.get("SKIP_COHERENCE_CHECK", "0") == "1"

print(f"[rag] Configuration : OLLAMA_MODEL={OLLAMA_MODEL} | OLLAMA_URL={OLLAMA_URL} | "
      f"OLLAMA_TIMEOUT={OLLAMA_TIMEOUT}s | SKIP_COHERENCE_CHECK={SKIP_COHERENCE_CHECK}", flush=True)

_client = None
_collection = None


def _log(msg):
    print(f"[rag] {msg}", flush=True)


def _get_collection(force_refresh: bool = False):
    global _client, _collection
    if _collection is None or force_refresh:
        _log("Connexion à ChromaDB et chargement du modèle d'embeddings...")
        t0 = time.time()
        _client = chromadb.PersistentClient(path=DB_DIR)
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        _collection = _client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)
        _log(f"Collection chargée en {time.time() - t0:.1f}s")
    return _collection


def retrieve(question: str, top_k: int = TOP_K):
    _log("ÉTAPE 1/4 — Début de la recherche vectorielle (embeddings + ChromaDB)")
    t0 = time.time()
    collection = _get_collection()
    try:
        results = collection.query(query_texts=[question], n_results=top_k)
    except Exception as e:
        _log(f"Échec de la requête ({e}), rafraîchissement de la collection...")
        collection = _get_collection(force_refresh=True)
        results = collection.query(query_texts=[question], n_results=top_k)
    _log(f"ÉTAPE 1/4 — Recherche terminée en {time.time() - t0:.1f}s")

    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    return [
        {
            "text": sanitize_chunk(c),
            "source": m["source"],
            "chunk_index": m["chunk_index"],
            "distance": d,
        }
        for c, m, d in zip(chunks, metadatas, distances)
    ]


SYSTEM_PROMPT_TEMPLATE = """Tu es l'assistant RH/juridique interne de l'entreprise. Tu réponds UNIQUEMENT
à partir des extraits de documents fournis ci-dessous (contexte). Règles strictes :

1. N'invente JAMAIS d'information absente du contexte fourni.
2. Si le contexte ne contient pas la réponse, dis clairement que tu ne trouves pas
   cette information dans les documents internes et invite l'utilisateur à contacter le service RH.
3. Cite toujours la source (nom du document) sur laquelle tu bases ta réponse.
4. Reste concis, professionnel et bienveillant.
5. {lang_instruction}

Contexte (extraits des documents internes) :
---
{context}
---
"""


def build_context(chunks):
    return "\n\n".join(f"[Source: {c['source']}]\n{c['text']}" for c in chunks)


def call_ollama(system_prompt: str, history: list, question: str) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.2,  # réponses plus factuelles/déterministes, moins de dérives
        },
    }

    _log(f"ÉTAPE 3/4 — Envoi de la requête à Ollama ({OLLAMA_URL}, modèle={OLLAMA_MODEL})...")
    t0 = time.time()
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        _log(f"ÉTAPE 3/4 — Réponse Ollama reçue en {time.time() - t0:.1f}s")
        return data["message"]["content"]
    except requests.exceptions.ConnectionError as e:
        _log(f"ÉCHEC — Connexion à Ollama impossible après {time.time() - t0:.1f}s : {e}")
        return (
            "⚠️ Impossible de contacter Ollama. Vérifie qu'Ollama est bien lancé "
            f"(`ollama serve`) et que le modèle `{OLLAMA_MODEL}` est installé "
            f"(`ollama pull {OLLAMA_MODEL}`)."
        )
    except Exception as e:
        _log(f"ÉCHEC — Erreur après {time.time() - t0:.1f}s : {e}")
        return f"⚠️ Erreur lors de l'appel au modèle : {e}"


def answer_question(question: str, history: list = None) -> dict:
    history = history or []
    _log(f"===== NOUVELLE QUESTION : {question!r} =====")

    clean_question = normalize_text(question)
    lang = detect_language(clean_question)
    _log(f"ÉTAPE 0/4 — Langue détectée : {lang}")

    chunks = retrieve(clean_question)

    if not chunks or chunks[0]["distance"] > DISTANCE_THRESHOLD:
        _log("Aucun contexte assez pertinent trouvé -> réponse 'non trouvé' sans appeler Ollama")
        msg = {
            "fr": "Je ne trouve pas cette information dans les documents internes disponibles. "
                  "Merci de contacter le service RH pour une réponse précise.",
            "ar": "لا أجد هذه المعلومة في الوثائق الداخلية المتوفرة. يرجى التواصل مع قسم الموارد البشرية.",
            "en": "I could not find this information in the internal documents. "
                  "Please contact the HR department for an accurate answer.",
        }.get(lang, "Je ne trouve pas cette information dans les documents internes disponibles.")
        return {
            "answer": msg, "sources": [], "confidence": "faible", "language": lang,
            "no_context_found": True, "ambiguous": False, "coherent": True,
        }

    if is_ambiguous(chunks):
        _log("Question jugée ambiguë -> demande de précision sans appeler Ollama")
        top_sources = sorted(set(c["source"] for c in chunks[:2]))
        msg = {
            "fr": f"Votre question peut concerner plusieurs sujets ({' ou '.join(top_sources)}). "
                  "Pouvez-vous préciser votre demande ?",
            "ar": "قد يتعلق سؤالك بعدة مواضيع مختلفة. هل يمكنك توضيح طلبك؟",
            "en": f"Your question could relate to several topics ({' or '.join(top_sources)}). "
                  "Could you clarify your request?",
        }.get(lang, "Votre question peut concerner plusieurs sujets, pouvez-vous préciser ?")
        return {
            "answer": msg, "sources": top_sources, "confidence": "moyenne", "language": lang,
            "no_context_found": False, "ambiguous": True, "coherent": True,
        }

    _log("ÉTAPE 2/4 — Construction du prompt avec le contexte récupéré")
    context = build_context(chunks)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        context=context, lang_instruction=get_language_instruction(lang)
    )

    answer = call_ollama(system_prompt, history, clean_question)

    # Si le 1er appel a échoué (timeout, erreur réseau...), inutile de lancer un 2e appel
    # de vérification sur un message d'erreur — ça doublerait l'attente pour rien.
    llm_call_failed = answer.startswith("⚠️")

    best_distance = chunks[0]["distance"]
    confidence = "haute" if best_distance < 0.6 else "moyenne" if best_distance < 0.9 else "faible"

    if llm_call_failed:
        _log("ÉTAPE 4/4 — Ignorée (le 1er appel a déjà échoué, pas de 2e appel inutile)")
        coherent = True  # rien à vérifier, l'erreur est déjà explicite pour l'utilisateur
        confidence = "faible"
    elif SKIP_COHERENCE_CHECK:
        _log("ÉTAPE 4/4 — Vérification de cohérence DÉSACTIVÉE (SKIP_COHERENCE_CHECK=1)")
        coherent = True
    else:
        _log("ÉTAPE 4/4 — Vérification de cohérence (2e appel Ollama)...")
        t0 = time.time()
        coherent = check_coherence(answer, context, OLLAMA_URL, OLLAMA_MODEL)
        _log(f"ÉTAPE 4/4 — Vérification terminée en {time.time() - t0:.1f}s (cohérent={coherent})")

    if not coherent and not llm_call_failed:
        confidence = "faible"
        warning = {
            "fr": "\n\n⚠️ Cette réponse n'a pas pu être entièrement vérifiée par rapport aux documents. Vérifiez l'information auprès du service RH.",
            "ar": "\n\n⚠️ لم يتم التحقق الكامل من هذه الإجابة مقارنة بالوثائق. يرجى التأكد من المعلومة مع قسم الموارد البشرية.",
            "en": "\n\n⚠️ This answer could not be fully verified against the source documents. Please confirm with HR.",
        }.get(lang, "\n\n⚠️ Réponse non entièrement vérifiée, merci de confirmer auprès du service RH.")
        answer += warning

    sources = sorted(set(c["source"] for c in chunks))
    _log("===== QUESTION TERMINÉE =====")

    return {
        "answer": answer, "sources": sources, "confidence": confidence, "language": lang,
        "no_context_found": False, "ambiguous": False, "coherent": coherent,
    }