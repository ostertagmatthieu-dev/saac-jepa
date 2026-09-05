# Figures article — style Meta AI / FAIR (langage visuel I-JEPA / V-JEPA)

Sources TikZ autonomes (`\documentclass[tikz]{standalone}`), compilables avec pdflatex
(Overleaf : glisser le dossier tel quel ; localement : TinyTeX suffit).

| Fichier | Contenu | Usage suggéré |
|---|---|---|
| `fig1_saacjepa_architecture.tex` | Architecture SAAC-JEPA complète : grilles de capteurs (canaux masqués), encodeur contexte, prédicteur causal conditionné par les actions, encodeur cible EMA (pointillés), pertes, marque stop-gradient | Figure 1 du papier |
| `fig2_schema_consistency.tex` | Les deux mécanismes du gagnant M03 : schema-consistency (vue complète vs amputée, encodeur partagé, pénalité sur latents) + action-recovery | Section méthode |
| `fig3_selection_pipeline.tex` | Pipeline de sélection anti-fuite : 20 candidats → composite → top-5 → refus de lock (instabilité) → seeds 6-7 → lock SHA-256 → test DS03 unique, avec la ligne « DS03 sous scellés » | Section protocole |
| `fig4_masking_actions.tex` | Les 5 modes de masquage (channel gagnant encadré) + les 3 injections d'action (token/FiLM/cross-attn) avec les RMSE mesurés | Section ablations / appendice |

`meta_style.tex` : style partagé — palette FAIR (bleu contexte #BDD7EE, saumon cible #F8CBAD,
vert prédicteur #C6E0B4, jaune actions #FFE699), Helvetica, blocs arrondis 7pt, flèches fines,
EMA en pointillés saumon, `\sgmark{x,y}` pour la marque stop-gradient (//).

Compilation locale :
```bash
~/.TinyTeX/bin/*/pdflatex -interaction=nonstopmode figX.tex
```
Les PDF et aperçus PNG (110 dpi) sont fournis à côté des sources.
Version web assortie (mêmes couleurs) : `outputs/SCHEMAS_METHODES.html`.
