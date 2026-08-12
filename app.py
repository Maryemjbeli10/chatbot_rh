import uuid
import streamlit as st
from src.rag_engine import answer_question
from src.ingest import build_index, index_is_stale
from src.db import init_db, log_conversation, log_feedback, get_usage_stats
from src.guardrails import scrub_pii
from src.auth import ensure_default_users, verify_login, register_user
from src.background_watcher import start_watcher

# ==========================================================================
# IDENTITÉ — à renseigner quand le nom de la société sera choisi.
# Laisser vide en attendant : l'appli utilise alors un intitulé générique
# ("Espace Collaborateur") partout où le nom apparaîtrait normalement.
# ==========================================================================
APP_NAME = ""
DISPLAY_NAME = APP_NAME if APP_NAME else "Espace Collaborateur"

st.set_page_config(page_title="Assistant Juridique / RH", page_icon="⚖️", layout="wide")

init_db()
ensure_default_users()
start_watcher()

# ==========================================================================
# SYSTÈME DE DESIGN
# Palette "dossier officiel" : papier neutre, encre marine, liseré laiton.
# Serif (Source Serif 4) pour les intitulés qui font autorité, Inter pour
# tout le reste (formulaires, données, interface) où la lisibilité prime.
# ==========================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

:root {
    --sidebar-bg: #FBFBFC;
    --sidebar-border: #E4E6EB;
    --sidebar-text: #2A2D37;
    --sidebar-dim: #8B90A0;
    --sidebar-hover: #F1F3F7;
    --sidebar-active: #E9EEF6;
    --accent: #1F3A5C;
    --accent-hover: #142943;
    --bg-main: #F7F8FA;
    --surface: #FFFFFF;
    --text-main: #14171F;
    --text-secondary: #5B6472;
    --border: #E4E6EB;
    --success: #157A54; --success-bg: #E4F5EC;
    --amber: #91600B; --amber-bg: #FCF0DC;
    --danger: #B0271E; --danger-bg: #FBEAE8;

    /* Palette dédiée à l'authentification — claire, cohérente avec le reste
       de l'appli, avec le même accent vif cyan/violet qu'en version sombre. */
    --auth-bg: #F6F8FB;
    --auth-surface: #FFFFFF;
    --auth-surface-2: #EEF2F8;
    --auth-ink: #14171F;
    --auth-ink-soft: #5B6472;
    --auth-line: #E1E5EC;
    --auth-cyan: #0EA5E9;
    --auth-cyan-text: #0369A1;
    --auth-violet: #7C6FE0;
    --auth-glow: rgba(14, 165, 233, 0.10);
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text-main); }
.stApp { background: var(--bg-main); }
section[data-testid="stSidebar"] {
    background: var(--sidebar-bg) !important;
    border-right: 1px solid var(--sidebar-border);
}
section[data-testid="stSidebar"] .stButton > button {
    background: transparent; border: 1px solid transparent; text-align: left;
    font-size: 13.5px; font-weight: 500; border-radius: 8px; color: var(--sidebar-text);
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--sidebar-hover) !important; border-color: var(--sidebar-hover) !important;
    color: var(--sidebar-text) !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: var(--sidebar-active) !important; border-color: var(--sidebar-active) !important;
    color: var(--accent) !important; font-weight: 600 !important;
}

.new-chat-btn button {
    background: var(--accent) !important; border-color: var(--accent) !important;
    color: #FFFFFF !important; font-weight: 600 !important;
}
.new-chat-btn button:hover { background: var(--accent-hover) !important; border-color: var(--accent-hover) !important; }

.badge { display:inline-flex; align-items:center; gap:5px; padding: 3px 10px; border-radius: 100px;
         font-size: 11.5px; font-weight: 600; margin-right:7px; }
.badge-success { background: var(--success-bg); color: var(--success); }
.badge-amber   { background: var(--amber-bg); color: var(--amber); }
.badge-danger  { background: var(--danger-bg); color: var(--danger); }
.badge-accent  { background: var(--sidebar-active); color: var(--accent); }

.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px; text-align: center; }
.stat-num { font-size: 19px; font-weight: 700; margin:0; color: var(--accent); }
.stat-label { font-size: 10px; color: var(--text-secondary); margin:0; text-transform: uppercase; letter-spacing: 0.3px; }

.main-header { font-size: 15px; font-weight: 600; color: var(--text-main); padding: 4px 0 18px; }

/* ==========================================================================
   PAGE D'AUTHENTIFICATION — fond sombre, accent vif, ambiance "console d'accès"
   Deux colonnes : à gauche l'argument de valeur, à droite le formulaire.
   ========================================================================== */
.stApp:has(.auth-wrap) {
    background:
        linear-gradient(rgba(20,23,31,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(20,23,31,0.025) 1px, transparent 1px),
        radial-gradient(circle at 15% 10%, var(--auth-glow), transparent 55%),
        var(--auth-bg);
    background-size: 34px 34px, 34px 34px, 100% 100%, 100%;
}

.auth-wrap { padding-top: 44px; }

.access-badge {
    width: 50px; height: 50px; border-radius: 12px;
    background: var(--auth-surface-2); border: 1px solid var(--auth-line);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; margin-bottom: 22px; color: var(--auth-cyan-text);
    box-shadow: 0 0 0 1px rgba(14,165,233,0.10), 0 0 18px rgba(14,165,233,0.10);
}
.auth-eyebrow {
    font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;
    letter-spacing: 1px; color: var(--auth-cyan-text); margin: 0 0 14px;
}
.brand-title {
    font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 33px;
    line-height: 1.25; color: var(--auth-ink); margin: 0 0 14px; max-width: 430px;
}
.brand-title em { font-style: normal; color: var(--auth-cyan-text); }
.brand-sub {
    font-size: 14.5px; line-height: 1.65; color: var(--auth-ink-soft);
    max-width: 390px; margin: 0 0 32px;
}
.feature-row { display: flex; gap: 12px; align-items: flex-start; max-width: 390px; margin-bottom: 18px; }
.feature-icon {
    flex-shrink: 0; width: 27px; height: 27px; border-radius: 8px;
    background: var(--auth-surface-2); border: 1px solid var(--auth-line); color: var(--auth-cyan-text);
    display: flex; align-items: center; justify-content: center; font-size: 13px; margin-top: 1px;
}
.feature-text b { display: block; font-size: 13px; font-weight: 600; color: var(--auth-ink); margin-bottom: 2px; }
.feature-text span { font-size: 12.5px; color: var(--auth-ink-soft); line-height: 1.55; }

.auth-card-title {
    font-family: 'Space Grotesk', sans-serif; font-size: 14px; font-weight: 600;
    color: var(--auth-ink); margin: 4px 0 18px;
}
.auth-footnote {
    display: flex; align-items: center; justify-content: center; gap: 6px;
    text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--auth-ink-soft); margin-top: 20px; letter-spacing: 0.2px;
}

/* La carte de connexion : on stylise directement la colonne qui la contient
   (3ᵉ des 4 colonnes : marge / argumentaire / carte / marge). stColumn et
   stHorizontalBlock sont des testids de structure présents depuis longtemps
   dans Streamlit — bien plus fiables qu'un wrapper interne de bordure ou
   qu'une div non fermée (que le moteur de rendu de st.markdown referme tout
   seul, élément par élément). */
.stApp:has(.auth-wrap) div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(3) {
    background: var(--auth-surface) !important; border: 1px solid var(--auth-line) !important;
    border-radius: 16px !important; box-shadow: 0 1px 2px rgba(20,23,31,0.04), 0 20px 44px rgba(20,23,31,0.08) !important;
    padding: 22px 26px 4px !important;
}

/* Onglets Se connecter / Créer un compte — soulignement, ambiance console */
.stTabs [data-baseweb="tab-list"] { gap: 22px; background: transparent; border-bottom: 1px solid var(--auth-line); }
.stTabs [data-baseweb="tab"] {
    background: transparent; border: none; padding: 8px 2px 12px;
    font-size: 13.5px; font-weight: 600; color: var(--auth-ink-soft);
}
.stTabs [aria-selected="true"] { color: var(--auth-cyan-text) !important; }
.stTabs [data-baseweb="tab-highlight"] { background: linear-gradient(90deg, var(--auth-cyan), var(--auth-violet)) !important; height: 2px !important; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* Champs de formulaire */
.stTextInput label, .stSelectbox label {
    font-family: 'JetBrains Mono', monospace; font-size: 10.5px !important; font-weight: 600 !important;
    color: var(--auth-ink-soft) !important; text-transform: uppercase; letter-spacing: 0.5px;
}
.stTextInput input, .stSelectbox [data-baseweb="select"] > div {
    background: var(--auth-surface-2) !important; border: 1px solid var(--auth-line) !important;
    border-radius: 8px !important; color: var(--auth-ink) !important;
}
.stTextInput input:focus {
    border-color: var(--auth-cyan) !important; box-shadow: 0 0 0 1px var(--auth-cyan) !important;
}
.stTextInput input::placeholder { color: var(--auth-ink-soft) !important; }
div[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(90deg, var(--auth-cyan), var(--auth-violet)) !important;
    border: none !important; color: #FFFFFF !important; font-weight: 700 !important; border-radius: 8px !important;
    box-shadow: 0 8px 20px rgba(14,165,233,0.25) !important;
}
div[data-testid="stFormSubmitButton"] button:hover { filter: brightness(1.06); }
div[data-testid="stFormSubmitButton"] button p { color: #FFFFFF !important; }
.stApp:has(.auth-wrap) .stCaption, .stApp:has(.auth-wrap) [data-testid="stCaptionContainer"] {
    color: var(--auth-ink-soft) !important;
}
.stApp:has(.auth-wrap) .stCaption code, .stApp:has(.auth-wrap) [data-testid="stCaptionContainer"] code {
    background: var(--auth-surface-2) !important; color: var(--auth-cyan-text) !important; border: 1px solid var(--auth-line) !important;
}
</style>
""", unsafe_allow_html=True)

if "index_checked" not in st.session_state:
    if index_is_stale():
        with st.spinner("Mise à jour de l'index documentaire..."):
            build_index(verbose=False)
    st.session_state.index_checked = True


# ==========================================================================
# PAGE D'ACCUEIL — connexion / inscription
# ==========================================================================
def render_auth_home():
    st.markdown('<div class="auth-wrap">', unsafe_allow_html=True)

    spacer_l, col_brand, col_card, spacer_r = st.columns([0.3, 3, 2.7, 0.3])

    with col_brand:
        st.markdown('<div class="access-badge">🔒</div>', unsafe_allow_html=True)
        st.markdown('<p class="auth-eyebrow">[ ACCÈS CHIFFRÉ ]</p>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="brand-title">Les réponses RH et juridiques de {DISPLAY_NAME}, '
            f'<em>sourcées</em> dans vos documents internes.</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="brand-sub">Congés, remboursements, contrat, salaire, formation : pose ta question, '
            'obtiens une réponse appuyée sur les documents de référence — jamais une supposition.</p>',
            unsafe_allow_html=True,
        )

        features = [
            ("📎", "Réponses sourcées", "Chaque réponse cite le document interne dont elle provient."),
            ("🕓", "Historique conservé", "Reprends une conversation là où tu l'avais laissée."),
            ("🛡️", "Données protégées", "Les informations personnelles sont masquées avant tout traitement."),
        ]
        for icon, title, desc in features:
            st.markdown(
                f'<div class="feature-row">'
                f'<div class="feature-icon">{icon}</div>'
                f'<div class="feature-text"><b>{title}</b><span>{desc}</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_card:
        tab_login, tab_signup = st.tabs(["Se connecter", "Créer un compte"])

        with tab_login:
            st.markdown('<p class="auth-card-title">Connexion à ton espace</p>', unsafe_allow_html=True)
            with st.form("login_form"):
                username = st.text_input("Identifiant")
                password = st.text_input("Mot de passe", type="password")
                submitted = st.form_submit_button("Se connecter", type="primary", use_container_width=True)
                if submitted:
                    profile = verify_login(username.strip(), password)
                    if profile:
                        st.session_state.user_id = profile["username"]
                        st.session_state.role = profile["role"]
                        st.session_state.department = profile["department"]
                        st.session_state.full_name = profile["full_name"]
                        st.rerun()
                    else:
                        st.error("Identifiant ou mot de passe incorrect.")
            

        with tab_signup:
            st.markdown('<p class="auth-card-title">Créer un compte collaborateur</p>', unsafe_allow_html=True)
            with st.form("signup_form"):
                su_full_name = st.text_input("Nom complet")
                su_username = st.text_input("Identifiant souhaité")
                su_department = st.selectbox("Département", ["IT", "RH", "Finance", "Marketing", "Opérations", "Autre"])
                su_password = st.text_input("Mot de passe", type="password", help="8 caractères minimum")
                su_confirm = st.text_input("Confirmer le mot de passe", type="password")
                su_submitted = st.form_submit_button("Créer mon compte", type="primary", use_container_width=True)
                if su_submitted:
                    ok, err = register_user(su_username, su_password, su_confirm, su_full_name, su_department)
                    if ok:
                        st.success("Compte créé. Connecte-toi dans l'onglet « Se connecter ».")
                    else:
                        st.error(err)

        st.markdown(
            '<p class="auth-footnote">🔒 Accès réservé aux collaborateurs autorisés</p>',
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)


if "user_id" not in st.session_state:
    render_auth_home()
    st.stop()


# ==========================================================================
# GESTION MULTI-CONVERSATIONS (comme Claude / ChatGPT)
# ==========================================================================
def new_chat_id():
    return str(uuid.uuid4())


if "chats" not in st.session_state:
    first_id = new_chat_id()
    st.session_state.chats = {first_id: {"title": "Nouvelle conversation", "history": [], "display": []}}
    st.session_state.current_chat_id = first_id
if "page" not in st.session_state:
    st.session_state.page = "Chat"

current = st.session_state.chats[st.session_state.current_chat_id]


# ==========================================================================
# SIDEBAR
# ==========================================================================
with st.sidebar:
    st.markdown(f"### ⚖️ {DISPLAY_NAME}")
    st.caption("Assistant Juridique / RH")
    st.write("")

    st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
    if st.button("＋  Nouvelle conversation", use_container_width=True):
        # Comme Claude/ChatGPT : si la conversation actuelle est déjà vide, on reste
        # dessus plutôt que d'empiler des conversations vides inutiles dans la liste.
        current_is_empty = not st.session_state.chats[st.session_state.current_chat_id]["display"]
        if not current_is_empty:
            cid = new_chat_id()
            st.session_state.chats[cid] = {"title": "Nouvelle conversation", "history": [], "display": []}
            st.session_state.current_chat_id = cid
        st.session_state.page = "Chat"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    st.caption("CONVERSATIONS")
    # Seules les conversations ayant au moins un échange apparaissent dans la liste —
    # une conversation vide n'est qu'un état transitoire, pas encore "une conversation".
    non_empty_chats = [cid for cid in st.session_state.chats if st.session_state.chats[cid]["display"]]
    for cid in reversed(non_empty_chats):
        chat = st.session_state.chats[cid]
        is_active = cid == st.session_state.current_chat_id and st.session_state.page == "Chat"
        if st.button(chat["title"], key=f"chat_{cid}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state.current_chat_id = cid
            st.session_state.page = "Chat"
            st.rerun()
    if not non_empty_chats:
        st.caption("Aucune conversation pour l'instant.")

    st.write("")
    st.divider()
    if st.button("Statistiques", key="nav_Statistiques", use_container_width=True,
                 type="primary" if st.session_state.page == "Statistiques" else "secondary"):
        st.session_state.page = "Statistiques"
        st.rerun()

    st.divider()
    if index_is_stale():
        st.markdown('<span class="badge badge-amber">⚠ Documents modifiés</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-success">✓ Documents à jour</span>', unsafe_allow_html=True)

    stats = get_usage_stats()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="stat-card"><p class="stat-num">{stats["total_questions"]}</p><p class="stat-label">Questions</p></div>', unsafe_allow_html=True)
    with c2:
        sat = stats["satisfaction"]
        sat_display = f'{sat}%' if sat is not None else "—"
        st.markdown(f'<div class="stat-card"><p class="stat-num">{sat_display}</p><p class="stat-label">Satisfaction</p></div>', unsafe_allow_html=True)

    st.write("")
    if st.button("🔄 Ré-indexer les documents", use_container_width=True):
        with st.spinner("Ré-indexation..."):
            build_index(verbose=False)
        st.success("Index mis à jour !")
        st.rerun()

    st.write("")
    st.caption(f"{st.session_state.get('full_name', st.session_state.user_id)} · {st.session_state.get('department', '')}")
    if st.button("🚪 Déconnexion", use_container_width=True):
        for key in ["user_id", "role", "department", "full_name", "chats", "current_chat_id", "page"]:
            st.session_state.pop(key, None)
        st.rerun()


# ==========================================================================
# ZONE PRINCIPALE
# ==========================================================================
if st.session_state.page == "Chat":
    current = st.session_state.chats[st.session_state.current_chat_id]

    st.markdown(
        '<div class="main-header">'
        '<span class="badge badge-success">🔒 Sécurisé</span>'
        '<span class="badge badge-accent">🧠 Mémoire ON</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not current["display"]:
        st.markdown(
            "<div style='text-align:center; padding: 60px 0 30px; color: var(--text-secondary);'>"
            "<div style='font-size:36px; margin-bottom:10px;'>⚖️</div>"
            "<p style='font-size:15px;'>Pose une question sur les congés, remboursements, contrat, salaire, formation...</p>"
            "</div>", unsafe_allow_html=True,
        )

    for i, turn in enumerate(current["display"]):
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            st.write(turn["answer"])
            if turn["sources"]:
                st.caption("📎 Sources : " + ", ".join(turn["sources"]))
            conf = turn["confidence"]
            badge_class = {"haute": "badge-success", "moyenne": "badge-amber", "faible": "badge-danger"}[conf]
            verified_badge = '<span class="badge badge-accent">✓ Vérifié</span>' if turn.get("coherent", True) else '<span class="badge badge-danger">⚠ Non vérifié</span>'
            st.markdown(f'<span class="badge {badge_class}">Confiance : {conf}</span>{verified_badge}', unsafe_allow_html=True)

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("👍 Utile", key=f"up_{st.session_state.current_chat_id}_{i}"):
                    log_feedback(turn["conv_id"], "positive")
                    st.toast("Merci pour votre retour !")
            with col2:
                if st.button("👎 Pas utile", key=f"down_{st.session_state.current_chat_id}_{i}"):
                    log_feedback(turn["conv_id"], "negative")
                    st.toast("Merci, nous allons améliorer la réponse.")

    question = st.chat_input("Posez votre question (congés, remboursements, règlement...)")

    if question:
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            try:
                with st.spinner("Recherche dans les documents... (peut prendre jusqu'à quelques minutes selon ta machine)"):
                    result = answer_question(question, history=current["history"])
                st.write(result["answer"])
                if result["sources"]:
                    st.caption("📎 Sources : " + ", ".join(result["sources"]))
            except Exception as e:
                import traceback
                st.error(f"⚠️ Erreur pendant le traitement de la question : {e}")
                with st.expander("Détails techniques"):
                    st.code(traceback.format_exc())
                st.stop()

        conv_id = log_conversation(
            st.session_state.user_id,
            scrub_pii(question),
            scrub_pii(result["answer"]),
            result["sources"], result["confidence"], result["language"],
        )

        # Titre automatique de la conversation à partir de la première question
        if current["title"] == "Nouvelle conversation":
            current["title"] = (question[:35] + "…") if len(question) > 35 else question

        current["history"].append({"role": "user", "content": question})
        current["history"].append({"role": "assistant", "content": result["answer"]})
        current["history"] = current["history"][-6:]

        current["display"].append({
            "question": question, "answer": result["answer"], "sources": result["sources"],
            "confidence": result["confidence"], "coherent": result.get("coherent", True),
            "conv_id": conv_id,
        })
        st.rerun()

elif st.session_state.page == "Statistiques":
    st.subheader("Statistiques d'usage")
    stats = get_usage_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Questions posées", stats["total_questions"])
    sat = stats["satisfaction"]
    c2.metric("Taux de satisfaction", f'{sat}%' if sat is not None else "—")
    c3.metric("Documents indexés", 9)

    st.write("**Répartition par document source**")
    if stats["by_source"]:
        st.bar_chart(stats["by_source"])
    else:
        st.caption("Pas encore de données.")

    st.write("**Répartition par niveau de confiance**")
    if stats["by_confidence"]:
        st.bar_chart(stats["by_confidence"])
    else:
        st.caption("Pas encore de données.")