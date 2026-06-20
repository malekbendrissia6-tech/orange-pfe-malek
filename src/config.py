"""
=============================================================
  MODULE : config.py
  RÔLE  : Configuration centralisée des règles de nettoyage
  PROJET: PFE Orange Tunisie - Pipeline de nettoyage
=============================================================

Principe DATA-DRIVEN :
    Les règles de nettoyage sont séparées du code.
    Pour ajouter une nouvelle table : ajouter une entrée
    dans le dictionnaire TABLES_CONFIG. Le code (cleaner.py)
    ne change pas !

Règles disponibles par table :
    - source_file      : chemin du fichier Excel brut
    - output_file      : chemin du fichier nettoyé
    - primary_key      : colonne identifiant unique
    - date_columns     : colonnes à convertir en date
    - numeric_columns  : colonnes à convertir en nombre
    - string_columns   : colonnes texte à normaliser
    - categorical_map  : mapping pour standardiser des valeurs
    - drop_if_null     : colonnes dont NaN = supprimer la ligne
    - fill_na          : valeurs par défaut pour les NaN
    - conditional_fill : remplissage conditionnel
    - output_types     : types finaux (pour Power BI)
=============================================================
"""

TABLES_CONFIG = {

    # ==================================================================
    # TABLE 1 : VENTES DE CONTRATS (DATASET.xlsx - table de faits)
    # ==================================================================
    "ventes_contrats": {
        "source_file": "data/input/ventes_contrats.xlsx",
        "output_file": "data/output/ventes_contrats_clean.xlsx",

        "primary_key": "CONTRAT_SOUSCRIT",

        "date_columns": ["ACTION_DATE"],
        "add_month_from": "ACTION_DATE",

        "numeric_columns": [
            "PRODUCT_NUMBER", "CUSTCODE", "TMCODE", "PRGCODE",
            "FIRST_MONTH_BILL", "SECOND_MONTH_BILL", "THIRD_MONTH_BILL",
        ],

        "string_columns": [
            "DUREE_ENGAGEMENT", "TYPE_ENGAGEMENT", "ENTITY_CODE",
            "SELLER_ID", "CONTRAT_SOUSCRIT", "OBJ_ID",
        ],

        # Standardisation CORRIGEE: on enleve le mot "mois"
        # "12Mois" -> "12", "24 mois" -> "24", etc.
        "categorical_map": {
            "DUREE_ENGAGEMENT": {
                "12mois": "12",
                "24mois": "24",
                "25mois": "25",
                "36mois": "36",
                "6mois":  "6",
            },
            "TYPE_ENGAGEMENT": {
                "avecengagement":  "Avec engagement",
                "sansengagement": "Sans engagement",
            },
        },

        # Supprimer la ligne si ces colonnes sont NaN (données inutilisables)
        "drop_if_null": ["CONTRAT_SOUSCRIT", "ACTION_DATE"],

        # Remplissage des NaN avec valeurs par défaut
        "fill_na": {
            "OBJ_ID": "NON_RENSEIGNE",
            "ENTITY_CODE": "NON_ATTRIBUE",
            "PRODUCT_NUMBER": -1,
            "DUREE_ENGAGEMENT": "0",
        },

        # Règle CORRIGEE: Sans engagement -> DUREE = "0" (zero)
        "conditional_fill": [
            {
                "if_column": "TYPE_ENGAGEMENT",
                "if_value": "Sans engagement",
                "then_column": "DUREE_ENGAGEMENT",
                "then_value": "0",
                "only_if_null": True,
            },
        ],

        # Types finaux optimisés pour Power BI
        # DUREE_ENGAGEMENT devient un NOMBRE ENTIER (Int16) pour les calculs
        "output_types": {
            "CONTRAT_SOUSCRIT": "string",
            "SELLER_ID": "string",
            "ENTITY_CODE": "string",
            "OBJ_ID": "string",
            "DUREE_ENGAGEMENT": "Int16",
            "TYPE_ENGAGEMENT": "string",
            "TMCODE": "Int64",
            "PRGCODE": "Int64",
            "PRODUCT_NUMBER": "Int64",
            "CUSTCODE": "float64",
            "FIRST_MONTH_BILL": "Int8",
            "SECOND_MONTH_BILL": "Int8",
            "THIRD_MONTH_BILL": "Int8",
            "MONTH": "string",
        },
    },

    # ==================================================================
    # TABLE 2 : CATALOGUE DES OFFRES (dimension)
    # ==================================================================
    "offres": {
        "source_file": "data/input/offres.xlsx",
        "output_file": "data/output/offres_clean.xlsx",

        "primary_key": "TMCODE",

        "date_columns": [],

        "numeric_columns": ["TMCODE"],

        "string_columns": [
            "OFFRE_NAME", "TYPE_OFFRE", "CANAL",
            "FAMILLE", "CATEGORIE", "CIBLE",
        ],

        "categorical_map": {},

        "drop_if_null": ["TMCODE"],

        "fill_na": {
            "OFFRE_NAME": "NON_RENSEIGNE",
            "TYPE_OFFRE": "INCONNU",
            "CANAL": "INCONNU",
            "FAMILLE": "INCONNU",
            "CATEGORIE": "INCONNU",
            "CIBLE": "INCONNU",
        },

        "conditional_fill": [],

        "output_types": {
            "TMCODE": "Int64",
            "OFFRE_NAME": "string",
            "TYPE_OFFRE": "string",
            "CANAL": "string",
            "FAMILLE": "string",
            "CATEGORIE": "string",
            "CIBLE": "string",
        },
    },

    # ==================================================================
    # TABLE 3 : VENDEURS (dimension)
    # ==================================================================
    "vendeurs": {
        "source_file": "data/input/vendeurs.xlsx",
        "output_file": "data/output/vendeurs_clean.xlsx",

        "primary_key": "SELLER_KEY",

        "date_columns": ["SELLER_DATE"],
        "add_month_from": "SELLER_DATE",

        "composite_key": {
            "name": "SELLER_KEY",
            "columns": ["SELLER_ID", "MONTH"],
            "separator": "_",
        },

        "numeric_columns": [],

        "string_columns": ["SELLER_ID", "SELLER_NAME", "CODE_STOCK"],

        "categorical_map": {},

        "drop_if_null": ["SELLER_ID"],

        "fill_na": {
            "SELLER_NAME": "NON_RENSEIGNE",
            "CODE_STOCK": "NON_ATTRIBUE",
        },

        "conditional_fill": [],

        "output_types": {
            "SELLER_ID": "string",
            "SELLER_NAME": "string",
            "CODE_STOCK": "string",
            "MONTH": "string",
            "SELLER_KEY": "string",
        },
    },

    # ==================================================================
    # TABLE 4 : BOUTIQUES (dimension - entités de vente)
    # ==================================================================
    "boutiques": {
        "source_file": "data/input/boutiques.xlsx",
        "output_file": "data/output/boutiques_clean.xlsx",

        "primary_key": "CODE_ENTITY",

        "date_columns": [],

        "numeric_columns": [],

        "string_columns": [
            "CODE_ENTITY", "ENTITY_NAME", "RESPONSABLE",
            "RESPONSABLE_ZONE", "CANAL_VENTE",
        ],

        "categorical_map": {},

        "drop_if_null": ["CODE_ENTITY"],

        "fill_na": {
            "ENTITY_NAME": "NON_RENSEIGNE",
            "RESPONSABLE": "NON_ATTRIBUE",
            "RESPONSABLE_ZONE": "NON_ATTRIBUE",
            "CANAL_VENTE": "INCONNU",
        },

        "conditional_fill": [],

        "output_types": {
            "CODE_ENTITY": "string",
            "ENTITY_NAME": "string",
            "RESPONSABLE": "string",
            "RESPONSABLE_ZONE": "string",
            "CANAL_VENTE": "string",
        },
    },

    # ==================================================================
    # TABLE 5 : GROUPES PRODUITS (dimension - lignes de produit)
    # ==================================================================
    "groupes": {
        "source_file": "data/input/groupes.xlsx",
        "output_file": "data/output/groupes_clean.xlsx",

        "primary_key": "PRGCODE",

        "date_columns": [],

        "numeric_columns": ["PRGCODE"],

        "string_columns": ["PRGNAME", "FAMILLE_PRGNAME"],

        "categorical_map": {},

        "drop_if_null": ["PRGCODE"],

        "fill_na": {
            "PRGNAME": "NON_RENSEIGNE",
            "FAMILLE_PRGNAME": "INCONNU",
        },

        "conditional_fill": [],

        "output_types": {
            "PRGCODE": "Int64",
            "PRGNAME": "string",
            "FAMILLE_PRGNAME": "string",
        },
    },
    # ==================================================================
    # TABLE 6 : ARTICLES (dimension - catalogue produits)
    # ==================================================================
    "articles": {
        "source_file": "data/input/articles.xlsx",
        "output_file": "data/output/articles_clean.xlsx",

        "primary_key": "PRODUCT_CODE",

        "date_columns": [],

        "numeric_columns": ["PRODUCT_CODE"],

        "string_columns": [
            "PRODUCT_NAME", "PRODUCT_CONTROL_KEY", "PRODUCT_TYPE",
        ],

        "categorical_map": {},

        "drop_if_null": ["PRODUCT_CODE"],

        "fill_na": {
            "PRODUCT_NAME": "NON_RENSEIGNE",
            "PRODUCT_CONTROL_KEY": "INCONNU",
            "PRODUCT_TYPE": "INCONNU",
        },

        "conditional_fill": [],

        "output_types": {
            "PRODUCT_CODE": "Int64",
            "PRODUCT_NAME": "string",
            "PRODUCT_CONTROL_KEY": "string",
            "PRODUCT_TYPE": "string",
        },

        # Renommer les colonnes (camelCase Excel -> UPPER_CASE Python)
        "rename_columns": {
            "Product_code": "PRODUCT_CODE",
            "product_name": "PRODUCT_NAME",
            "product_control_key": "PRODUCT_CONTROL_KEY",
            "product_type": "PRODUCT_TYPE",
        },
    },

    # ==================================================================
    # TABLE 7 : REF_OBJECTIFS (dimension - types d'objectifs)
    # ==================================================================
    "ref_objectifs": {
        "source_file": "data/input/ref_objectifs.xlsx",
        "output_file": "data/output/ref_objectifs_clean.xlsx",

        "primary_key": "LIGNE_PDT_OBJ",

        "date_columns": [],

        "numeric_columns": [],

        "string_columns": ["LIGNE_PDT_OBJ", "DESIGNATION_OBJECTIF"],

        "categorical_map": {},

        "drop_if_null": ["LIGNE_PDT_OBJ"],

        "fill_na": {
            "DESIGNATION_OBJECTIF": "NON_RENSEIGNE",
        },

        "conditional_fill": [],

        "output_types": {
            "LIGNE_PDT_OBJ": "string",
            "DESIGNATION_OBJECTIF": "string",
        },

        # Renommer les colonnes (espaces -> underscores)
        "rename_columns": {
            "ligne_pdt_obj": "LIGNE_PDT_OBJ",
            "Designation Objectif": "DESIGNATION_OBJECTIF",
        },
    },

    # ==================================================================
    # TABLE 8 : OBJECTIFS (table de faits - objectifs par boutique)
    # ==================================================================
    "objectifs": {
        "source_file": "data/input/objectifs.xlsx",
        "output_file": "data/output/objectifs_clean.xlsx",

        "primary_key": None,

        "date_columns": [],

        "numeric_columns": ["OBJECTIF"],

        "string_columns": ["CODE_OBJ", "CODE_ENTITY"],

        "categorical_map": {},

        "drop_if_null": ["CODE_OBJ", "CODE_ENTITY"],

        "fill_na": {
            "OBJECTIF": 0,
        },

        "conditional_fill": [],

        "output_types": {
            "CODE_OBJ": "string",
            "CODE_ENTITY": "string",
            "OBJECTIF": "Int64",
        },

        # Renommer les colonnes (espace -> underscore)
        "rename_columns": {
            "CODE ENTITE": "CODE_ENTITY",
        },
    },

}