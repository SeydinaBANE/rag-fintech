# 🤖 Assistant IA RAG — Fintech Afrique de l'Ouest

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.2+-green?logo=chainlink&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.57+-red?logo=streamlit&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql&logoColor=white)
![Claude Haiku](https://img.shields.io/badge/LLM-Claude%20Haiku-orange?logo=anthropic&logoColor=white)
![License](https://img.shields.io/badge/Licence-MIT-lightgrey)

Chatbot intelligent qui répond à des questions en langage naturel sur des données financières via **Text-to-SQL** et **LLM**. Conçu pour l'analyse de fraude dans le contexte fintech ouest-africain.

---

## 📸 Screenshots

<p align="center">
  <img src="screenshot/interface1.png" width="30%" />
  <img src="screenshot/interface2.png" width="30%" />
  <img src="screenshot/interface3.png" width="30%" />
</p>

---

## 💡 Démonstration

> **Question :** "Quel client a le plus de transactions frauduleuses ?"
>
> **Réponse :** Aminata Traoré enregistre le plus grand nombre de transactions frauduleuses avec 56 fraudes détectées. Audit immédiat recommandé.
>
> **SQL généré automatiquement :**
> ```sql
> SELECT u.id, u.nom, COUNT(t.id) AS nombre_fraudes
> FROM users u
> JOIN comptes c ON u.id = c.user_id
> JOIN transactions t ON c.id = t.compte_id
> WHERE t.est_fraude = 1
> GROUP BY u.id, u.nom
> ORDER BY nombre_fraudes DESC
> LIMIT 1;
> ```

---

## 🏗️ Architecture

```
Question utilisateur
        ↓
LangChain (orchestration)
        ↓
Claude Haiku — génère le SQL
        ↓
PostgreSQL — exécute la requête
        ↓
Claude Haiku — formule la réponse
        ↓
Streamlit Chat UI
```

---

## 🛠️ Stack technique

| Outil | Rôle |
|-------|------|
| [LangChain](https://www.langchain.com/) | Orchestration LLM + outils |
| [Claude Haiku](https://openrouter.ai/) via OpenRouter | Génération SQL + réponses naturelles |
| [PostgreSQL](https://www.postgresql.org/) | Base de données fintech |
| [SQLAlchemy](https://www.sqlalchemy.org/) | Connexion et exécution SQL |
| [Streamlit](https://streamlit.io/) | Interface chat interactive |

---

## ✨ Fonctionnalités

- **Text-to-SQL automatique** — pose une question, le LLM génère le SQL
- **Réponses en langage naturel professionnel** en français
- **Affichage du SQL généré** pour la transparence
- **Questions suggérées** dans la sidebar pour démarrer rapidement
- **Historique de conversation** persistant dans la session
- **Données brutes** accessibles en un clic (tableau interactif)

---

## 💬 Exemples de questions

- "Combien de transactions frauduleuses y a-t-il ?"
- "Quel est le montant total des fraudes ?"
- "Quels pays destination ont le plus de fraudes ?"
- "Quel est le taux de fraude par type de transaction ?"
- "Quelles heures sont les plus risquées ?"
- "Quel client a le solde le plus élevé ?"

---

## 🚀 Lancer le projet

### Prérequis

- [Docker](https://www.docker.com/)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets)
- Clé API [OpenRouter](https://openrouter.ai/)

### 1. Cloner le projet

```bash
git clone https://github.com/SeydinaBANE/projet-rag-fintech.git
cd projet-rag-fintech
```

### 2. Configurer les variables d'environnement

```bash
cp .env.example .env
# Remplis les valeurs dans .env
```

```env
OPENROUTER_API_KEY=ta_clé_api
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DB_HOST=localhost
DB_PORT=5433
DB_NAME=fintech
DB_USER=ton_user
DB_PASSWORD=ton_mot_de_passe
```

### 3. Lancer la base de données PostgreSQL

```bash
docker run --name postgres-fintech \
  -e POSTGRES_USER=ton_user \
  -e POSTGRES_PASSWORD=ton_mot_de_passe \
  -e POSTGRES_DB=fintech \
  -p 5433:5432 \
  -d postgres:15
```

### 4. Installer les dépendances et lancer l'assistant

```bash
uv sync
uv run streamlit run dashboard/app.py --server.port 8502
```

Ouvre [http://localhost:8502](http://localhost:8502)

---

## 📁 Structure du projet

```
projet-rag-fintech/
├── rag/
│   └── engine.py        # Moteur RAG — pipeline Text-to-SQL
├── dashboard/
│   └── app.py           # Interface Streamlit Chat
├── screenshot/          # Captures d'écran de l'interface
├── .env.example         # Modèle de variables d'environnement
├── pyproject.toml       # Dépendances du projet
└── README.md
```

---

## 🌍 Ce qui rend ce projet unique

Ce projet implémente le pattern **Text-to-SQL avec LLM** — une des compétences les plus recherchées en 2026. Au lieu d'écrire des requêtes SQL manuellement, le LLM comprend la question en langage naturel, génère le SQL approprié, exécute la requête et formule une réponse professionnelle. Applicable dans n'importe quel secteur : banque, télécommunications, retail, santé.

---

## 👤 Auteur

**Seydina Mouhamet BANE**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Seydina%20Bane-blue?logo=linkedin)](https://www.linkedin.com/in/seydina-mouhamet-bane-4710931a1)
[![GitHub](https://img.shields.io/badge/GitHub-SeydinaBANE-black?logo=github)](https://github.com/SeydinaBANE)
