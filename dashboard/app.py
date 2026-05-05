import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from rag.engine import repondre

st.set_page_config(
    page_title="Assistant IA Fintech",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Assistant IA Fintech")
st.caption("Posez vos questions en langage naturel sur vos données financières")

# ── QUESTIONS SUGGÉRÉES ──
st.sidebar.header("💡 Questions suggérées")
suggestions = [
    "Combien de transactions frauduleuses y a-t-il ?",
    "Quel client a le plus de transactions frauduleuses ?",
    "Quel est le montant total des fraudes ?",
    "Quels pays destination ont le plus de fraudes ?",
    "Quel est le taux de fraude par type de transaction ?",
    "Quelles heures sont les plus risquées ?",
    "Quel est le solde moyen des comptes ?",
    "Combien de clients viennent du Sénégal ?",
]

for s in suggestions:
    if st.sidebar.button(s, use_container_width=True):
        st.session_state.question_auto = s

st.sidebar.divider()
st.sidebar.markdown("**Stack technique**")
st.sidebar.markdown("- Claude Haiku (OpenRouter)")
st.sidebar.markdown("- LangChain")
st.sidebar.markdown("- PostgreSQL")
st.sidebar.markdown("- Streamlit")

# ── HISTORIQUE ──
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Bonjour ! Je suis votre assistant IA fintech. Posez-moi n'importe quelle question sur vos données de transactions. Par exemple : *'Combien de fraudes ce mois-ci ?'* ou *'Quel client est le plus actif ?'*"
    })

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg and msg["sql"]:
            with st.expander("Voir le SQL généré"):
                st.code(msg["sql"], language="sql")
        if "resultats" in msg and msg["resultats"]:
            with st.expander("Voir les données brutes"):
                import pandas as pd
                st.dataframe(pd.DataFrame(msg["resultats"]))

# ── INPUT ──
question = st.chat_input("Posez votre question...")

if "question_auto" in st.session_state:
    question = st.session_state.question_auto
    del st.session_state.question_auto

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyse en cours..."):
            result = repondre(question)

        st.markdown(result["reponse"])

        if result["sql"]:
            with st.expander("Voir le SQL généré"):
                st.code(result["sql"], language="sql")

        if result["resultats"]:
            with st.expander("Voir les données brutes"):
                import pandas as pd
                st.dataframe(pd.DataFrame(result["resultats"]))

    st.session_state.messages.append({
        "role":      "assistant",
        "content":   result["reponse"],
        "sql":       result["sql"],
        "resultats": result["resultats"]
    })