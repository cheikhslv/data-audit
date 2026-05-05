# Audit Analytics — Oryx Energies Group

Outil d'automatisation de l'analyse pre-audit. Ingere un Flash Report Sage X3 et genere automatiquement les KPIs, graphiques et flags de risque.

## Installation

```bash
git clone https://github.com/cheikhslv/data-audit.git
cd data-audit
pip install -r requirements.txt
```

## Lancer l'outil

```bash
streamlit run app.py
```

Puis ouvrir http://localhost:8501 dans le navigateur.

## Structure du projet

```
data-audit/
├── app.py              # Dashboard Streamlit (point d'entrée)
├── requirements.txt
├── src/
│   ├── ingestion.py    # Upload + détection auto des colonnes
│   ├── kpis.py         # Calcul KPIs Revenue, Volume, Marge
│   ├── flags.py        # Détection des risques
│   └── export.py       # Export Excel des flags
└── data/               # Fichiers exemples (ne pas versionner les vraies données)
```

## Pages du dashboard

- **Vue générale** — KPIs globaux, tendance mensuelle, revenu par LOB et segment
- **Analyse clients** — Top 10, concentration, marge décroissante
- **Flags de risque** — Marge négative, COGS=0, doublons, concentration client + export Excel

## Formats acceptés

Fichier Excel (.xlsx) ou CSV exporté depuis Sage X3.
Séparateur CSV : point-virgule ou tabulation. Encodage : UTF-8 ou Latin-1.

## Colonnes Sage X3 reconnues automatiquement

| Colonne interne | Noms Sage X3 reconnus |
|---|---|
| date | Date comptable |
| tiers | Tiers, Code tiers |
| segment | Segment |
| lob | LOB |
| canal | Sales Channel |
| montant_ht | Montant HT |
| qte | Qte facturee |
| cogs | COGS |
| marge_total | Marge total |
| num_piece | Numero de piece |

## Prochaines etapes (V2)

- Integration API Sage X3 (remplace l'upload manuel)
- Extension multi-filiales avec sélecteur
- Score de risque global par filiale
