import pandas as pd


def kpi_generaux(df):
    revenu_total    = df["montant_ht"].sum()  if "montant_ht"  in df.columns else 0
    volume_total    = df["qte"].sum()         if "qte"         in df.columns else 0
    nb_transactions = len(df)

    # BUG 2 FIX: marge % calculée uniquement sur les lignes avec COGS > 0
    # (exclut les Frais de Passage où Marge = Montant HT = 100%)
    if "cogs" in df.columns and "marge_total" in df.columns and "montant_ht" in df.columns:
        df_cogs = df[df["cogs"] > 0]
        marge_totale  = df_cogs["marge_total"].sum()
        revenu_cogs   = df_cogs["montant_ht"].sum()
        marge_pct     = (marge_totale / revenu_cogs * 100) if revenu_cogs != 0 else 0
    else:
        marge_totale = df["marge_total"].sum() if "marge_total" in df.columns else 0
        marge_pct    = (marge_totale / revenu_total * 100) if revenu_total != 0 else 0

    return {
        "revenu_total":      revenu_total,
        "marge_totale":      marge_totale,
        "marge_pct_globale": round(marge_pct, 2),
        "volume_total":      volume_total,
        "nb_transactions":   nb_transactions,
    }


def revenu_par_lob(df):
    if "lob" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    out = df.groupby("lob", dropna=False).agg(
        revenu=("montant_ht","sum"), marge=("marge_total","sum")
    ).reset_index()
    out["marge_pct"] = (out["marge"] / out["revenu"].replace(0, pd.NA) * 100).round(2)
    return out.sort_values("revenu", ascending=False)


def revenu_par_segment(df):
    if "segment" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    out = df.groupby("segment", dropna=False).agg(
        revenu=("montant_ht","sum"), volume=("qte","sum"), marge=("marge_total","sum")
    ).reset_index()
    out["marge_pct"] = (out["marge"] / out["revenu"].replace(0, pd.NA) * 100).round(2)
    return out.sort_values("revenu", ascending=False)


def revenu_par_canal(df):
    if "canal" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    out = df.groupby("canal", dropna=False).agg(
        revenu=("montant_ht","sum"), marge=("marge_total","sum")
    ).reset_index()
    out["marge_pct"] = (out["marge"] / out["revenu"].replace(0, pd.NA) * 100).round(2)
    return out.sort_values("revenu", ascending=False)


def tendance_mensuelle(df):
    if "mois" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    out = df.groupby("mois").agg(
        revenu=("montant_ht","sum"), volume=("qte","sum")
    ).reset_index()
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
