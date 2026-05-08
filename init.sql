-- Schéma de la base de données fintech

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    pays VARCHAR(50),
    telephone VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comptes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    numero VARCHAR(20) UNIQUE NOT NULL,
    type_compte VARCHAR(30),
    solde NUMERIC(15, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    compte_id INTEGER REFERENCES comptes(id),
    type_tx VARCHAR(20) CHECK (type_tx IN ('transfert', 'paiement', 'retrait', 'depot')),
    montant NUMERIC(15, 2) NOT NULL,
    pays_origine VARCHAR(50),
    pays_destination VARCHAR(50),
    heure INTEGER CHECK (heure BETWEEN 0 AND 23),
    est_fraude SMALLINT DEFAULT 0 CHECK (est_fraude IN (0, 1)),
    score_fraude NUMERIC(5, 4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alertes_fraude (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER REFERENCES transactions(id),
    niveau VARCHAR(20) CHECK (niveau IN ('faible', 'moyen', 'eleve')),
    rapport_llm TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Données de test
INSERT INTO users (nom, email, pays, telephone) VALUES
('Moussa Diallo',    'moussa.diallo@email.sn',   'Sénégal',      '+221771234567'),
('Aminata Traoré',  'aminata.traore@email.ml',   'Mali',         '+22376543210'),
('Kofi Mensah',     'kofi.mensah@email.gh',      'Ghana',        '+23324567890'),
('Fatou Balde',     'fatou.balde@email.gn',      'Guinée',       '+224621234567'),
('Ibrahim Coulibaly','ibrahim.c@email.ci',        'Côte d''Ivoire','+22507654321'),
('Aïssatou Sow',    'aissatou.sow@email.sn',     'Sénégal',      '+221789876543'),
('Cheikh Ndiaye',   'cheikh.ndiaye@email.sn',    'Sénégal',      '+221771122334'),
('Mariama Barry',   'mariama.barry@email.gn',    'Guinée',       '+224631234567');

INSERT INTO comptes (user_id, numero, type_compte, solde) VALUES
(1, 'SN001001', 'courant',  250000),
(2, 'ML002001', 'epargne',   80000),
(3, 'GH003001', 'courant',  520000),
(4, 'GN004001', 'mobile',    15000),
(5, 'CI005001', 'courant',  370000),
(6, 'SN006001', 'epargne',  130000),
(7, 'SN007001', 'courant',   45000),
(8, 'GN008001', 'mobile',     8000);

INSERT INTO transactions (compte_id, type_tx, montant, pays_origine, pays_destination, heure, est_fraude, score_fraude) VALUES
(1, 'transfert',  50000, 'Sénégal',       'Mali',           14, 0, 0.05),
(1, 'transfert', 980000, 'Sénégal',       'Nigéria',         2, 1, 0.97),
(2, 'paiement',   12000, 'Mali',          'Mali',           10, 0, 0.02),
(3, 'retrait',    75000, 'Ghana',         'Ghana',           9, 0, 0.03),
(3, 'transfert', 500000, 'Ghana',         'Chine',           3, 1, 0.95),
(4, 'depot',       5000, 'Guinée',        'Guinée',         11, 0, 0.01),
(5, 'paiement',   30000, 'Côte d''Ivoire','Côte d''Ivoire', 15, 0, 0.04),
(5, 'transfert', 850000, 'Côte d''Ivoire','Émirats Arabes',  1, 1, 0.98),
(6, 'retrait',    20000, 'Sénégal',       'Sénégal',        13, 0, 0.06),
(7, 'transfert', 120000, 'Sénégal',       'Guinée',         16, 0, 0.10),
(7, 'transfert', 720000, 'Sénégal',       'Chine',           4, 1, 0.92),
(8, 'depot',       3000, 'Guinée',        'Guinée',         12, 0, 0.01),
(1, 'paiement',   18000, 'Sénégal',       'Sénégal',         8, 0, 0.03),
(2, 'transfert', 620000, 'Mali',          'Turquie',         0, 1, 0.94),
(3, 'paiement',   45000, 'Ghana',         'Ghana',          17, 0, 0.02);

INSERT INTO alertes_fraude (transaction_id, niveau, rapport_llm) VALUES
(2,  'eleve', 'Transfert international de 980 000 FCFA à 2h du matin vers un pays à haut risque. Score de fraude : 0.97. Action immédiate recommandée.'),
(5,  'eleve', 'Transfert de 500 000 FCFA vers la Chine à 3h du matin. Comportement inhabituel pour ce compte. Score : 0.95.'),
(8,  'eleve', 'Virement de 850 000 FCFA vers les Émirats à 1h du matin. Première transaction internationale de ce compte. Score : 0.98.'),
(11, 'moyen', 'Transfert de 720 000 FCFA vers la Chine à 4h du matin. Score de fraude modéré : 0.92. Surveillance conseillée.'),
(14, 'eleve', 'Transfert de 620 000 FCFA vers la Turquie à minuit. Montant inhabituel pour ce profil. Score : 0.94.');
