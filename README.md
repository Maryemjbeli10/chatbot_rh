# Chatbot RH/Juridique interne — RAG 100% gratuit (Ollama + Chroma)

## Installation locale — de A à Z (Windows, PowerShell)

**1. Installer Ollama** : https://ollama.com/download

**2. Télécharger un modèle LÉGER (important sur un PC sans carte graphique) :**
```powershell
ollama pull qwen2.5:3b
```
`qwen2.5:3b` (~2 Go) est nettement plus rapide sur CPU que `llama3.1` (8B, ~4.7 Go) et bien meilleur en arabe.

**3. Dézipper le projet, puis dans PowerShell (vérifie que le prompt affiche bien `PS` au début) :**
```powershell
cd C:\rag-chatbot-rh
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**4. Indexer les documents :**
```powershell
python -m src.ingest
```
Doit afficher : `✅ Index créé : 45 chunks à partir de 9 documents.`

**5. Lancer l'application, en précisant le modèle léger AVANT de lancer :**
```powershell
$env:OLLAMA_MODEL = "qwen2.5:3b"
$env:OLLAMA_TIMEOUT = "600"
streamlit run app.py
```
⚠️ Ces variables ne valent que pour la fenêtre PowerShell où elles sont tapées — relance tout dans le **même terminal**, ne pas ouvrir une nouvelle fenêtre entre les deux.

**6. Se connecter :** `employee1` / `conges2026`

## Dépannage — problèmes déjà rencontrés et résolus

| Symptôme | Cause | Solution |
|---|---|---|
| Le bot répond "je ne trouve pas" même pour des questions simples | ChromaDB utilisait la distance L2 par défaut au lieu du cosinus | Corrigé dans `ingest.py` (`metadata={"hnsw:space": "cosine"}`) — si ton index est ancien, supprime `data/chroma_db` et relance `python -m src.ingest` |
| "Votre question peut concerner plusieurs sujets" sur des questions claires | Détection d'ambiguïté trop sensible, perturbée par la FAQ qui duplique le contenu | Corrigé dans `guardrails.py` |
| `Read timed out (read timeout=...)` | Modèle trop lourd (`llama3.1`, 8B) pour un CPU sans GPU | Utiliser `qwen2.5:3b`, plus léger et rapide |
| Réponse en arabe mélangée avec du russe/anglais | Modèle trop petit gère mal le multilingue, ou mauvais modèle utilisé par erreur | `qwen2.5:3b` gère bien l'arabe ; vérifie la ligne `[rag] Configuration : OLLAMA_MODEL=...` au démarrage pour confirmer le bon modèle |
| `Collection ... does not exist` | Plusieurs `streamlit run app.py` tournent en même temps (processus fantôme) | `netstat -ano | findstr :8501` pour trouver le PID, puis `taskkill /PID <pid> /F` ; ne garder qu'**un seul** processus actif |
| Rien ne s'affiche après une question, aucune erreur visible | Le modèle est juste très lent, ou un processus fantôme répond à ta place | Vérifier `[rag] Configuration` au démarrage pour confirmer le bon modèle/timeout ; regarder les logs `[rag] ÉTAPE X/4` dans le terminal pour voir où ça bloque |
| `$env:OLLAMA_MODEL = "..."` donne une erreur de syntaxe | Tu es en fait dans l'Invite de commandes (cmd), pas en PowerShell (le prompt n'affiche pas `PS`) | Ouvrir spécifiquement "Windows PowerShell" depuis le menu Démarrer, ou utiliser `set OLLAMA_MODEL=qwen2.5:3b` en cmd |

## Comment lire les logs de diagnostic

Le terminal où tourne `streamlit run app.py` affiche désormais, pour chaque question :
```
[rag] ===== NOUVELLE QUESTION : '...' =====
[rag] ÉTAPE 0/4 — Langue détectée : fr
[rag] ÉTAPE 1/4 — Début de la recherche vectorielle
[rag] ÉTAPE 1/4 — Recherche terminée en 0.4s
[rag] ÉTAPE 2/4 — Construction du prompt avec le contexte récupéré
[rag] ÉTAPE 3/4 — Envoi de la requête à Ollama (..., modèle=qwen2.5:3b)...
[rag] ÉTAPE 3/4 — Réponse Ollama reçue en 45.2s
[rag] ÉTAPE 4/4 — Vérification de cohérence (2e appel Ollama)...
[rag] ÉTAPE 4/4 — Vérification terminée en 38.1s (cohérent=True)
[rag] ===== QUESTION TERMINÉE =====
```
Si ça bloque quelque part, la dernière ligne affichée indique exactement l'étape en cause.

## Accélérer les réponses (machine lente)

```powershell
$env:SKIP_COHERENCE_CHECK = "1"    # désactive le 2e appel LLM (vérification), divise le temps d'attente par ~2
```

## Comptes de démonstration

| Identifiant | Mot de passe | Rôle |
|---|---|---|
| `employee1` | `conges2026` | employee |
| `rh_admin` | `admin2026` | hr_admin |

## Corpus documentaire (9 documents, 45 chunks)

congés, remboursements, règlement intérieur, contrat de travail, rémunération/avantages,
formation/évaluation, rupture de contrat/discipline, protection des données/éthique, FAQ générale.

## Jeu de test

`data/tests/questions_test.md` — 20 questions couvrant tous les documents + cas limites
(hors sujet, ambiguïté, majuscules, fautes, arabe) pour évaluer objectivement le chatbot.

## Déploiement Docker

```bash
docker compose up --build -d
docker exec -it ollama ollama pull qwen2.5:3b
```
Ouvre http://localhost:8501. Décommente `DATABASE_URL` dans `docker-compose.yml` pour utiliser PostgreSQL au lieu de SQLite.

## Déploiement accessible depuis internet

- **Démo rapide** : `ngrok http 8501` après avoir lancé l'app en local
- **Persistant** : VPS (OVH, DigitalOcean, Hetzner) + `docker compose up --build -d`
- **Streamlit Community Cloud** : héberge l'interface gratuitement, mais Ollama doit tourner sur un serveur séparé (pointer `OLLAMA_URL` vers son adresse publique)
