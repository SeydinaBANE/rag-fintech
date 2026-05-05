# CLAUDE.md

Ce fichier fournit des instructions à Claude Code (claude.ai/code) pour travailler dans ce dépôt.

## Commandes

```bash
# Lancer l'application
uv run streamlit run dashboard/app.py --server.port 8502
# Ouvrir http://localhost:8502

# Installer les dépendances
uv sync

```

PostgreSQL tourne sur le port 5433 (non standard). Nécessite Docker avec le conteneur `postgres-fintech` en cours d'exécution.

## Architecture

Pipeline LLM en 3 étapes orchestré par LangChain :

```
Question utilisateur → Claude Haiku (génération SQL) → Exécution PostgreSQL → Claude Haiku (réponse en français) → Interface Streamlit
```

**Fichiers clés :**
- `rag/engine.py` — Moteur RAG principal. `repondre(question)` est le point d'entrée qui enchaîne `generer_sql()` → `executer_sql()` → `formuler_reponse()`. Tous les appels LLM utilisent Claude Haiku via OpenRouter.
- `dashboard/app.py` — Interface chat Streamlit. Gère l'état de session pour l'historique des messages, affiche le SQL généré et les données brutes dans des sections dépliables.

## Schéma de la base de données (PostgreSQL, db : fintech)

- `users` — id, nom, email, pays, telephone, created_at
- `comptes` — id, user_id, numero, type_compte, solde, created_at
- `transactions` — id, compte_id, type_tx, montant, pays_origine, pays_destination, heure, est_fraude, score_fraude, created_at
- `alertes_fraude` — id, transaction_id, niveau, rapport_llm, created_at

## Variables d'environnement

Requises dans `.env` :
```
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DB_HOST=localhost
DB_PORT=5433
DB_NAME=fintech
DB_USER=
DB_PASSWORD=
```

## Notes

- Toutes les réponses LLM sont en français — les prompts dans `rag/engine.py` sont rédigés en français.
- `chromadb` est listé comme dépendance mais n'est utilisé dans aucun fichier source.
- Le fichier `.env` doit être ajouté au `.gitignore` pour éviter de committer des secrets.
