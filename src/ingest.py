"""
Indexation des documents internes : chunking + embeddings multilingues + ChromaDB.
"""

import os
import hashlib
import chromadb
from chromadb.utils import embedding_functions

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "documents")
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME = "documents_rh"

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            last_break = text.rfind("\n\n", start, end)
            if last_break != -1 and last_break > start + 100:
                end = last_break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end - overlap > start else end
    return chunks


def file_hash(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def load_documents():
    docs = []
    for fname in sorted(os.listdir(DOCS_DIR)):
        if fname.endswith((".md", ".txt")):
            fpath = os.path.join(DOCS_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            docs.append({"filename": fname, "content": content, "hash": file_hash(fpath)})
    return docs


def build_index(verbose: bool = True):
    os.makedirs(DB_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=DB_DIR)

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    # IMPORTANT : on force la métrique cosinus. Sans "hnsw:space", Chroma utilise
    # par défaut la distance L2, incompatible avec le seuil de confiance calibré
    # dans rag_engine.py (DISTANCE_THRESHOLD), ce qui casse la détection de pertinence.
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    documents = load_documents()
    if not documents:
        if verbose:
            print(f"⚠️  Aucun document trouvé dans {DOCS_DIR}")
        return

    all_ids, all_chunks, all_metadatas = [], [], []
    for doc in documents:
        chunks = chunk_text(doc["content"])
        for i, chunk in enumerate(chunks):
            all_ids.append(f"{doc['filename']}_{i}")
            all_chunks.append(chunk)
            all_metadatas.append({"source": doc["filename"], "chunk_index": i})

    collection.add(ids=all_ids, documents=all_chunks, metadatas=all_metadatas)

    with open(os.path.join(DB_DIR, "file_hashes.txt"), "w") as f:
        for doc in documents:
            f.write(f"{doc['filename']}:{doc['hash']}\n")

    if verbose:
        print(f"✅ Index créé : {len(all_chunks)} chunks à partir de {len(documents)} documents.")


def index_is_stale() -> bool:
    hash_file = os.path.join(DB_DIR, "file_hashes.txt")
    if not os.path.exists(hash_file):
        return True

    stored = {}
    with open(hash_file) as f:
        for line in f:
            if ":" in line:
                name, h = line.strip().split(":", 1)
                stored[name] = h

    current_docs = load_documents()
    current = {d["filename"]: d["hash"] for d in current_docs}
    return current != stored


if __name__ == "__main__":
    build_index()
