"""Classification des intentions utilisateur."""


class IntentClassifier:
    def __init__(self):
        self.keywords = {
            'data_visualization': [
                'graphique', 'graph', 'chart', 'diagramme', 'courbe',
                'montre', 'visualise', 'affiche', 'dessine', 'trace', 'plot'
            ],
            'kpi_query': [
                'combien', 'total', 'somme', 'moyenne', 'nombre',
                'quel', 'quelle', 'taux', 'pourcentage',
                'top', 'meilleur', 'mieux', 'classement', 'liste', 'rang',
                'ventes', 'vente', 'boutique', 'magasin', 'vendeur', 'commercial', 'agent',
                'canal', 'produit', 'offre', 'forfait',
                'objectif', 'realisation', 'facture', 'impaye', 'paiement',
                'chiffre', 'ca', 'region', 'activation', 'contrat',
                'plus de', 'le plus', 'la plus', 'premier', 'premiere',
            ],
            'app_help': [
                'comment', 'ou est', 'ou se trouve', 'aide', 'help',
                'comprendre', 'expliquer', 'utiliser', 'fonctionne',
                'mode sombre', 'connexion', 'login', 'page', 'naviguer',
                'deconnecter', 'parametre'
            ],
            'general_business': [
                'pourquoi', 'analyse', 'recommandation', 'strategie',
                'amelioration', 'risque', 'opportunite', 'tendance',
                'compare', 'concurrent', 'marche', 'levier', 'action'
            ]
        }

    def classify(self, message: str) -> str:
        msg = message.lower()
        scores = {
            intent: sum(1 for kw in kws if kw in msg)
            for intent, kws in self.keywords.items()
        }
        if scores['data_visualization'] > 0:
            return 'data_visualization'
        if scores['kpi_query'] > 0:
            return 'kpi_query'
        if scores['app_help'] > 0:
            return 'app_help'
        if scores['general_business'] > 0:
            return 'general_business'
        return 'general'
