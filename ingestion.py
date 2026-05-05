import pandas as pd
import streamlit as st

COLONNES_ATTENDUES = {
    "date": ["date comptable", "date_comptable", "datecomptable"],
    "tiers": ["tiers", "code tiers", "code_tiers"],
    "raison_sociale": ["raison sociale", "raison_sociale", "client"],
    "article": ["article", "code article", "code_article"],
    "designation": ["designation article", "designation_article", "designation"],
    "segment": ["segment"],
    "lob": ["lob", "line of business"],
    "canal": ["sales channel", "sales_channel", "canal"],
    "montant_ht": ["montant ht", "montant_ht", "ca ht", "ca_ht", "chiffre affaires"],
    "qte": ["qte facturee", "qte_facturee", "quantite", "quantity"],
    "cogs": ["cogs", "cout revient", "cout_revient"],
    "marge": ["marge", "marge unitaire", "marge_unitaire"],
    "marge_total": ["marge total", "marge_total", "marge totale"],
    "num_piece": ["numero de piece", "numero_piece", "num piece", "piece"],
    "mvt_stock": ["mvt stock", "mvt_stock", "mouvement stock"],
}


def detecter_colonne(df_cols, noms_possibles):
    df_cols_lower = [c.lower().strip() for c in df_cols]
    for nom in noms_possibles:
        for i, col in enumerate(df_cols_lower):
            if nom in col or col in nom:
                return df_cols[i]
    return None


def charger_fichier(fichier):
    nom = fichier.name.lower()
    try:
        if nom.endswith(".csv"):
            for sep in [";", "\t", ","]:
                try:
                    df = pd.read_csv(fichier, sep=sep, encoding="utf-8")
                    if len(df.columns) > 2:
                        break
                except Exception:
                    fichier.seek(0)
            else:
                df = pd.read_csv(fichier, encoding="latin-1", sep=";")
        else:
            df = pd.read_excel(fichier)
    except Exception as e:
        st.error(f"Erreur lecture fichier : {e}")
        return None, {}

    df.columns = [str(c).strip() for c in df.columns]

    mapping = {}
    for cle, noms in COLONNES_ATTENDUES.items():
        col = detecter_colonne(list(df.columns), noms)
        if col:
            mapping[cle] = col

    df_clean = pd.DataFrame()
    for cle, col in mapping.items():
        df_clean[cle] = df[col]

    if "date" in df_clean.columns:
        df_clean["date"] = pd.to_datetime(df_clean["date"], errors="coerce")
        df_clean["mois"] = df_clean["date"].dt.to_period("M").astype(str)

    for col_num in ["montant_ht", "cogs", "marge", "marge_total", "qte"]:
        if col_num in df_clean.columns:
            df_clean[col_num] = pd.to_numeric(df_clean[col_num], errors="coerce").fillna(0)

    colonnes_manquantes = [k for k in COLONNES_ATTENDUES if k not in mapping]

    return df_clean, {"mapping": mapping, "colonnes_manquantes": colonnes_manquantes, "nb_lignes": len(df_clean)}
