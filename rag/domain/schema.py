SCHEMA = """
Base de données fintech PostgreSQL. Tables disponibles :

1. users (id, nom, email, pays, telephone, created_at)
2. comptes (id, user_id, numero, type_compte, solde, created_at)
3. transactions (id, compte_id, type_tx, montant, pays_origine, pays_destination, heure, est_fraude, score_fraude, created_at)
4. alertes_fraude (id, transaction_id, niveau, rapport_llm, created_at)

Relations :
- comptes.user_id → users.id
- transactions.compte_id → comptes.id
- alertes_fraude.transaction_id → transactions.id

Valeurs importantes :
- est_fraude : 0 = normal, 1 = fraude
- type_tx : transfert, paiement, retrait, depot
- heure : 0-23
"""
