"""
Script de génération automatique des 4 diagrammes PlantUML - VERSION CORRIGÉE.

Corrections appliquées :
- Diagramme 1 (Flask) : layout réorganisé, ML models connectés aux blueprints
- Diagramme 3 (ORYA)  : flux séquentiel vertical au lieu de radial
- Diagrammes 2 & 4    : conservés (déjà parfaits)

Usage : python generate_all_diagrams.py
"""

import requests
import os
import sys

OUTPUT_DIR = "images"

STYLE_COMMUN = """
!theme plain
skinparam backgroundColor #FFFFFF
skinparam dpi 100
skinparam defaultFontName "Arial"
skinparam defaultFontSize 11
skinparam defaultFontColor #000000
skinparam shadowing false
skinparam roundCorner 0

skinparam ArrowColor #000000
skinparam ArrowFontColor #000000

skinparam sequence {
  ArrowColor #000000
  ActorBorderColor #000000
  ActorBackgroundColor #FFFFFF
  ActorFontColor #000000
  ParticipantBorderColor #000000
  ParticipantBackgroundColor #F5F5F5
  ParticipantFontColor #000000
  LifeLineBorderColor #888888
  LifeLineBackgroundColor #FFFFFF
  NoteBorderColor #888888
  NoteBackgroundColor #FAFAFA
  NoteFontColor #000000
  GroupBorderColor #000000
  GroupBackgroundColor #FFFFFF
  GroupFontColor #000000
  GroupHeaderFontColor #000000
  DividerBorderColor #000000
  DividerBackgroundColor #EEEEEE
  DividerFontColor #000000
  Padding 4
  BoxPadding 8
}

skinparam component {
  BackgroundColor #FFFFFF
  BorderColor #000000
  FontColor #000000
}
skinparam package {
  BackgroundColor #FAFAFA
  BorderColor #000000
  FontColor #000000
}
skinparam database {
  BackgroundColor #F5F5F5
  BorderColor #000000
  FontColor #000000
}
skinparam cloud {
  BackgroundColor #FAFAFA
  BorderColor #000000
  FontColor #000000
}
skinparam node {
  BackgroundColor #FFFFFF
  BorderColor #000000
  FontColor #000000
}
skinparam actor {
  BackgroundColor #FFFFFF
  BorderColor #000000
  FontColor #000000
}
skinparam titleFontColor #000000
skinparam titleFontSize 14
"""

# ═══════════════════════════════════════════════════════════
# DIAGRAMME 1 — ARCHITECTURE FLASK (CORRIGÉ)
# Layout vertical, ML models liés à leur blueprint
# ═══════════════════════════════════════════════════════════
DIAGRAM_1_FLASK_ARCHI = """
@startuml
""" + STYLE_COMMUN + """
title Architecture MVC + Blueprints - Application Flask

actor "Utilisateur\\n(3 roles)" as User

package "VUE - Frontend" as Vue {
  component "Templates Jinja2" as Templates
  component "Bootstrap 5\\n+ Chart.js 4.4" as Front
}

package "CONTROLEUR - Flask Blueprints" as Controleur {
  component "auth" as Auth
  component "performance" as Perf
  component "objectifs" as Obj
  component "prediction" as Pred
  component "paiements" as Pay
  component "chatbot ORYA" as Orya
  component "data_quality" as DQ
}

package "Modeles ML (joblib)" as ML {
  component "K-Means\\n(clustering)" as KM
  component "Isolation Forest\\n(anomalies)" as IF
  component "KNN\\n(regression)" as KNN
  component "Prophet\\n(forecasting)" as Prophet
  component "XGBoost\\n(classification)" as XGB
}

package "MODELE - SQLAlchemy" as Model {
  component "User" as MUser
  component "Vente" as MVente
  component "Boutique" as MBoutique
  component "Vendeur" as MVendeur
}

database "PostgreSQL\\norange_dwh" as DB
cloud "Google Gemini API" as Gemini

' --- Connexions verticales claires ---
User --> Templates : HTTP
Templates --> Front
Front --> Auth
Front --> Perf
Front --> Obj
Front --> Pred
Front --> Pay
Front --> Orya
Front --> DQ

' --- Blueprints utilisent leurs modeles ML ---
Perf ..> KM : segmentation
Obj ..> KNN : regression
Pred ..> Prophet : forecast
Pay ..> XGB : classif
DQ ..> IF : anomalies

' --- Auth utilise User ---
Auth --> MUser

' --- Blueprints accedent au DB via SQLAlchemy ---
Perf --> MVente
Perf --> MBoutique
Obj --> MVente
Pred --> MVente
Pay --> MVente
DQ --> MVendeur

MUser --> DB
MVente --> DB
MBoutique --> DB
MVendeur --> DB

' --- ORYA appelle Gemini et DB ---
Orya --> Gemini : NL to SQL
Orya --> DB : execute SQL

@enduml
"""

# ═══════════════════════════════════════════════════════════
# DIAGRAMME 2 — SÉQUENCE AUTH (CONSERVÉ - DÉJÀ PARFAIT)
# ═══════════════════════════════════════════════════════════
DIAGRAM_2_AUTH_SEQ = """
@startuml
""" + STYLE_COMMUN + """
title Diagramme de sequence - Authentification

actor "User" as U
participant "Navigateur" as B
participant "Flask" as F
participant "flask-login" as A
database "PostgreSQL" as D

== Saisie ==
U -> B : Ouvre /auth/login
B -> F : GET /auth/login
F --> B : Page de connexion
U -> B : email + mot de passe
B -> F : POST /auth/login

== Verification ==
F -> F : Valide formulaire (CSRF)
F -> D : SELECT user WHERE email
D --> F : user (hash scrypt, role)
F -> F : check_password_hash()

alt Identifiants valides
  F -> A : login_user(user)
  A -> A : Cree session (cookie signe)
  A --> F : Session active
  note right of F
    Redirection selon role:
    admin -> /dashboard/admin
    commercial -> /dashboard/performance
    data_engineer -> /data_quality
  end note
  F --> B : 302 + Set-Cookie
  B -> F : GET /dashboard/...
  F --> B : Dashboard
  B --> U : Acces accorde
else Identifiants invalides
  F --> B : flash("Identifiants incorrects")
  B --> U : Page login + erreur
end

@enduml
"""

# ═══════════════════════════════════════════════════════════
# DIAGRAMME 3 — ARCHITECTURE ORYA (CORRIGÉ)
# Flux vertical séquentiel au lieu de radial
# ═══════════════════════════════════════════════════════════
DIAGRAM_3_ORYA_ARCHI = """
@startuml
""" + STYLE_COMMUN + """
title Architecture du chatbot analytique ORYA

actor "Utilisateur metier" as User

package "Frontend Web" as Front {
  component "Interface conversationnelle\\n(HTML + JS)" as UI
}

package "ORYA Backend (Python)" as Backend {
  component "Schema Provider\\n(extraction schema DWH)" as Schema
  component "Agent ORYA\\n(orchestrateur principal)" as Agent
  component "SQL Security Validator\\n(filtre DROP/DELETE/UPDATE)" as Validator
  component "Response Formatter\\n(mise en forme)" as Formatter
}

cloud "Google Gemini API\\n(gemini-1.5-flash)" as Gemini
database "PostgreSQL\\norange_dwh\\n(9 tables)" as DWH
database "chatbot_conversations\\nchatbot_messages" as Logs

' --- Flux principal vertical ---
User -down-> UI : 1. question NL
UI -down-> Agent : 2. POST /orya/ask

' --- Agent recupere le schema ---
Agent -right-> Schema : 3. demande schema
Schema -left-> Agent : 4. tables + colonnes

' --- Agent appelle Gemini pour generer SQL ---
Agent -up-> Gemini : 5. prompt (question + schema)
Gemini -down-> Agent : 6. SQL genere

' --- Validation securite ---
Agent -right-> Validator : 7. valider SQL
Validator -left-> Agent : 8. OK / REJET

' --- Execution sur DWH ---
Agent -down-> DWH : 9. execute SQL
DWH -up-> Agent : 10. resultats

' --- Reformulation en langage naturel ---
Agent -up-> Gemini : 11. reformuler resultats
Gemini -down-> Agent : 12. reponse texte

' --- Mise en forme et reponse ---
Agent -right-> Formatter : 13. mise en forme
Formatter -left-> Agent : 14. reponse formatee
Agent -up-> UI : 15. reponse finale
UI -up-> User : 16. affiche reponse

' --- Journalisation ---
Agent ..> Logs : journalise\\nconversation

@enduml
"""

# ═══════════════════════════════════════════════════════════
# DIAGRAMME 4 — SÉQUENCE ORYA (CONSERVÉ - DÉJÀ PARFAIT)
# ═══════════════════════════════════════════════════════════
DIAGRAM_4_ORYA_SEQ = """
@startuml
""" + STYLE_COMMUN + """
title Diagramme de sequence - Requete analytique via ORYA

actor "User" as U
participant "Navigateur" as B
participant "ORYA\\nAgent" as O
participant "Gemini\\nAPI" as G
participant "SQL\\nValidator" as V
database "PostgreSQL\\norange_dwh" as D
database "Logs" as L

U -> B : Saisit question\\n(ex: "Top 5 vendeurs ?")
B -> O : POST /orya/ask\\n(question)

== Generation SQL ==
O -> O : Charge schema DWH
O -> G : Prompt enrichi\\n(question + schema)
G --> O : SQL genere
note right of G
  Exemple:
  SELECT seller_name, COUNT(*)
  FROM fact_ventes v
  JOIN dim_vendeur d ON ...
  GROUP BY seller_name
  ORDER BY COUNT(*) DESC
  LIMIT 5;
end note

== Validation securite ==
O -> V : Valide SQL

alt SQL securise (SELECT uniquement)
  V --> O : OK
  == Execution ==
  O -> D : Execute SQL
  D --> O : Resultats (DataFrame)
  == Reformulation NL ==
  O -> G : Reformuler resultats\\nen langage naturel
  G --> O : Reponse texte
  O --> B : Reponse finale
  B --> U : Affiche reponse
else SQL dangereux\\n(DROP/DELETE/UPDATE/INSERT)
  V --> O : REJET
  O --> B : "Operation non autorisee"
  B --> U : Message d'erreur
end

== Journalisation ==
O -> L : Insert\\n(conversation_id, question, sql, response)

@enduml
"""

DIAGRAMS = [
    ("fig_5_1_architecture_flask.png", DIAGRAM_1_FLASK_ARCHI),
    ("fig_5_3_seq_login.png",          DIAGRAM_2_AUTH_SEQ),
    ("fig_5_8_orya_architecture.png",  DIAGRAM_3_ORYA_ARCHI),
    ("fig_5_10_seq_orya.png",          DIAGRAM_4_ORYA_SEQ),
]


def generate_png(plantuml_code, output_path):
    try:
        response = requests.post(
            "https://kroki.io/plantuml/png",
            data=plantuml_code.encode('utf-8'),
            headers={"Content-Type": "text/plain"},
            timeout=60
        )
        if response.status_code != 200:
            print(f"   ERREUR HTTP {response.status_code}")
            print(f"   Reponse : {response.text[:300]}")
            return False
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        size_kb = len(response.content) / 1024
        print(f"   OK {output_path} ({size_kb:.1f} Ko)")
        return True
    except Exception as e:
        print(f"   ERREUR : {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  GENERATION V2 - DIAGRAMMES CORRIGES")
    print("=" * 60)
    success = 0
    for filename, code in DIAGRAMS:
        path = os.path.join(OUTPUT_DIR, filename)
        print(f"\n{filename}...")
        if generate_png(code, path):
            success += 1
    print("\n" + "=" * 60)
    print(f"  RESULTAT : {success}/{len(DIAGRAMS)} generes")
    print("=" * 60)
    if success < len(DIAGRAMS):
        sys.exit(1)
