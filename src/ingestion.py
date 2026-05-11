import pandas as pd
import streamlit as st
import zipfile
import io
import re
from lxml import etree

# ---------------------------------------------------------------------------
# Mapping colonnes Sage X3 -> noms internes
# ---------------------------------------------------------------------------
COLONNES_ATTENDUES = {
    "date":           ["date comptable"],
    "num_piece":      ["numéro de pièce", "numero de piece"],
    "type_facture":   ["type facture"],
    "tiers":          ["tiers"],
    "raison_sociale": ["raison sociale"],
    "article":        ["article"],
    "designation":    ["désignation article", "designation article"],
    "segment":        ["segment"],
    "lob":            ["lob"],
    "canal":          ["sales channel"],
    "montant_ht":     ["montant ht (devise local)"],
    "qte":            ["qté facturée", "qte facturee"],
    "cogs":           ["cogs (devise local)"],
    "marge":          ["marge (devise local)"],
    "marge_total":    ["marge total (devise local)"],
    "mvt_stock":      ["mvt stock"],
    "prix_revient":   ["prix revient (devise local)"],
    "devise":         ["devise"],
    "site":           ["site"],
    "compte":         ["comptes généraux", "comptes generaux", "compte général", "compte general"],
    "societe":        ["société", "societe"],
    "cost_center":    ["cost center"],
    "produit":        ["product"],
    "volume":         ["volume ligne"],
    "collect":        ["collect"],
}

LOB_VALIDES   = {"B2B", "B2C", "LUB", "LPG", "INDUS", "DODO", "DISTR", "COMM",
                 "WHOSA", "EXPOR", "CODO", "DOMES", "AGRI"}
CANAL_VALIDES = {"DISTR", "DODO", "INDUS", "EXPOR", "CODO", "COMM", "WHOSA",
                 "DOMES", "AGRI", "OWNDI"}

EXCEL_EPOCH = pd.Timestamp("1899-12-30")

# ---------------------------------------------------------------------------
# Logique de segmentation comptable
#
#   SINV + compte 31x  → df_ventes       (vraies ventes, KPIs principaux)
#   SINV + compte 36x  → df_frais_passage (transit/intermédiaire, onglet séparé)
#   CRM   (tout compte)→ df_avoirs        (credit notes, onglet séparé)
#   SDBN  (tout compte)→ exclu            (dépôts Fleet Card, pas des ventes)
# ---------------------------------------------------------------------------


def _compte_prefix(serie: pd.Series) -> pd.Series:
    """Retourne les 2 premiers chiffres du compte général."""
    return serie.astype(str).str.strip().str[:2]


# ---------------------------------------------------------------------------
# Parseur XML Sage X3
# ---------------------------------------------------------------------------

def col_letters(cell_ref: str) -> str:
    return re.match(r'([A-Z]+)', cell_ref).group(1)


def detecter_colonne(df_cols: list, noms_possibles: list):
    df_cols_lower = [c.lower().strip() for c in df_cols]
    for nom in noms_possibles:
        for i, col in enumerate(df_cols_lower):
            if col == nom or nom in col:
                return df_cols[i]
    return None


def serial_to_date(val):
    try:
        n = float(val)
        if 30000 < n < 70000:
            return EXCEL_EPOCH + pd.Timedelta(days=int(n))
        return pd.NaT
    except Exception:
        return pd.NaT


def lire_xlsx_sage(contenu_bytes: bytes) -> pd.DataFrame | None:
    """
    Parseur XML robuste pour fichiers Sage X3 (stylesheet parfois corrompue).
    - Cible la feuille Sage.X3.DS. (sheet2.xml par défaut)
    - Lit les cellules par référence de colonne (évite les décalages)
    - Ignore les lignes cachées (totaux intermédiaires Sage)
    """
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

    with zipfile.ZipFile(io.BytesIO(contenu_bytes)) as z:
        with z.open("xl/sharedStrings.xml") as f:
            shared_root = etree.parse(f)
        strings = [
            "".join(t.text or "" for t in si.findall(f".//{{{ns}}}t"))
            for si in shared_root.findall(f"{{{ns}}}si")
        ]

        # Trouver "Sage.X3.DS." par son nom exact dans workbook.xml
        # Elle peut être en sheet2, sheet3... selon si un TCD est présent avant elle
        target_sheet = None
        try:
            with z.open("xl/workbook.xml") as f:
                wb = etree.parse(f)
            rels_map = {}
            with z.open("xl/_rels/workbook.xml.rels") as f:
                rels_xml = etree.parse(f)
            for r in rels_xml.findall(
                ".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
            ):
                rels_map[r.get("Id")] = r.get("Target")
            for s in wb.findall(f".//{{{ns}}}sheet"):
                if s.get("name", "") == "Sage.X3.DS.":
                    rid = s.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    )
                    target = rels_map.get(rid, "")
                    if target:
                        target_sheet = f"xl/{target}"
                        break
        except Exception:
            pass

        # Fallback : feuille avec le plus grand nombre de colonnes dans le header
        if not target_sheet or target_sheet not in z.namelist():
            best_sheet = "xl/worksheets/sheet2.xml"
            best_cols = 0
            for sheet_file in z.namelist():
                if not (sheet_file.startswith("xl/worksheets/sheet") and sheet_file.endswith(".xml")):
                    continue
                try:
                    with z.open(sheet_file) as f:
                        sh = etree.parse(f)
                    first_rows = sh.findall(f".//{{{ns}}}row")
                    n = len(first_rows[0].findall(f"{{{ns}}}c")) if first_rows else 0
                    if n > best_cols:
                        best_cols = n
                        best_sheet = sheet_file
                except Exception:
                    continue
            target_sheet = best_sheet

        with z.open(target_sheet) as f:
            sheet = etree.parse(f)

        rows = sheet.findall(f".//{{{ns}}}row")
        if len(rows) < 2:
            return None

        # Header
        col_map = {}
        for c in rows[0].findall(f"{{{ns}}}c"):
            ref = c.get("r", "")
            if not ref:
                continue
            letters = col_letters(ref)
            t = c.get("t", "")
            v_el = c.find(f"{{{ns}}}v")
            v = v_el.text if v_el is not None else None
            if t == "s" and v is not None:
                col_map[letters] = strings[int(v)]
            elif v is not None:
                col_map[letters] = v

        if len(col_map) < 5:
            return None

        # Données
        data = []
        for row in rows[1:]:
            if row.get("hidden") == "1":
                continue
            rd = {}
            for c in row.findall(f"{{{ns}}}c"):
                ref = c.get("r", "")
                if not ref:
                    continue
                letters = col_letters(ref)
                col_name = col_map.get(letters, letters)
                t = c.get("t", "")
                v_el = c.find(f"{{{ns}}}v")
                v = v_el.text if v_el is not None else None
                if t == "s" and v is not None:
                    rd[col_name] = strings[int(v)]
                elif v is not None:
                    try:
                        rd[col_name] = float(v)
                    except Exception:
                        rd[col_name] = v
                else:
                    rd[col_name] = None
            data.append(rd)

        return pd.DataFrame(data) if data else None


# ---------------------------------------------------------------------------
# Nettoyage commun (appliqué à toutes les strates)
# ---------------------------------------------------------------------------

def _nettoyer_base(df_raw: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Sélectionne et nettoie les colonnes mappées.
    Retourne le DataFrame complet SANS filtre par type/compte.
    """
    df = pd.DataFrame()
    for cle, col in mapping.items():
        df[cle] = df_raw[col].copy()

    # Type facture
    if "type_facture" in df.columns:
        df["type_facture"] = df["type_facture"].astype(str).str.strip()
    else:
        df["type_facture"] = "SINV"

    # Compte général — préfixe 2 chiffres
    if "compte" in df.columns:
        df["compte"] = df["compte"].astype(str).str.strip()
        df["compte_prefix"] = df["compte"].str[:2]
    else:
        df["compte"] = ""
        df["compte_prefix"] = ""

    # Dates serial Excel -> datetime
    if "date" in df.columns:
        sample = df["date"].dropna().iloc[0] if not df["date"].dropna().empty else None
        if sample is not None and isinstance(sample, (float, int)):
            df["date"] = df["date"].apply(serial_to_date)
        else:
            df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
        df["mois"] = df["date"].dt.to_period("M").astype(str)

    # Numériques
    for c in ["montant_ht", "cogs", "marge", "marge_total", "qte", "prix_revient"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # LOB
    if "lob" in df.columns:
        df["lob"] = df["lob"].astype(str).str.strip()
        df["lob"] = df["lob"].where(df["lob"].isin(LOB_VALIDES), other="Autre")

    # Canal
    if "canal" in df.columns:
        df["canal"] = df["canal"].astype(str).str.strip()
        df["canal"] = df["canal"].where(df["canal"].isin(CANAL_VALIDES), other="Autre")

    # Segment
    if "segment" in df.columns:
        df["segment"] = df["segment"].astype(str).str.strip()
        df["segment"] = df["segment"].replace(
            {"": "Non défini", "nan": "Non défini", "None": "Non défini"}
        )

    # Strings
    for c in ["tiers", "raison_sociale", "num_piece", "article", "designation",
              "mvt_stock", "societe", "cost_center", "produit", "collect"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # Supprimer lignes montant = 0
    if "montant_ht" in df.columns:
        df = df[df["montant_ht"] != 0].copy()

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Segmentation comptable principale
# ---------------------------------------------------------------------------

def segmenter_flash_report(df: pd.DataFrame) -> dict:
    """
    Segmente le DataFrame brut nettoyé en 3 strates comptables :

    - 'ventes'         : SINV + compte 31x → vraies ventes, KPIs principaux
    - 'frais_passage'  : SINV + compte 36x → transit/intermédiaire, onglet dédié
    - 'avoirs'         : CRM (tous comptes) → credit notes, onglet dédié
    - (SDBN exclu)     : dépôts Fleet Card, pas des ventes

    Retourne un dict avec les 3 DataFrames + métadonnées.
    """
    tf = df["type_facture"]
    cp = df.get("compte_prefix", pd.Series([""] * len(df)))

    # Strate 1 — Vraies ventes : SINV compte 31x
    mask_ventes = (tf == "SINV") & (cp == "31")
    df_ventes = df[mask_ventes].copy()

    # Strate 2 — Frais de passage : SINV compte 36x
    mask_fp = (tf == "SINV") & (cp == "36")
    df_fp = df[mask_fp].copy()

    # Strate 3 — Avoirs : CRM (tous comptes)
    mask_avoirs = tf == "CRM"
    df_avoirs = df[mask_avoirs].copy()

    # SDBN → exclu silencieusement (dépôts Fleet Card)
    nb_sdbn = int((tf == "SDBN").sum())

    return {
        "ventes":          df_ventes,
        "frais_passage":   df_fp,
        "avoirs":          df_avoirs,
        "nb_sdbn_exclus":  nb_sdbn,
        "stats": {
            "nb_ventes":        len(df_ventes),
            "nb_frais_passage": len(df_fp),
            "nb_avoirs":        len(df_avoirs),
            "nb_sdbn":          nb_sdbn,
        },
    }


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def charger_fichier(fichier) -> tuple[dict | None, dict]:
    """
    Charge un fichier Flash Report Sage X3 (xlsx ou csv).

    Retourne :
        (segments, meta)
        segments = {"ventes": df, "frais_passage": df, "avoirs": df, ...}
        meta     = {"mapping": ..., "colonnes_manquantes": ..., "stats": ..., ...}
    """
    nom = fichier.name.lower()
    df_raw = None

    try:
        contenu = fichier.read()

        if nom.endswith(".csv"):
            for sep in [";", "\t", ","]:
                for enc in ["utf-8", "latin-1", "utf-8-sig"]:
                    try:
                        df_raw = pd.read_csv(io.BytesIO(contenu), sep=sep, encoding=enc)
                        if len(df_raw.columns) > 3:
                            break
                    except Exception:
                        continue
                if df_raw is not None and len(df_raw.columns) > 3:
                    break
        else:
            # Essai 1 : openpyxl standard
            try:
                df_raw = pd.read_excel(io.BytesIO(contenu), engine="openpyxl")
            except Exception:
                # Essai 2 : parseur XML custom (stylesheet Sage corrompue)
                df_raw = lire_xlsx_sage(contenu)

    except Exception as e:
        st.error(f"Erreur lecture fichier : {e}")
        return None, {}

    if df_raw is None or df_raw.empty:
        st.error("Impossible de lire le fichier.")
        return None, {}

    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    # Détecter le mapping colonnes
    mapping = {}
    for cle, noms in COLONNES_ATTENDUES.items():
        col = detecter_colonne(list(df_raw.columns), noms)
        if col:
            mapping[cle] = col

    colonnes_manquantes = [
        k for k in ["date", "tiers", "montant_ht", "marge_total", "cogs", "compte"]
        if k not in mapping
    ]

    if colonnes_manquantes:
        st.warning(
            f"⚠️ Colonnes non trouvées : {', '.join(colonnes_manquantes)}. "
            "Vérifier le format du fichier."
        )

    # Nettoyage de base
    try:
        df_clean = _nettoyer_base(df_raw, mapping)
    except Exception as e:
        st.error(f"Erreur nettoyage : {e}")
        return None, {}

    # Segmentation comptable
    segments = segmenter_flash_report(df_clean)

    # Métadonnées
    meta = {
        "mapping":             mapping,
        "colonnes_manquantes": colonnes_manquantes,
        "stats":               segments["stats"],
        "nom_fichier":         fichier.name,
    }

    return segments, meta
