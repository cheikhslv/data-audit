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
    Parseur XML robuste pour fichiers Sage X3 (stylesheet corrompue).
    - Lit toujours la feuille Sage.X3.DS. (sheet2.xml)
    - Lit les cellules par référence de colonne (pas par position)
    - Ignore les lignes cachées (totaux)
    """
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

    with zipfile.ZipFile(io.BytesIO(contenu_bytes)) as z:
        # Shared strings
        with z.open("xl/sharedStrings.xml") as f:
            shared_root = etree.parse(f)
        strings = []
        for si in shared_root.findall(f"{{{ns}}}si"):
            texts = si.findall(f".//{{{ns}}}t")
            strings.append("".join(t.text or "" for t in texts))

        # Trouver la feuille Sage.X3.DS. via workbook.xml + rels
        target_sheet = "xl/worksheets/sheet2.xml"  # défaut fiable
        try:
            with z.open("xl/workbook.xml") as f:
                wb = etree.parse(f)
            rels_map = {}
            with z.open("xl/_rels/workbook.xml.rels") as f:
                rels_xml = etree.parse(f)
            for r in rels_xml.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                rels_map[r.get('Id')] = r.get('Target')
            for s in wb.findall(f".//{{{ns}}}sheet"):
                name = s.get('name', '')
                if 'DS' in name or ('Sage' in name and 'Reserved' not in name):
                    rid = s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    target = rels_map.get(rid, '')
                    if target:
                        target_sheet = f"xl/{target}"
                        break
        except Exception:
            pass

        # Lire la feuille de données
        if target_sheet not in z.namelist():
            target_sheet = "xl/worksheets/sheet2.xml"

        with z.open(target_sheet) as f:
            sheet = etree.parse(f)

        rows = sheet.findall(f".//{{{ns}}}row")
        if len(rows) < 2:
            return None

        # Header — lire par référence de colonne
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

        # Données — lire par référence de colonne (correction bug décalage)
        data = []
        for row in rows[1:]:
            if row.get('hidden') == '1':  # ignorer lignes cachées (totaux)
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
        df["segment"] = df["segment"].replace(
            {"": "Non défini", "nan": "Non défini", "None": "Non défini"}
        )

    # Strings
    for c in ["tiers", "raison_sociale", "num_piece", "article", "designation", "mvt_stock"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # Filtre SINV uniquement
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
            # 1. openpyxl (fichiers normaux)
            try:
                df_raw = pd.read_excel(io.BytesIO(contenu), engine="openpyxl")
            except Exception:
                # 2. Parseur XML custom (Sage X3 stylesheet corrompue)
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

    colonnes_manquantes = [
        k for k in ["date", "tiers", "montant_ht", "marge_total", "cogs"]
        if k not in mapping
    ]

    try:
        df_clean = nettoyer_df(df_raw, mapping)
    except Exception as e:
        st.error(f"Erreur nettoyage : {e}")
        return None, {}

    # Compter avoirs pour info sidebar
    tf_col = next((c for c in df_raw.columns if "type" in c.lower() and "facture" in c.lower()), None)
    nb_avoirs = 0
    if tf_col:
        nb_avoirs = len(df_raw[df_raw[tf_col].astype(str).str.strip() == "CRM"])

    return df_clean, {
        "mapping": mapping,
        "colonnes_manquantes": colonnes_manquantes,
        "nb_lignes": len(df_clean),
        "nb_avoirs": nb_avoirs,
    }
