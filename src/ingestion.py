import pandas as pd
import streamlit as st
import zipfile
import io
import re
from lxml import etree

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
}

LOB_VALIDES   = {"B2B","B2C","LUB","LPG","INDUS","DODO","DISTR","COMM","WHOSA","EXPOR","CODO","DOMES","AGRI"}
CANAL_VALIDES = {"DISTR","DODO","INDUS","EXPOR","CODO","COMM","WHOSA","DOMES","AGRI"}
SINV_TYPES    = {"SINV"}
EXCEL_EPOCH   = pd.Timestamp("1899-12-30")


def serial_to_date(val):
    try:
        n = float(val)
        if 30000 < n < 60000:
            return EXCEL_EPOCH + pd.Timedelta(days=int(n))
        return pd.NaT
    except Exception:
        return pd.NaT


def col_letters(cell_ref):
    """Extraire les lettres de colonne d'une référence de cellule ex: 'AB12' -> 'AB'"""
    return re.match(r'([A-Z]+)', cell_ref).group(1)


def detecter_colonne(df_cols, noms_possibles):
    df_cols_lower = [c.lower().strip() for c in df_cols]
    for nom in noms_possibles:
        for i, col in enumerate(df_cols_lower):
            if col == nom or nom in col:
                return df_cols[i]
    return None


def lire_xlsx_sage(contenu_bytes):
    """
    Parseur XML robuste pour les fichiers Sage X3 avec stylesheet corrompu.
    CORRECTION BUG 1: lecture par référence de colonne (pas par position)
    pour éviter le décalage quand des cellules sont vides.
    """
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

    with zipfile.ZipFile(io.BytesIO(contenu_bytes)) as z:
        # Lire les shared strings
        with z.open("xl/sharedStrings.xml") as f:
            shared_root = etree.parse(f)
        strings = []
        for si in shared_root.findall(f"{{{ns}}}si"):
            texts = si.findall(f".//{{{ns}}}t")
            strings.append("".join(t.text or "" for t in texts))

        # Trouver la feuille de données (Sage.X3.DS. = sheet2.xml via workbook.xml)
        try:
            with z.open("xl/workbook.xml") as f:
                wb = etree.parse(f)
            # Chercher la feuille "Sage.X3.DS."
            rels_map = {}
            with z.open("xl/_rels/workbook.xml.rels") as f:
                rels = etree.parse(f)
            for r in rels.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                rels_map[r.get('Id')] = r.get('Target')

            target_sheet = None
            for s in wb.findall(f".//{{{ns}}}sheet"):
                if "DS" in s.get('name', '') or "Sage" in s.get('name', ''):
                    rid = s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    target = rels_map.get(rid, '')
                    if target:
                        target_sheet = f"xl/{target}" if not target.startswith('xl/') else target
                        break
        except Exception:
            target_sheet = None

        # Lister toutes les feuilles disponibles
        available_sheets = sorted([f for f in z.namelist() if "worksheets/sheet" in f])

        # Essayer d'abord la feuille cible, sinon essayer toutes
        sheets_to_try = []
        if target_sheet and target_sheet in z.namelist():
            sheets_to_try.append(target_sheet)
        sheets_to_try.extend([s for s in available_sheets if s != target_sheet])

        for sheet_file in sheets_to_try:
            with z.open(sheet_file) as f:
                sheet = etree.parse(f)

            rows = sheet.findall(f".//{{{ns}}}row")
            if len(rows) < 5:
                continue

            # Lire le header avec positions de colonnes exactes
            header_row = rows[0]
            col_map = {}  # lettre -> nom colonne
            for c in header_row.findall(f"{{{ns}}}c"):
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
                continue

            # Lire les données avec référence de colonne explicite (CORRECTION BUG 1)
            data = []
            for row in rows[1:]:
                # Ignorer les lignes cachées (ex: ligne de total en bas)
                if row.get('hidden') == '1':
                    continue
                row_data = {}
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
                        row_data[col_name] = strings[int(v)]
                    elif v is not None:
                        try:
                            row_data[col_name] = float(v)
                        except Exception:
                            row_data[col_name] = v
                    else:
                        row_data[col_name] = None
                data.append(row_data)

            if len(data) > 10:
                return pd.DataFrame(data)

    return None


def nettoyer_df(df_raw, mapping):
    df = pd.DataFrame()
    for cle, col in mapping.items():
        df[cle] = df_raw[col].copy()

    # Type facture
    if "type_facture" in df.columns:
        df["type_facture"] = df["type_facture"].astype(str).str.strip()
    else:
        df["type_facture"] = "SINV"

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
        df["segment"] = df["segment"].replace({"": "Non défini", "nan": "Non défini", "None": "Non défini"})

    # Strings
    for c in ["tiers", "raison_sociale", "num_piece", "article", "designation", "mvt_stock"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # FILTRE : SINV uniquement
    df = df[df["type_facture"].isin(SINV_TYPES)].copy()

    # Supprimer lignes montant = 0
    if "montant_ht" in df.columns:
        df = df[df["montant_ht"] != 0].copy()

    return df.reset_index(drop=True)


def charger_fichier(fichier):
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
            # 1. Essayer openpyxl (fichiers normaux)
            try:
                df_raw = pd.read_excel(io.BytesIO(contenu), engine="openpyxl")
            except Exception:
                # 2. Fallback: parseur XML custom corrigé (Sage X3 avec stylesheet corrompu)
                df_raw = lire_xlsx_sage(contenu)

    except Exception as e:
        st.error(f"Erreur lecture fichier : {e}")
        return None, {}

    if df_raw is None or df_raw.empty:
        st.error("Impossible de lire le fichier.")
        return None, {}

    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    mapping = {}
    for cle, noms in COLONNES_ATTENDUES.items():
        col = detecter_colonne(list(df_raw.columns), noms)
        if col:
            mapping[cle] = col

    colonnes_manquantes = [k for k in ["date", "tiers", "montant_ht", "marge_total", "cogs"] if k not in mapping]

    try:
        df_clean = nettoyer_df(df_raw, mapping)
    except Exception as e:
        st.error(f"Erreur nettoyage : {e}")
        return None, {}

    nb_total = len(df_raw)
    nb_sinv  = len(df_clean)
    nb_avoirs = len(df_raw[df_raw.get("Type facture", pd.Series(dtype=str)).astype(str).str.strip() == "CRM"]) if "Type facture" in df_raw.columns else 0

    return df_clean, {
        "mapping": mapping,
        "colonnes_manquantes": colonnes_manquantes,
        "nb_lignes": nb_sinv,
        "nb_total_raw": nb_total,
        "nb_avoirs": nb_avoirs,
    }
