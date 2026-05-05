import pandas as pd


def kpi_generaux(df):
    revenu_total  = df["montant_ht"].sum()   if "montant_ht"   in df.columns else 0
    marge_totale  = df["marge_total"].sum()  if "marge_total"  in df.columns else 0
    volume_total  = df["qte"].sum()          if "qte"          in df.columns else 0
    nb_transactions = len(df)
    marge_pct = (marge_totale / revenu_total * 100) if revenu_total != 0 else 0
    return {
        "revenu_total":      revenu_total,
        "marge_totale":      marge_totale,
        "marge_pct_globale": round(marge_pct, 2),
        "volume_total":      volume_total,
        "nb_transactions":   nb_transactions,
    }


def _grp(df, col_group, col_val="montant_ht"):
    if col_group not in df.columns or col_val not in df.columns:
        return pd.DataFrame()
    return df.groupby(col_group, dropna=False)


def revenu_par_lob(df):
    grp = _grp(df, "lob")
    if grp is None or isinstance(grp, pd.DataFrame):
        return pd.DataFrame()
    out = grp.agg(revenu=("montant_ht","sum"), marge=("marge_total","sum")).reset_index()
    out["marge_pct"] = (out["marge"] / out["revenu"].replace(0, pd.NA) * 100).round(2)
    return out.sort_values("revenu", ascending=False)


def revenu_par_segment(df):
    grp = _grp(df, "segment")
    if grp is None or isinstance(grp, pd.DataFrame):
        return pd.DataFrame()
    out = grp.agg(revenu=("montant_ht","sum"), volume=("qte","sum"), marge=("marge_total","sum")).reset_index()
    out["marge_pct"] = (out["marge"] / out["revenu"].replace(0, pd.NA) * 100).round(2)
    return out.sort_values("revenu", ascending=False)


def revenu_par_canal(df):
    grp = _grp(df, "canal")
    if grp is None or isinstance(grp, pd.DataFrame):
        return pd.DataFrame()
    out = grp.agg(revenu=("montant_ht","sum"), marge=("marge_total","sum")).reset_index()
    out["marge_pct"] = (out["marge"] / out["revenu"].replace(0, pd.NA) * 100).round(2)
    return out.sort_values("revenu", ascending=False)


def tendance_mensuelle(df):
    if "mois" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    out = df.groupby("mois").agg(revenu=("montant_ht","sum"), volume=("qte","sum")).reset_index()
    out = out[out["mois"].notna() & (out["mois"] != "NaT")].sort_values("mois")
    return out


def top_clients(df, n=10):
    if "tiers" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    cols = ["tiers"] + (["raison_sociale"] if "raison_sociale" in df.columns else [])
    out = df.groupby(cols, dropna=False).agg(
        revenu=("montant_ht","sum"),
        marge=("marge_total","sum"),
        nb_transactions=("montant_ht","count"),
    ).reset_index()
    out["marge_pct"] = (out["marge"] / out["revenu"].replace(0, pd.NA) * 100).round(2)
    return out.sort_values("revenu", ascending=False).head(n)


def marge_par_client_mensuelle(df):
    if not all(c in df.columns for c in ["tiers","mois","montant_ht","marge_total"]):
        return pd.DataFrame()
    out = df.groupby(["tiers","mois"], dropna=False).agg(
        revenu=("montant_ht","sum"), marge=("marge_total","sum")
    ).reset_index()
    out["marge_pct"] = (out["marge"] / out["revenu"].replace(0, pd.NA) * 100).round(2)
    return out
