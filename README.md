# Plateforme de Pilotage et de Prédiction des Ventes — Orange Tunisie

Projet de Fin d'Études (PFE) — Licence Business Computing, Esprit School of Business (2026)
Réalisé en stage au sein de la Direction Commerciale B2C d'Orange Tunisie.

## 🎯 Objectif
Concevoir une plateforme décisionnelle complète permettant de piloter, analyser et prédire les ventes des contrats à facture, en combinant Business Intelligence et Machine Learning.

## 🏗️ Architecture du projet

- **ETL Python** : pipeline de traitement (132 411 lignes traitées, 90 696 chargées)
- **Data Warehouse PostgreSQL** : modélisation en constellation (Kimball) — 9 tables (7 dimensions + 2 faits)
- **Application web Flask** : architecture MVC + Blueprints, 4 dashboards, authentification, chatbot IA
- **Chatbot ORYA** : assistant conversationnel basé sur Groq Llama 3.3 70B
- **Interface Data Engineer** : supervision de la qualité des données
- **Déploiement cloud** : Render.com + Neon.tech (PostgreSQL serverless)

## 🧠 Machine Learning (notebooks)

| Notebook | Objectif | Technique |
|---|---|---|
| `01_exploration.ipynb` | Exploration du Data Warehouse (8 tables) | EDA |
| `02_clustering_vendeurs.ipynb` | Segmentation des vendeurs en personas | K-Means |
| `03_anomalies.ipynb` | Détection de vendeurs anormaux | Isolation Forest |
| `04_prediction_ventes.ipynb` | Prédiction des ventes | Régression, KNN + GridSearchCV |
| `05_forecasting_mensuel.ipynb` | Prévision de clôture mensuelle | XGBoost vs Prophet (MAPE 3.6%) |
| `06_suivi_paiements.ipynb` | Prédiction des paiements clients | XGBoost (AUC 0.812) |

## 📊 Power BI (bonus)

Un dashboard Power BI complète le projet, mais la prévision avancée (Prophet, XGBoost) est réalisée dans les notebooks Python — Power BI ne proposant qu'une prévision linéaire native limitée.

![Dashboard Commercial](rapport/powerbi-dashboard-commercial.png)
![Prédiction des ventes](rapport/powerbi-prediction-ventes.png)

## 🛠️ Stack technique
Python · Flask · PostgreSQL · Pandas · Scikit-learn · XGBoost · Prophet · Power BI · Bootstrap 5 · Chart.js · Render.com

## 👤 Auteur
Malek Ben Drissia — Licence Business Computing, Esprit School of Business
Mention Très Bien — 17/20
