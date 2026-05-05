import pandas as pd


def kpi_generaux(df):
    revenu_total = df["montant_ht"].sum() if "montant_ht" in df.columns else 0
    marge_totale = df["marge_total"].sum() if "marge_total" in df.columns else 0
    volume_total = df["qte"].sum() if "qte" in df.columns else 0
    nb_transactions = len(df)
    marge_pct = (marge_totale / revenu_total * 100) if revenu_total != 0 else 0

    return {
        "revenu_total": revenu_total,
        "marge_totale": marge_totale,
        "marge_pct_globale": round(marge_pct, 2),
        "volume_total": volume_total,
        "nb_transactions": nb_transactions,
    }


def revenu_par_lob(df):
    if "lob" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    grp = df.groupby("lob").agg(
        revenu=("montant_ht", "sum"),
        marge=("marge_total", "sum"),
    ).reset_index()
    grp["marge_pct"] = (grp["marge"] / grp["revenu"] * 100).round(2)
    return grp.sort_values("revenu", ascending=False)


def revenu_par_segment(df):
    if "segment" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    grp = df.groupby("segment").agg(
        revenu=("montant_ht", "sum"),
        volume=("qte", "sum"),
        marge=("marge_total", "sum"),
    ).reset_index()
    grp["marge_pct"] = (grp["marge"] / grp["revenu"] * 100).round(2)
    return grp.sort_values("revenu", ascending=False)


def revenu_par_canal(df):
    if "canal" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    grp = df.groupby("canal").agg(
        revenu=("montant_ht", "sum"),
        marge=("marge_total", "sum"),
    ).reset_index()
    grp["marge_pct"] = (grp["marge"] / grp["revenu"] * 100).round(2)
    return grp.sort_values("revenu", ascending=False)


def tendance_mensuelle(df):
    if "mois" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    return df.groupby("mois").agg(
        revenu=("montant_ht", "sum"),
        volume=("qte", "sum"),
    ).reset_index().sort_values("mois")


def top_clients(df, n=10):
    if "tiers" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    cols = ["tiers"]
    if "raison_sociale" in df.columns:
        cols.append("raison_sociale")

    grp = df.groupby(cols).agg(
        revenu=("montant_ht", "sum"),
        marge=("marge_total", "sum"),
        nb_transactions=("montant_ht", "count"),
    ).reset_index()
    grp["marge_pct"] = (grp["marge"] / grp["revenu"] * 100).round(2)
    return grp.sort_values("revenu", ascending=False).head(n)


def marge_par_client_mensuelle(df):
    if not all(c in df.columns for c in ["tiers", "mois", "montant_ht", "marge_total"]):
        return pd.DataFrame()
    grp = df.groupby(["tiers", "mois"]).agg(
        revenu=("montant_ht", "sum"),
        marge=("marge_total", "sum"),
    ).reset_index()
    grp["marge_pct"] = (grp["marge"] / grp["revenu"] * 100).round(2)
    return grp
