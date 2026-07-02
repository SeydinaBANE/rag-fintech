import os
import time

import pandas as pd
import streamlit as st

from rag.engine import repondre

MAX_TENTATIVES_CONNEXION = 5
DUREE_BLOCAGE_S = 60


def _afficher_sql_resultats(sql, resultats):
    if sql:
        with st.expander("Voir le SQL généré"):
            st.code(sql, language="sql")
    if resultats:
        with st.expander("Voir les données brutes"):
            st.dataframe(pd.DataFrame(resultats))


def _authentifie() -> bool:
    mot_de_passe_attendu = os.getenv("DASHBOARD_PASSWORD")
    if not mot_de_passe_attendu:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.session_state.setdefault("tentatives_connexion", 0)
    st.session_state.setdefault("blocage_jusqu_a", 0.0)

    st.title("🔒 Connexion requise")

    if time.time() < st.session_state["blocage_jusqu_a"]:
        restant = int(st.session_state["blocage_jusqu_a"] - time.time())
        st.error(f"Trop de tentatives. Réessayez dans {restant}s.")
        return False

    mot_de_passe = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if mot_de_passe == mot_de_passe_attendu:
            st.session_state["authenticated"] = True
            st.session_state["tentatives_connexion"] = 0
            st.rerun()
        else:
            st.session_state["tentatives_connexion"] += 1
            if st.session_state["tentatives_connexion"] >= MAX_TENTATIVES_CONNEXION:
                st.session_state["blocage_jusqu_a"] = time.time() + DUREE_BLOCAGE_S
                st.session_state["tentatives_connexion"] = 0
            st.error("Mot de passe incorrect.")
    return False


st.set_page_config(page_title="Assistant IA Fintech", page_icon="🤖", layout="wide")

if not _authentifie():
    st.stop()

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
st.sidebar.caption("🤖 Propulsé par IA")

# ── HISTORIQUE ──
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": "Bonjour ! Je suis votre assistant IA fintech. Posez-moi n'importe quelle question sur vos données de transactions. Par exemple : *'Combien de fraudes ce mois-ci ?'* ou *'Quel client est le plus actif ?'*",
        }
    )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        _afficher_sql_resultats(msg.get("sql"), msg.get("resultats"))

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
        _afficher_sql_resultats(result["sql"], result["resultats"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["reponse"],
            "sql": result["sql"],
            "resultats": result["resultats"],
        }
    )
