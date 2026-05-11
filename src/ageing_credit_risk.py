"""
Module Ageing Credit Risk — Oryx Energies Group
Analyse du risque crédit par client et par tranche d'ancienneté.

Structure du fichier source (Crystal Reports → .xls converti en .xlsx) :
  - 1 feuille par année (nommée "2024", "2025", "2026")
  - Ligne 0 : titre + société + date de référence
  - Ligne 1 : header colonnes
  - Lignes 2..N-2 : données clients
  - Avant-dernière ligne : ligne TOTAL (à exclure)
  - Dernière ligne : "Page 1 de 1" (à exclure)

Colonnes :
  A=Entité  B=CUK code  C=Code Client  D=Nom Client  E=LOB  F=Groupe
  G=Terme paiement  H=Courant  I=0-30  J=31-60  K=61-90  L=91-120
  M=121-180  N=>=180  O=Balance Totale  P=Limite Credit  Q=Excès
  R=Provisions  S=Type Sécurité  T=Montant Sécurité  U=Date Expiration
"""

import pandas as pd
import subprocess
import zipfile
import io
import re
import tempfile
import os
from lxml import etree

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TRANCHES = ["Courant", "0-30", "31-60", "61-90", "91-120", "121-180", ">=180"]

# Mapping lettre colonne → nom interne
COL_MAP = {
    "A": "entite",
    "B": "cuk_code",
    "C": "code_client",
    "D": "nom_client",
    "E": "lob",
    "F": "groupe",
    "G": "terme_paiement",
    "H": "courant",
    "I": "j0_30",
    "J": "j31_60",
    "K": "j61_90",
    "L": "j91_120",
    "M": "j121_180",
    "N": "j180_plus",
    "O": "balance_totale",
    "P": "limite_credit",
    "Q": "exces",
    "R": "provisions",
    "S": "type_securite",
    "T": "montant_securite",
    "U": "date_expiration",
}

COLS_TRANCHES = ["courant", "j0_30", "j31_60", "j61_90", "j91_120", "j121_180", "j180_plus"]
COLS_NUMERIQUES = COLS_TRANCHES + ["balance_totale", "limite_credit", "montant_securite", "provisions"]

EXCEL_EPOCH = pd.Timestamp("1899-12-30")

# Seuils flags
SEUIL_OVERDUE_PCT    = 0.30   # >30% de la balance en overdue = flag orange
SEUIL_OVERDUE_GRAVE  = 0.50   # >50% en 91+ jours = flag rouge
SEUIL_BALANCE_NEG    = 0      # balance négative = flag
SEUIL_EXCES_CREDIT   = True   # client avec "Excess" dans colonne Q


# ---------------------------------------------------------------------------
# Lecture fichier XLS (Crystal Reports / Sage)
# ---------------------------------------------------------------------------
def _convert_xls_to_xlsx(contenu_bytes):
    import xlrd, openpyxl
    wb_in = xlrd.open_workbook(file_contents=contenu_bytes)
    out = io.BytesIO()
    wb_out = openpyxl.Workbook()
    wb_out.remove(wb_out.active)
    for sh in wb_in.sheets():
        ws = wb_out.create_sheet(sh.name)
        for i in range(sh.nrows):
            ws.append([sh.cell_value(i, j) for j in range(sh.ncols)])
    wb_out.save(out)
    return out.getvalue()


def _lire_feuille(z: zipfile.ZipFile, sheet_path: str, strings: list, ns: str) -> list[dict]:
    """Lit une feuille XML et retourne une liste de dicts {lettre: valeur}."""
    with z.open(sheet_path) as f:
        sheet = etree.parse(f)
    rows = sheet.findall(f".//{{{ns}}}row")
    data = []
    for row in rows:
        rd = {}
        for c in row.findall(f"{{{ns}}}c"):
            ref = c.get("r", "")
            letters = _col_letters(ref)
            if not letters:
                continue
            t = c.get("t", "")
            v_el = c.find(f"{{{ns}}}v")
            v = v_el.text if v_el is not None else None
            if t == "s" and v is not None:
                rd[letters] = strings[int(v)]
            elif v is not None:
                try:
                    rd[letters] = float(v)
                except Exception:
                    rd[letters] = v
            else:
                rd[letters] = None
        if rd:
            data.append(rd)
    return data


def _parser_feuille(rows_raw: list[dict]) -> tuple[pd.DataFrame, dict]:
    """
    Parse les lignes brutes d'une feuille Ageing :
    - Extrait les métadonnées (société, date référence)
    - Ignore header, totaux, pied de page
    - Retourne (df_clients, meta)
    """
    if len(rows_raw) < 3:
        return pd.DataFrame(), {}

    # Ligne 0 = titre + meta
    meta_row = rows_raw[0]
    societe       = meta_row.get("D", "")
    date_ref_raw  = meta_row.get("G")
    date_ref = None
    if date_ref_raw and isinstance(date_ref_raw, (float, int)):
        date_ref = EXCEL_EPOCH + pd.Timedelta(days=int(date_ref_raw))

    meta = {
        "societe":   societe,
        "date_ref":  date_ref,
        "date_ref_str": date_ref.strftime("%d/%m/%Y") if date_ref else "N/A",
    }

    # Ligne 1 = header (ignorée — on utilise COL_MAP directement)
    # Lignes 2..fin = données + TOTAL + pied de page
    data_rows = rows_raw[2:]

    records = []
    for rd in data_rows:
        # Exclure ligne TOTAL (colonne C = "TOTAL ")
        if str(rd.get("C", "")).strip().upper().startswith("TOTAL"):
            continue
        # Exclure pied de page (colonne A = "Page...")
        if str(rd.get("A", "")).strip().lower().startswith("page"):
            continue
        # Exclure lignes vides
        if not rd.get("D"):
            continue

        record = {}
        for col_letter, col_name in COL_MAP.items():
            record[col_name] = rd.get(col_letter)
        records.append(record)

    if not records:
        return pd.DataFrame(), meta

    df = pd.DataFrame(records)

    # Nettoyage types
    for col in COLS_NUMERIQUES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Exces : normaliser en booléen
    if "exces" in df.columns:
        df["exces_bool"] = df["exces"].astype(str).str.strip().str.lower() == "excess"
    else:
        df["exces_bool"] = False

    # Strings
    for col in ["nom_client", "lob", "groupe", "terme_paiement",
                "type_securite", "entite", "code_client", "cuk_code"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})

    # Date expiration sécurité
    if "date_expiration" in df.columns:
        df["date_expiration"] = df["date_expiration"].apply(
            lambda v: EXCEL_EPOCH + pd.Timedelta(days=int(v))
            if pd.notna(v) and isinstance(v, (float, int)) and v > 0 else pd.NaT
        )

    # Calcul colonnes dérivées utiles pour l'analyse
    # Total overdue = tout sauf "Courant"
    df["total_overdue"] = df[["j0_30","j31_60","j61_90","j91_120","j121_180","j180_plus"]].sum(axis=1)
    # Total 91+ jours (risque grave)
    df["total_91_plus"] = df[["j91_120","j121_180","j180_plus"]].sum(axis=1)
    # % overdue sur balance totale
    df["pct_overdue"] = df.apply(
        lambda r: r["total_overdue"] / r["balance_totale"] * 100
        if r["balance_totale"] != 0 else 0, axis=1
    ).round(1)
    # % 91+ sur balance
    df["pct_91_plus"] = df.apply(
        lambda r: r["total_91_plus"] / r["balance_totale"] * 100
        if r["balance_totale"] != 0 else 0, axis=1
    ).round(1)
    # Utilisation limite crédit
    df["utilisation_credit_pct"] = df.apply(
        lambda r: r["balance_totale"] / r["limite_credit"] * 100
        if r.get("limite_credit", 0) and r["limite_credit"] > 0 else None, axis=1
    )

    return df.reset_index(drop=True), meta


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def _rows_to_dicts(rows_list):
    result = []
    for row in rows_list:
        rd = {}
        for j, val in enumerate(row):
            idx = j
            letters = ''
            while True:
                letters = chr(65 + idx % 26) + letters
                idx = idx // 26 - 1
                if idx < 0:
                    break
            rd[letters] = val if val != '' else None
        result.append(rd)
    return result

def charger_ageing(fichier) -> dict:
    import xlrd
    nom = fichier.name.lower()
    contenu = fichier.read()
    resultats = {}
    wb = xlrd.open_workbook(file_contents=contenu)
    for sh in wb.sheets():
        if sh.name in ('', 'Sheet1', 'Sheet2', 'Sheet3'):
            continue
        rows_list = []
        for i in range(sh.nrows):
            row = []
            for j in range(sh.ncols):
                cell = sh.cell(i, j)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    row.append(xlrd.xldate_as_datetime(cell.value, wb.datemode))
                elif cell.ctype == xlrd.XL_CELL_EMPTY:
                    row.append(None)
                else:
                    row.append(cell.value)
            rows_list.append(row)
        rows_raw = _rows_to_dicts(rows_list)
        df, meta = _parser_feuille(rows_raw)
        if not df.empty:
            resultats[sh.name] = {'df': df, 'meta': meta}
    resultats['annees'] = sorted(k for k in resultats.keys() if k != 'annees')
    return resultats

# ---------------------------------------------------------------------------
# KPIs Ageing
# ---------------------------------------------------------------------------

def kpi_ageing(df: pd.DataFrame) -> dict:
    """KPIs principaux d'un rapport Ageing."""
    nb_clients       = len(df)
    balance_totale   = df["balance_totale"].sum()
    total_overdue    = df["total_overdue"].sum()
    total_91_plus    = df["total_91_plus"].sum()
    nb_excess        = df["exces_bool"].sum() if "exces_bool" in df.columns else 0
    balance_negative = df[df["balance_totale"] < 0]["balance_totale"].sum()
    nb_neg           = (df["balance_totale"] < 0).sum()

    pct_overdue   = total_overdue / balance_totale * 100 if balance_totale else 0
    pct_91_plus   = total_91_plus / balance_totale * 100 if balance_totale else 0

    return {
        "nb_clients":       nb_clients,
        "balance_totale":   balance_totale,
        "total_overdue":    total_overdue,
        "total_91_plus":    total_91_plus,
        "pct_overdue":      round(pct_overdue, 1),
        "pct_91_plus":      round(pct_91_plus, 1),
        "nb_excess":        int(nb_excess),
        "balance_negative": balance_negative,
        "nb_neg":           int(nb_neg),
    }


def ageing_par_lob(df: pd.DataFrame) -> pd.DataFrame:
    """Balance et overdue par LOB."""
    if "lob" not in df.columns:
        return pd.DataFrame()
    grp = df.groupby("lob").agg(
        nb_clients=("nom_client", "count"),
        balance=("balance_totale", "sum"),
        overdue=("total_overdue", "sum"),
        j91_plus=("total_91_plus", "sum"),
    ).reset_index()
    grp["pct_overdue"] = (grp["overdue"] / grp["balance"].replace(0, pd.NA) * 100).round(1)
    grp["pct_91_plus"] = (grp["j91_plus"] / grp["balance"].replace(0, pd.NA) * 100).round(1)
    return grp.sort_values("balance", ascending=False)


def ageing_par_tranche(df: pd.DataFrame) -> pd.DataFrame:
    """Distribution de la balance par tranche d'ancienneté."""
    tranches = {
        "Courant":   df["courant"].sum(),
        "0-30 j":    df["j0_30"].sum(),
        "31-60 j":   df["j31_60"].sum(),
        "61-90 j":   df["j61_90"].sum(),
        "91-120 j":  df["j91_120"].sum(),
        "121-180 j": df["j121_180"].sum(),
        "≥180 j":    df["j180_plus"].sum(),
    }
    total = sum(tranches.values())
    rows = [
        {"tranche": k, "montant": v,
         "pct": round(v / total * 100, 1) if total else 0}
        for k, v in tranches.items()
    ]
    return pd.DataFrame(rows)


def top_clients_risque(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top N clients par balance totale avec détail risque."""
    cols = ["nom_client", "lob", "terme_paiement", "balance_totale",
            "total_overdue", "total_91_plus", "pct_overdue", "pct_91_plus",
            "limite_credit", "exces_bool", "type_securite", "montant_securite"]
    cols = [c for c in cols if c in df.columns]
    return df[cols].sort_values("balance_totale", ascending=False).head(n)


# ---------------------------------------------------------------------------
# FLAGS de risque Ageing
# ---------------------------------------------------------------------------

def flag_overdue_critique(df: pd.DataFrame) -> pd.DataFrame:
    """Clients avec >50% de leur balance en 91+ jours."""
    mask = (df["balance_totale"] > 0) & (df["pct_91_plus"] > 50)
    cols = ["nom_client", "lob", "balance_totale", "total_91_plus",
            "pct_91_plus", "j91_120", "j121_180", "j180_plus", "terme_paiement"]
    cols = [c for c in cols if c in df.columns]
    return df[mask][cols].sort_values("total_91_plus", ascending=False)


def flag_depassement_credit(df: pd.DataFrame) -> pd.DataFrame:
    """Clients ayant dépassé leur limite de crédit."""
    mask = df.get("exces_bool", pd.Series([False]*len(df)))
    cols = ["nom_client", "lob", "balance_totale", "limite_credit",
            "utilisation_credit_pct", "total_overdue", "type_securite", "montant_securite"]
    cols = [c for c in cols if c in df.columns]
    return df[mask][cols].sort_values("balance_totale", ascending=False)


def flag_balance_negative(df: pd.DataFrame) -> pd.DataFrame:
    """Clients avec balance totale négative (avoirs non imputés / trop-perçus)."""
    mask = df["balance_totale"] < 0
    cols = ["nom_client", "lob", "balance_totale", "courant",
            "j0_30", "total_overdue", "terme_paiement"]
    cols = [c for c in cols if c in df.columns]
    return df[mask][cols].sort_values("balance_totale")


def flag_180_plus(df: pd.DataFrame) -> pd.DataFrame:
    """Clients avec créances ≥ 180 jours (risque de perte)."""
    mask = df["j180_plus"] > 0
    cols = ["nom_client", "lob", "j180_plus", "balance_totale",
            "pct_91_plus", "type_securite", "montant_securite", "provisions"]
    cols = [c for c in cols if c in df.columns]
    return df[mask][cols].sort_values("j180_plus", ascending=False)


def flag_securite_expiree(df: pd.DataFrame, date_ref: pd.Timestamp = None) -> pd.DataFrame:
    """Clients avec garantie expirée ou absente alors qu'ils ont une limite de crédit."""
    if "date_expiration" not in df.columns:
        return pd.DataFrame()
    ref = date_ref or pd.Timestamp.now()
    mask = (
        df["limite_credit"].fillna(0) > 0
    ) & (
        df["montant_securite"].fillna(0) > 0
    ) & (
        df["date_expiration"].notna()
    ) & (
        df["date_expiration"] < ref
    )
    cols = ["nom_client", "lob", "limite_credit", "balance_totale",
            "type_securite", "montant_securite", "date_expiration"]
    cols = [c for c in cols if c in df.columns]
    return df[mask][cols].sort_values("date_expiration")


def resume_flags_ageing(df: pd.DataFrame, date_ref: pd.Timestamp = None) -> dict:
    """Résumé de tous les flags Ageing."""
    return {
        "nb_overdue_critique":     len(flag_overdue_critique(df)),
        "nb_depassement_credit":   len(flag_depassement_credit(df)),
        "nb_balance_negative":     len(flag_balance_negative(df)),
        "nb_180_plus":             len(flag_180_plus(df)),
        "nb_securite_expiree":     len(flag_securite_expiree(df, date_ref)),
    }

