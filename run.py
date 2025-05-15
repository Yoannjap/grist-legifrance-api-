import os
import requests
import time
from dotenv import load_dotenv

# Charger les variables d’environnement depuis .env (utile en local)
load_dotenv()

# === CONFIGURATION ===
GRIST_API_KEY = os.getenv("GRIST_API_KEY")
GRIST_DOC_ID = os.getenv("GRIST_DOC_ID")
GRIST_API_URL = f"https://grist.numerique.gouv.fr/api/docs/{GRIST_DOC_ID}"
GRIST_TABLE = os.getenv("GRIST_TABLE", "Resultats")
GRIST_SEARCH_TABLE = os.getenv("GRIST_SEARCH_TABLE", "Recherche")

LEGIFRANCE_CLIENT_ID = os.getenv("LEGIFRANCE_CLIENT_ID")
LEGIFRANCE_CLIENT_SECRET = os.getenv("LEGIFRANCE_CLIENT_SECRET")

# === OBTENIR LE TOKEN LEGIFRANCE ===
def get_legifrance_token():
    url = "https://oauth.aife.economie.gouv.fr/api/oauth/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": LEGIFRANCE_CLIENT_ID,
        "client_secret": LEGIFRANCE_CLIENT_SECRET,
        "scope": "openid legifrance"
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

# === INTERROGER LEGIFRANCE ===
def interroger_legifrance(critere, token_legifrance):
    url = "https://api.aife.economie.gouv.fr/dila/legifrance/lf-engine-app/consult/search"
    headers = {"Authorization": f"Bearer {token_legifrance}"}
    payload = {
        "pageSize": 10,
        "pageNumber": 1,
        "query": critere,
        "sources": ["JORF"],
        "types": ["ARRETE"]
    }
    r = requests.post(url, json=payload, headers=headers)
    r.raise_for_status()
    return r.json()

# === INSÉRER DANS GRIST ===
def inserer_dans_grist(docs, critere):
    headers = {"Authorization": f"Bearer {GRIST_API_KEY}"}
    for doc in docs:
        titre = doc.get("title", "")
        date_pub = doc.get("datePubli", "")[:10]
        id_lien = doc.get("id", "")
        url_doc = f"https://www.legifrance.gouv.fr/jorf/id/{id_lien}"

        payload = {
            "records": [{
                "fields": {
                    "Critere de recherche": critere,
                    "Titre du document": titre,
                    "Date de publication": date_pub,
                    "Source (URL PDF ou Legifrance)": url_doc,
                    "Type d’habilitation repérée": "Inconnue",
                    "Région si mentionnée": "",
                    "Validité estimée (année de fin)": None
                }
            }]
        }

        r = requests.post(f"{GRIST_API_URL}/tables/{GRIST_TABLE}/records", headers=headers, json=payload)
        if r.status_code not in [200, 201]:
            print(f"⚠️ Erreur insertion Grist : {r.status_code} - {r.text}")
        else:
            print(f"✅ Insertion réussie : {titre}")
        time.sleep(0.5)

# === LIRE LE CHAMP DE RECHERCHE ===
def lire_critere_recherche():
    headers = {"Authorization": f"Bearer {GRIST_API_KEY}"}
    r = requests.get(f"{GRIST_API_URL}/tables/{GRIST_SEARCH_TABLE}/records", headers=headers)
    r.raise_for_status()
    data = r.json()["records"]
    for d in data:
        if d["fields"].get("Soumettre") is True:
            return d["id"], d["fields"].get("Critere")
    return None, None

# === RÉINITIALISER LE BOUTON ===
def reinitialiser_bouton(id_ligne):
    headers = {"Authorization": f"Bearer {GRIST_API_KEY}"}
    payload = {"records": [{"id": id_ligne, "fields": {"Soumettre": False}}]}
    r = requests.patch(f"{GRIST_API_URL}/tables/{GRIST_SEARCH_TABLE}/records", headers=headers, json=payload)
    if r.status_code not in [200, 201]:
        print(f"⚠️ Erreur réinitialisation bouton : {r.text}")

# === MAIN ===
if __name__ == "__main__":
    ligne_id, critere = lire_critere_recherche()
    if critere:
        print(f"🔍 Lancement de la recherche pour : {critere}")
        try:
            token = get_legifrance_token()
            resultats = interroger_legifrance(critere, token)
            inserer_dans_grist(resultats.get("results", []), critere)
        except Exception as e:
            print(f"❌ Erreur : {e}")
        finally:
            if ligne_id:
                reinitialiser_bouton(ligne_id)
        print("✅ Traitement terminé.")
    else:
        print("⏸ Aucun critère actif.")
