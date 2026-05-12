"""
Module d'analyse multi-années pour la comparaison YoY.
"""
import pandas as pd
import re


def detecter_annee(nom_fichier: str) -> str:
    """Détecte l'année depuis le nom du fichier Sage X3.
    Ex: Requêteur ZFLD RW01 010124 au 311224.xlsx -> 2024
        Requêteur_ZFLD_RW01_010126_au_210426.xlsx -> 2026
    Les dates sont au format JJMMAA (6 chiffres).
    """
    # Chercher après " au " ou "_au_" : les 2 derniers chiffres = année sur 2 digits
    m = re.search(r'[\s_]au[\s_]\d{4}(\d{2})', nom_fichier, re.IGNORECASE)
    if m:
        yr = int(m.group(1))
        if 0 <= yr <= 99:
            return str(2000 + yr)

    # Chercher la date de fin : 6 chiffres juste avant l'extension
    m2 = re.search(r'(\d{6})(?:\.\w+)?$', nom_fichier)
    if m2:
        yr = int(m2.group(1)[-2:])
        if 0 <= yr <= 99:
            return str(2000 + yr)

    # Chercher un bloc de 6 chiffres séparé par espace ou underscore
    m3 = re.search(r'[\s_](\d{6})[\s_]', nom_fichier)
    if m3:
        yr = int(m3.group(1)[-2:])
        if 0 <= yr <= 99:
            return str(2000 + yr)

    # Fallback : chercher un entier 4 chiffres entre 2000 et 2099
    for tok in re.findall(r'\d{4}', nom_fichier):
        if 2000 <= int(tok) <= 2099:
            return tok

    return "Inconnu"


def nb_mois_fichier(df: pd.DataFrame) -> int:
    """Nombre de mois distincts dans le fichier."""
    if "mois" not in df.columns:
        return 12
    mois = df["mois"].dropna().unique()
    return len([m for m in mois if m != "NaT"])


def kpi_annee(df: pd.DataFrame, annee: str) -> dict:
    """KPIs principaux pour une année."""
    revenu = df["montant_ht"].sum() if "montant_ht" in df.columns else 0
    volume = df["qte"].sum() if "qte" in df.columns else 0
    nb_tx  = len(df)
    nb_mois = nb_mois_fichier(df)

    # Marge COGS>0
    if all(c in df.columns for c in ["cogs","marge_total","montant_ht"]):
        cogs_ok = df[df["cogs"] > 0]
        rev_cogs = cogs_ok["montant_ht"].sum()
        marge_pct = (cogs_ok["marge_total"].sum() / rev_cogs * 100) if rev_cogs > 0 else 0
    else:
        marge_pct = 0

    return {
        "annee":    annee,
        "revenu":   revenu,
        "volume":   volume,
        "nb_tx":    nb_tx,
        "marge_pct": round(marge_pct, 2),
        "nb_mois":  nb_mois,
        "annualise": nb_mois < 12,
    }


def yoy_par_lob(dfs: dict) -> pd.DataFrame:
    """Revenu par LOB par année."""
    rows = []
    for annee, df in dfs.items():
        if "lob" not in df.columns or "montant_ht" not in df.columns:
            continue
        grp = df.groupby("lob")["montant_ht"].sum().reset_index()
        grp["annee"] = annee
        rows.append(grp)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    out = out[out["lob"] != "Autre"]
    return out.pivot(index="lob", columns="annee", values="montant_ht").fillna(0).reset_index()


def yoy_par_segment(dfs: dict) -> pd.DataFrame:
    """Volume par segment par année."""
    rows = []
    for annee, df in dfs.items():
        if "segment" not in df.columns or "qte" not in df.columns:
            continue
        grp = df.groupby("segment")["qte"].sum().reset_index()
        grp["annee"] = annee
        rows.append(grp)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    out = out[out["segment"] != "Non défini"]
    return out.pivot(index="segment", columns="annee", values="qte").fillna(0).reset_index()


def evolution_clients(df_ref: pd.DataFrame, df_cmp: pd.DataFrame,
                      annee_ref: str, annee_cmp: str) -> dict:
    """Analyse évolution clients entre 2 années."""
    if "tiers" not in df_ref.columns or "tiers" not in df_cmp.columns:
        return {}

    col_nom = "raison_sociale" if "raison_sociale" in df_ref.columns else "tiers"

    def rev_client(df):
        return df.groupby([col_nom])["montant_ht"].sum().reset_index()

    ref = rev_client(df_ref).rename(columns={"montant_ht": f"rev_{annee_ref}"})
    cmp = rev_client(df_cmp).rename(columns={"montant_ht": f"rev_{annee_cmp}"})

    merged = ref.merge(cmp, on=col_nom, how="outer").fillna(0)
    merged["evol_pct"] = ((merged[f"rev_{annee_cmp}"] - merged[f"rev_{annee_ref}"]) /
                           merged[f"rev_{annee_ref}"].replace(0, pd.NA) * 100).round(1)

    nouveaux  = merged[merged[f"rev_{annee_ref}"] == 0].copy()
    disparus  = merged[merged[f"rev_{annee_cmp}"] == 0].copy()
    croissants = merged[
        (merged[f"rev_{annee_ref}"] > 0) & (merged["evol_pct"] >= 50)
    ].sort_values("evol_pct", ascending=False)
    en_baisse = merged[
        (merged[f"rev_{annee_ref}"] > 0) & (merged["evol_pct"] <= -30)
    ].sort_values("evol_pct")

    return {
        "nouveaux":   nouveaux,
        "disparus":   disparus,
        "croissants": croissants,
        "en_baisse":  en_baisse,
        "merged":     merged,
    }


def analyse_frais_passage(dfs: dict) -> pd.DataFrame:
    """Clients avec marge > 90% (Frais de Passage / COGS=0)."""
    rows = []
    for annee, df in dfs.items():
        if not all(c in df.columns for c in ["montant_ht","cogs","marge_total"]):
            continue
        col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
        grp = df.groupby(col_nom).agg(
            revenu=("montant_ht","sum"),
            cogs=("cogs","sum"),
            marge=("marge_total","sum"),
        ).reset_index()
        grp["marge_pct"] = (grp["marge"] / grp["revenu"].replace(0, pd.NA) * 100).round(1)
        fp = grp[grp["marge_pct"] >= 90].copy()
        fp["annee"] = annee
        rows.append(fp)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(["annee","revenu"], ascending=[True,False])


def analyse_expor(dfs: dict) -> dict:
    """Analyse du canal EXPOR."""
    rows_rev = []
    rows_cli = []
    for annee, df in dfs.items():
        if "canal" not in df.columns:
            continue
        expor = df[df["canal"] == "EXPOR"].copy()
        if expor.empty:
            continue

        rev_total = df["montant_ht"].sum()
        rev_expor = expor["montant_ht"].sum()
        rows_rev.append({
            "annee": annee,
            "revenu_expor": rev_expor,
            "pct_total": round(rev_expor / rev_total * 100, 1) if rev_total > 0 else 0,
        })

        col_nom = "raison_sociale" if "raison_sociale" in expor.columns else "tiers"
        cli = expor.groupby(col_nom).agg(
            revenu=("montant_ht","sum"), marge=("marge_total","sum")
        ).reset_index()
        cli["marge_pct"] = (cli["marge"] / cli["revenu"].replace(0,pd.NA) * 100).round(1)
        cli["annee"] = annee
        rows_cli.append(cli)

    return {
        "revenu_par_annee": pd.DataFrame(rows_rev),
        "clients": pd.concat(rows_cli, ignore_index=True) if rows_cli else pd.DataFrame(),
    }
