# Documentation Technique — Assistant IA RAG Fintech

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Pipeline Text-to-SQL](#3-pipeline-text-to-sql)
4. [Base de données](#4-base-de-données)
5. [API interne](#5-api-interne)
6. [Interface utilisateur](#6-interface-utilisateur)
7. [Configuration](#7-configuration)
8. [Tests](#8-tests)
9. [Pipeline CI/CD](#9-pipeline-cicd)
10. [Déploiement Fly.io](#10-déploiement-flyio)
11. [Décisions techniques](#11-décisions-techniques)

---

## 1. Vue d'ensemble

L'application est un chatbot d'analyse financière qui traduit des questions en langage naturel en requêtes SQL, les exécute sur une base PostgreSQL, et reformule les résultats en français. Elle cible la détection de fraude dans le contexte fintech ouest-africain.

**Modèle utilisé :** `anthropic/claude-haiku-4-5` via OpenRouter
**Pattern :** Text-to-SQL (pas de RAG vectoriel — pas de ChromaDB, pas d'embeddings)
**Interface :** Streamlit chat avec historique de session

---

## 2. Architecture

### Schéma global

```
┌─────────────────────────────────────────────────────┐
│                    Utilisateur                      │
└────────────────────────┬────────────────────────────┘
                         │ question (texte libre)
                         ▼
┌─────────────────────────────────────────────────────┐
│              dashboard/app.py (Streamlit)           │
│  - Historique de session (st.session_state)         │
│  - Questions suggérées (sidebar)                    │
│  - Affichage SQL + données brutes (expanders)       │
└────────────────────────┬────────────────────────────┘
                         │ appel repondre(question)
                         ▼
┌─────────────────────────────────────────────────────┐
│               rag/engine.py                         │
│                                                     │
│  generer_sql()  ──► Claude Haiku (OpenRouter)       │
│       │                                             │
│       ▼                                             │
│  executer_sql() ──► PostgreSQL (SQLAlchemy)         │
│       │                                             │
│       ▼                                             │
│  formuler_reponse() ──► Claude Haiku (OpenRouter)   │
│       │                                             │
│       ▼                                             │
│  repondre() → {reponse, sql, resultats, erreur}     │
└─────────────────────────────────────────────────────┘
```

### Composants

| Composant | Fichier | Rôle |
|---|---|---|
| Moteur RAG | `rag/engine.py` | Pipeline Text-to-SQL complet |
| Interface chat | `dashboard/app.py` | UI Streamlit |
| Schéma DB | `init.sql` | DDL + données de test |
| Init production | `scripts/init_db.py` | Init DB idempotent (Fly.io) |

---

## 3. Pipeline Text-to-SQL

Le pipeline enchaîne **deux appels LLM** séquentiels autour d'une exécution SQL.

### Étape 1 — Génération SQL (`generer_sql`)

```
Entrée : question utilisateur (str)
  +
Contexte : constante SCHEMA (schéma DB en texte)

Prompt système :
  "Tu es un expert SQL PostgreSQL. Génère UNIQUEMENT la requête SQL..."
  Règles : LIMIT 20, ROUND(...::numeric, 0) pour les montants

Sortie : requête SQL brute (str, sans backticks ni explication)
```

Le `SCHEMA` est une constante statique dans `rag/engine.py`. C'est le seul contexte que le LLM reçoit sur la base de données — il doit être maintenu à jour manuellement si le schéma change.

### Étape 2 — Exécution SQL (`executer_sql`)

```
Entrée : requête SQL (str)

Exécution via SQLAlchemy + psycopg2
  → conn.execute(text(sql))
  → résultats convertis en list[dict]

Sortie : liste de dictionnaires (colonnes → valeurs)
```

Pas de validation du SQL avant exécution — le LLM est supposé générer du SQL valide. Les erreurs sont capturées par `repondre()`.

### Étape 3 — Formulation de la réponse (`formuler_reponse`)

```
Entrée : question + SQL exécuté + résultats bruts

Prompt système :
  "Tu es un assistant analyste financier pour une fintech africaine.
   Formule une réponse claire, professionnelle et concise en français."

Sortie : réponse en langage naturel (str)
```

### Gestionnaire principal (`repondre`)

```python
def repondre(question: str) -> dict:
    # Retourne toujours les 4 clés, même en cas d'erreur
    {
        "reponse": str,   # texte affiché à l'utilisateur
        "sql":     str,   # requête générée (None si erreur)
        "resultats": list, # données brutes ([] si erreur)
        "erreur":  str,   # message d'erreur (None si succès)
    }
```

Toute exception (LLM indisponible, SQL invalide, DB inaccessible) est capturée et retournée proprement via la clé `erreur`.

---

## 4. Base de données

### Schéma relationnel

```
users
  id (PK)
  nom, email (UNIQUE), pays, telephone, created_at

      │ 1
      │
      ▼ N
comptes
  id (PK)
  user_id (FK → users.id)
  numero (UNIQUE), type_compte, solde, created_at

      │ 1
      │
      ▼ N
transactions
  id (PK)
  compte_id (FK → comptes.id)
  type_tx, montant, pays_origine, pays_destination
  heure (0–23), est_fraude (0/1), score_fraude (0.0–1.0)
  created_at

      │ 1
      │
      ▼ 0..1
alertes_fraude
  id (PK)
  transaction_id (FK → transactions.id)
  niveau ('faible'/'moyen'/'eleve')
  rapport_llm (TEXT), created_at
```

### Contraintes importantes

| Table | Colonne | Contrainte |
|---|---|---|
| `users` | `email` | UNIQUE |
| `comptes` | `numero` | UNIQUE |
| `comptes` | `type_compte` | libre (courant/epargne/mobile) |
| `transactions` | `type_tx` | CHECK IN ('transfert','paiement','retrait','depot') |
| `transactions` | `heure` | CHECK BETWEEN 0 AND 23 |
| `transactions` | `est_fraude` | CHECK IN (0, 1) |
| `alertes_fraude` | `niveau` | CHECK IN ('faible','moyen','eleve') |

### Connexion

En local, le conteneur Docker expose PostgreSQL sur le port **5433** (non standard). En production Fly.io, la variable `DATABASE_URL` est injectée automatiquement par Fly Postgres.

```python
# rag/engine.py
_db_url = os.getenv("DATABASE_URL") or (
    f"postgresql://{os.getenv('DB_USER')}:..."
)
DB_URL = _db_url.replace("postgres://", "postgresql://", 1)
```

La conversion `postgres://` → `postgresql://` est nécessaire car Fly.io injecte le schéma court que SQLAlchemy ne reconnaît pas.

---

## 5. API interne

### `rag/engine.py`

#### `generer_sql(question: str) -> str`

Appelle Claude Haiku avec le prompt SQL. Retourne le SQL brut sans formatage.

#### `executer_sql(sql: str) -> list[dict]`

Exécute la requête via SQLAlchemy. Retourne une liste de dictionnaires `{colonne: valeur}`. Retourne `[]` si aucun résultat.

#### `formuler_reponse(question: str, sql: str, resultats: list) -> str`

Appelle Claude Haiku avec la question, le SQL et les résultats. Retourne une réponse en français.

#### `repondre(question: str) -> dict`

Point d'entrée principal. Enchaîne les 3 fonctions ci-dessus et capture toutes les exceptions.

**Retour :**
```python
{
    "reponse":   str,        # toujours présent
    "sql":       str | None, # None si erreur avant exécution
    "resultats": list,       # [] si erreur
    "erreur":    str | None, # None si succès
}
```

### `dashboard/app.py`

Pas d'API exposée. La Streamlit app gère :
- `st.session_state.messages` — historique complet avec SQL et résultats par message
- `st.session_state.question_auto` — question injectée depuis la sidebar (effacée après traitement)

---

## 6. Interface utilisateur

L'interface est une single-page Streamlit avec deux zones :

**Sidebar :**
- 8 questions suggérées (boutons) qui injectent la question dans le chat
- Stack technique (informatif)

**Zone principale :**
- Historique de conversation (messages user/assistant)
- Chaque réponse assistant inclut deux expanders optionnels :
  - "Voir le SQL généré" → `st.code(sql, language="sql")`
  - "Voir les données brutes" → `st.dataframe(pd.DataFrame(resultats))`

L'historique est conservé en mémoire de session (perdu au rechargement de la page).

---

## 7. Configuration

### Variables d'environnement

| Variable | Obligatoire | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Oui | Clé API OpenRouter |
| `OPENROUTER_BASE_URL` | Oui | `https://openrouter.ai/api/v1` |
| `DATABASE_URL` | Non* | URL complète PostgreSQL (injectée par Fly.io) |
| `DB_HOST` | Non* | Hôte PostgreSQL |
| `DB_PORT` | Non* | Port PostgreSQL (5433 en local) |
| `DB_NAME` | Non* | Nom de la base (`fintech`) |
| `DB_USER` | Non* | Utilisateur PostgreSQL |
| `DB_PASSWORD` | Non* | Mot de passe PostgreSQL |

*`DATABASE_URL` **ou** les variables `DB_*` individuelles sont obligatoires.

### Docker Compose vs local vs Fly.io

| Contexte | DB_HOST | DB_PORT | Source |
|---|---|---|---|
| Local (sans Docker) | `localhost` | `5433` | `.env` |
| Docker Compose (app) | `postgres` | `5432` | `docker-compose.yml` override |
| Fly.io | — | — | `DATABASE_URL` injectée automatiquement |

---

## 8. Tests

### Stratégie

Les tests unitaires dans `tests/test_engine.py` couvrent uniquement `rag/engine.py`. Aucune connexion réelle à la DB ou à l'API LLM n'est requise.

**Technique de mocking :** les dépendances externes (`sqlalchemy.create_engine` et `langchain_openai.ChatOpenAI`) sont patchées **avant l'import du module**, ce qui évite l'initialisation de la connexion DB au chargement :

```python
with patch("sqlalchemy.create_engine"), patch("langchain_openai.ChatOpenAI"):
    import rag.engine as engine_module
```

### Couverture

| Module | Couverture |
|---|---|
| `rag/__init__.py` | 100 % |
| `rag/engine.py` | 83 % |
| **Total** | **83 %** |

Les lignes non couvertes (108–121) correspondent au bloc `if __name__ == "__main__"` — non pertinent pour les tests unitaires.

**Seuil minimum :** 70 % (enforced en CI via `--cov-fail-under=70`).

### Lancer les tests

```bash
make test       # pytest -v
make coverage   # pytest + rapport terminal + HTML dans htmlcov/
```

---

## 9. Pipeline CI/CD

### Vue d'ensemble

```
Push / PR → main
      │
      ▼
┌─────────────┐   ┌─────────────┐
│  CI : lint  │   │  CI : test  │  (parallèles)
│  ruff check │   │  pytest     │
│  ruff format│   │  coverage   │
└──────┬──────┘   └──────┬──────┘
       └────────┬─────────┘
                │ CI succeeded
                ▼
       ┌─────────────────┐
       │ CD : build-push │
       │ Docker → GHCR   │
       └────────┬────────┘
                │ build succeeded
                ▼
       ┌─────────────────┐
       │ CD : deploy     │
       │ flyctl deploy   │
       │ → Fly.io        │
       └─────────────────┘
```

### Workflow CI (`ci.yml`)

**Déclencheurs :** push sur `main`, pull_request vers `main`

| Job | Étapes |
|---|---|
| `lint` | checkout → setup-uv → install deps → `ruff check` → `ruff format --check` |
| `test` | checkout → setup-uv → install deps → `pytest --cov=rag --cov-fail-under=70` |

### Workflow CD (`cd.yml`)

**Déclencheurs :** `workflow_run` (CI complété sur `main`) + releases publiées

| Job | Condition | Étapes |
|---|---|---|
| `build-push` | CI success OU release | checkout → buildx → login GHCR → metadata → build+push |
| `deploy` | `build-push` succeeded | checkout → flyctl → `flyctl deploy --image ghcr.io/...` |

**Tags d'image :**
- `main` — pour chaque push sur la branche main
- `sha-<7chars>` — SHA court du commit
- `v1.2.3`, `v1.2` — sur release publiée

**Secrets requis :**

| Secret | Scope | Valeur |
|---|---|---|
| `GITHUB_TOKEN` | Automatique | Fourni par GitHub Actions |
| `FLY_API_TOKEN` | Repo secret | `fly auth token` |

**Environnement GitHub :** le job `deploy` utilise l'environnement `production` (créer dans GitHub → Settings → Environments).

---

## 10. Déploiement Fly.io

### Configuration (`fly.toml`)

| Paramètre | Valeur | Raison |
|---|---|---|
| `primary_region` | `cdg` (Paris) | Proximité Afrique de l'Ouest |
| `internal_port` | `8502` | Port Streamlit |
| `memory` | `512mb` | LangChain + pandas nécessitent ~300 MB |
| `cpu_kind` | `shared` | Suffisant pour un usage interactif |
| `auto_stop_machines` | `stop` | Économise les ressources hors usage |
| `release_command` | `python scripts/init_db.py` | Init DB avant chaque déploiement |

### Health check

Streamlit expose `/_stcore/health` (HTTP 200 si l'app est prête). Fly.io interroge ce endpoint toutes les 30 secondes avec un délai de grâce de 10 secondes au démarrage.

### Init DB (`scripts/init_db.py`)

Le script est idempotent :
1. Vérifie si la table `users` existe et contient des données
2. Si non → exécute tout `init.sql` (DDL + seed)
3. Si oui → exécute uniquement les statements non-INSERT (DDL, idempotent via `IF NOT EXISTS`)

Le script se connecte via `DATABASE_URL` (Fly Postgres) ou les variables `DB_*` individuelles.

### Procédure de première mise en production

```bash
# 1. Authentification
fly auth login

# 2. Créer l'app
fly apps create rag-fintech

# 3. Base de données
fly postgres create --name rag-fintech-db --region cdg
fly postgres attach rag-fintech-db
# → DATABASE_URL est automatiquement injectée comme secret

# 4. Secrets applicatifs
fly secrets set \
  OPENROUTER_API_KEY=<clé> \
  OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# 5. GitHub — ajouter FLY_API_TOKEN
fly auth token   # copier la valeur
# GitHub → Settings → Secrets → Actions → New secret : FLY_API_TOKEN

# 6. GitHub — créer l'environnement production
# GitHub → Settings → Environments → New environment : production

# 7. Premier déploiement (déclenché automatiquement par le pipeline CD)
# Ou manuellement :
make fly-deploy
```

---

## 11. Décisions techniques

### Pourquoi Text-to-SQL et non RAG vectoriel ?

Les données sont structurées (tables SQL) — un index vectoriel n'apporterait rien. Le LLM génère directement des requêtes SQL précises à partir du schéma, ce qui est plus fiable, plus rapide, et plus transparent (le SQL est affiché à l'utilisateur).

### Pourquoi OpenRouter plutôt que l'API Anthropic directe ?

OpenRouter permet de switcher de modèle sans changer le code (compatibilité API OpenAI). Claude Haiku est choisi pour sa vitesse et son faible coût — adapté à un usage conversationnel en temps réel.

### Pourquoi `uv` plutôt que `pip` / `poetry` ?

`uv` est 10–100× plus rapide que pip pour l'installation de dépendances. Le `uv.lock` garantit la reproductibilité exacte des builds (local, CI, Docker).

### Pourquoi deux appels LLM séquentiels plutôt qu'un seul ?

Séparer la génération SQL de la formulation de la réponse permet de :
- Optimiser chaque prompt indépendamment
- Afficher le SQL généré à l'utilisateur pour la transparence
- Gérer les erreurs SQL indépendamment des erreurs de formulation

### Pourquoi `LIMIT 20` enforced dans le prompt ?

Sans limite, le LLM pourrait générer des requêtes retournant des milliers de lignes, saturant la mémoire Streamlit et ralentissant l'interface. 20 lignes est suffisant pour toutes les questions analytiques typiques.
