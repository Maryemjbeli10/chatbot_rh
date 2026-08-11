import streamlit as st
from src.rag_engine import answer_question
from src.ingest import build_index, index_is_stale
from src.db import init_db, log_conversation, log_feedback, get_history, get_usage_stats
from src.guardrails import scrub_pii
from src.auth import ensure_default_users, verify_login
from src.background_watcher import start_watcher

st.set_page_config(page_title="Assistant Juridique / RH", page_icon="⚖️", layout="wide")

init_db()
ensure_default_users()
start_watcher()

st.markdown("""
<style>
.header-banner {
    background: linear-gradient(90deg, #6D5BD0 0%, #4E7FE0 100%);
    border-radius: 16px; padding: 20px 28px;
    display: flex; align-items: center; gap: 16px; margin-bottom: 20px;
}
.header-banner .icon-box {
    width: 52px; height: 52px; border-radius: 12px;
    background: rgba(255,255,255,0.18);
    display: flex; align-items: center; justify-content: center; font-size: 26px;
}
.header-banner h1 { color: white; font-size: 22px; margin: 0; font-weight: 600; }
.header-banner p { color: rgba(255,255,255,0.85); font-size: 13px; margin: 2px 0 0; }
.badge { display:inline-block; padding: 3px 10px; border-radius: 8px; font-size: 11px; font-weight: 600; margin-right:6px;}
.badge-green { background:#E1F5EE; color:#0F6E56; }
.badge-purple { background:#EEEDFE; color:#3C3489; }
.badge-amber { background:#FAEEDA; color:#854F0B; }
.badge-red { background:#FCEBEB; color:#791F1F; }
.stat-card { background:#F7F7FA; border-radius:12px; padding:10px 14px; text-align:center; }
.stat-num { font-size:20px; font-weight:700; margin:0; }
.stat-label { font-size:11px; color:#666; margin:0; }
</style>
""", unsafe_allow_html=True)

if "index_checked" not in st.session_state:
    if index_is_stale():
        with st.spinner("Mise à jour de l'index documentaire..."):
            build_index(verbose=False)
    st.session_state.index_checked = True

if "user_id" not in st.session_state:
    st.markdown("""
    <div class="header-banner">
        <div class="icon-box">⚖️</div>
        <div><h1>Assistant Juridique / RH</h1><p>NovaTech Solutions — v2.0</p></div>
    </div>
    """, unsafe_allow_html=True)
    with st.form("login"):
        username = st.text_input("Identifiant employé")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter")
        if submitted:
            profile = verify_login(username.strip(), password)
            if profile:
                st.session_state.user_id = profile["username"]
                st.session_state.role = profile["role"]
                st.session_state.department = profile["department"]
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")
    st.caption("Comptes de démo : `employee1` / `conges2026` — ou `rh_admin` / `admin2026`")
    st.stop()

if "history" not in st.session_state:
    st.session_state.history = []
if "chat_display" not in st.session_state:
    st.session_state.chat_display = []
if "page" not in st.session_state:
    st.session_state.page = "Chat"

st.markdown("""
<div class="header-banner">
    <div class="icon-box">⚖️</div>
    <div><h1>Assistant Juridique / RH</h1><p>NovaTech Solutions — v2.0</p></div>
</div>
""", unsafe_allow_html=True)

col_side, col_main = st.columns([1, 3])

with col_side:
    st.markdown(f"**👤 {st.session_state.user_id}**")
    st.caption(f"{st.session_state.get('department', '')} · {st.session_state.get('role', 'employee')}")
    st.divider()

    st.markdown("**📍 Navigation**")
    for label in ["Chat", "Historique", "Statistiques"]:
        if st.button(label, key=f"nav_{label}", use_container_width=True,
                     type="primary" if st.session_state.page == label else "secondary"):
            st.session_state.page = label
            st.rerun()

    st.divider()
    if index_is_stale():
        st.markdown('<span class="badge badge-amber">⚠ Documents modifiés</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-green">✓ Documents à jour</span>', unsafe_allow_html=True)
        st.caption("Aucun changement détecté")

    stats = get_usage_stats()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="stat-card"><p class="stat-num" style="color:#0F6E56">{stats["total_questions"]}</p><p class="stat-label">Questions</p></div>', unsafe_allow_html=True)
    with c2:
        sat = stats["satisfaction"]
        sat_display = f'{sat}%' if sat is not None else "—"
        st.markdown(f'<div class="stat-card"><p class="stat-num" style="color:#3C3489">{sat_display}</p><p class="stat-label">Satisfaction</p></div>', unsafe_allow_html=True)

    if st.button("🔄 Forcer la ré-indexation", use_container_width=True):
        with st.spinner("Ré-indexation..."):
            build_index(verbose=False)
        st.success("Index mis à jour !")
        st.rerun()

with col_main:
    if st.session_state.page == "Chat":
        st.markdown(
            '<span class="badge badge-green">🔒 Sécurisé</span>'
            '<span class="badge badge-purple">🧠 Mémoire ON</span>',
            unsafe_allow_html=True,
        )
        st.write("")

        for i, turn in enumerate(st.session_state.chat_display):
            with st.chat_message("user"):
                st.write(turn["question"])
            with st.chat_message("assistant"):
                st.write(turn["answer"])
                if turn["sources"]:
                    st.caption("📎 Sources : " + ", ".join(turn["sources"]))
                conf = turn["confidence"]
                badge_class = {"haute": "badge-green", "moyenne": "badge-amber", "faible": "badge-red"}[conf]
                verified_badge = '<span class="badge badge-purple">✓ Vérifié</span>' if turn.get("coherent", True) else '<span class="badge badge-red">⚠ Non vérifié</span>'
                st.markdown(f'<span class="badge {badge_class}">Confiance : {conf}</span>{verified_badge}', unsafe_allow_html=True)

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("👍 Utile", key=f"up_{i}"):
                        log_feedback(turn["conv_id"], "positive")
                        st.toast("Merci pour votre retour !")
                with col2:
                    if st.button("👎 Pas utile", key=f"down_{i}"):
                        log_feedback(turn["conv_id"], "negative")
                        st.toast("Merci, nous allons améliorer la réponse.")

        question = st.chat_input("Posez votre question (congés, remboursements, règlement...)")

        if question:
            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):
                try:
                    with st.spinner("Recherche dans les documents... (peut prendre jusqu'à quelques minutes selon ta machine)"):
                        result = answer_question(question, history=st.session_state.history)
                    st.write(result["answer"])
                    if result["sources"]:
                        st.caption("📎 Sources : " + ", ".join(result["sources"]))
                except Exception as e:
                    import traceback
                    st.error(f"⚠️ Erreur pendant le traitement de la question : {e}")
                    with st.expander("Détails techniques (à copier si tu demandes de l'aide)"):
                        st.code(traceback.format_exc())
                    st.stop()

            conv_id = log_conversation(
                st.session_state.user_id,
                scrub_pii(question),
                scrub_pii(result["answer"]),
                result["sources"], result["confidence"], result["language"],
            )

            st.session_state.history.append({"role": "user", "content": question})
            st.session_state.history.append({"role": "assistant", "content": result["answer"]})
            st.session_state.history = st.session_state.history[-6:]

            st.session_state.chat_display.append({
                "question": question, "answer": result["answer"], "sources": result["sources"],
                "confidence": result["confidence"], "coherent": result.get("coherent", True),
                "conv_id": conv_id,
            })
            st.rerun()

    elif st.session_state.page == "Historique":
        st.subheader("🕘 Historique des échanges")
        rows = get_history(st.session_state.user_id, limit=100)
        if not rows:
            st.info("Aucun échange pour l'instant.")
        for row in rows:
            with st.expander(f"{row['timestamp'][:19]} — {row['question'][:60]}"):
                st.write(f"**Question :** {row['question']}")
                st.write(f"**Réponse :** {row['answer']}")
                st.caption(f"Sources : {row['sources'] or '—'} · Confiance : {row['confidence']} · Langue : {row['language']}")

    elif st.session_state.page == "Statistiques":
        st.subheader("📊 Statistiques d'usage")
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
