import pandas as pd

REVENU_MIN_MENSUEL = 100_000  # RWF — exclure mois avec revenu < 100k (évite divisions aberrantes)
MARGE_PCT_MAX      = 500      # Cap : exclure % > 500 (valeurs impossibles)


def flag_marge_negative(df):
    if "marge_total" not in df.columns:
        return pd.DataFrame()
    mask = df["marge_total"] < 0
    cols = [c for c in ["num_piece","tiers","raison_sociale","segment","lob","montant_ht","cogs","marge_total","date"] if c in df.columns]
    return df[mask][cols].copy().sort_values("marge_total")


def flag_cogs_zero(df):
    if "cogs" not in df.columns or "montant_ht" not in df.columns:
        return pd.DataFrame()
    mask = (df["cogs"] == 0) & (df["montant_ht"] > 0)
    cols = [c for c in ["num_piece","tiers","raison_sociale","segment","montant_ht","cogs","date"] if c in df.columns]
    return df[mask][cols].copy()


def flag_doublons(df):
    if not all(c in df.columns for c in ["tiers","montant_ht"]):
        return pd.DataFrame()
    cols_dedup = ["tiers","montant_ht"] + (["date"] if "date" in df.columns else [])
    doublons = df[df.duplicated(subset=cols_dedup, keep=False)].copy()
    cols_aff = [c for c in ["num_piece","tiers","raison_sociale","montant_ht","date","segment"] if c in df.columns]
    return doublons[cols_aff].sort_values(cols_dedup)


def flag_concentration_client(df, seuil=0.50):
    if "tiers" not in df.columns or "montant_ht" not in df.columns:
        return {}
    revenu_total = df["montant_ht"].sum()
    if revenu_total == 0:
        return {}
    col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
    top3 = df.groupby(col_nom)["montant_ht"].sum().nlargest(3)
    pct_top3 = top3.sum() / revenu_total
    return {
        "top3": top3.reset_index().rename(columns={"montant_ht":"revenu", col_nom:"client"}),
        "pct_top3": round(pct_top3 * 100, 1),
        "flag": pct_top3 > seuil,
        "seuil": seuil * 100,
    }


def flag_marge_decroissante(df, nb_mois=2):
    """
    BUG 4 FIX:
    - Filtre les mois avec revenu < 100k RWF (évite divisions par quasi-zéro)
    - Cap les % aberrants > 500% (valeurs impossibles)
    """
    if not all(c in df.columns for c in ["tiers","mois","montant_ht","marge_total"]):
        return pd.DataFrame()

    grp = df.groupby(["tiers","mois"], dropna=False).agg(
        revenu=("montant_ht","sum"), marge=("marge_total","sum")
    ).reset_index()

    # BUG 4 FIX: exclure mois avec revenu trop faible
    grp = grp[grp["revenu"] >= REVENU_MIN_MENSUEL]

    grp["marge_pct"] = (grp["marge"] / grp["revenu"] * 100).round(2)

    # BUG 4 FIX: exclure % aberrants
    grp = grp[grp["marge_pct"].abs() <= MARGE_PCT_MAX]

    grp = grp.dropna(subset=["marge_pct"]).sort_values(["tiers","mois"])

    clients_flag = []
    for tiers, g in grp.groupby("tiers"):
        if len(g) < nb_mois + 1:
            continue
        marges = g["marge_pct"].values
        mois_l = g["mois"].values
        for i in range(len(marges) - nb_mois):
            fenetre = marges[i:i + nb_mois + 1]
            if all(fenetre[j] > fenetre[j+1] for j in range(nb_mois)):
                row = {"tiers": tiers, "mois_debut": mois_l[i], "mois_fin": mois_l[i+nb_mois]}
                for j in range(nb_mois+1):
                    row[f"marge_m{j}%"] = round(fenetre[j], 2)
                clients_flag.append(row)
                break

    return pd.DataFrame(clients_flag)


def resume_flags(df):
    return {
        "nb_marge_negative":     len(flag_marge_negative(df)),
        "nb_cogs_zero":          len(flag_cogs_zero(df)),
        "nb_doublons":           len(flag_doublons(df)),
        "concentration":         flag_concentration_client(df),
        "nb_marge_decroissante": len(flag_marge_decroissante(df)),
    }
