# RoboPAD V2 — Ablation RevIN appariée dans SAAC-JEPA (M03)

Date : 9 septembre 2026. Demande d'Ayoub : « JEPA lacks RevIN/instance-wise normalization while target baselines use RevIN » → ajouter l'instance-wise normalization sur le JEPA seulement.

## 1. Ce qui a été fait

- **RevIN interne au JEPA** (`src/cncjepa/models/revin.py`, `MaskedRevIN`) : statistiques par (fenêtre, canal) calculées sur la **fenêtre de contexte** uniquement et sur les **entrées présentes** uniquement (les entrées absentes/masquées valent 0 dans `data.py`, une moyenne naïve serait biaisée ; même choix que SimMTM officiel). Canal jamais observé dans la fenêtre → identité (comportement V1 conservé pour les 7 canaux absents de DS03). `y` normalisé avec les stats du contexte (jamais ajustées sur le futur). Sortie dé-normalisée : `mu·σ+μ`, `logvar+2·log σ`, donc **tout l'espace métrique V1 est inchangé** (ancre trivial-predictor 0,9575 identique sur les deux bras).
- **Réglages = baselines officielles** de `scripts/66` : `affine=0`, `subtract_last=0`, `eps=1e-5`. Flag `model.revin.enabled` ; absent/false = code V1 bit à bit (vérifié : les 3 contrôles reproduisent exactement les `val_metrics.json` de V1, seeds 0-2).
- Protocole : `scripts/68_revin_ablation.py` → pour chaque seed, `scripts/41` (SSL → finetune tête fraîche → bundle de validation en espace commun) sur `configs/search_v2/M03.yaml` (contrôle) et `configs/revin/M03_revin.yaml` (identique + RevIN). 6 runs séquentiels sur le GB10, 72 min/run. Tests : `tests/test_p3fix.py` section (i), 18 invariants (équivariance `mu'=a·mu+c`, stats insensibles au masquage, round-trip, compatibilité checkpoints V1).

## 2. Validation DS01 (source_val, espace z-score commun, 3 seeds appariés)

| composante | M03 | M03 + RevIN | Δ | IC95 bootstrap | RevIN gagne |
|---|---|---|---|---|---|
| clean RMSE | 0,8190 ± 0,0103 | **0,7663 ± 0,0012** | −0,053 (−6,4 %) | [−0,064, −0,046] | 3/3 |
| schema-drop RMSE | 0,9180 ± 0,0047 | **0,8867 ± 0,0034** | −0,031 | [−0,036, −0,025] | 3/3 |
| masked RMSE | 0,8272 ± 0,0096 | **0,7862 ± 0,0023** | −0,041 | [−0,051, −0,034] | 3/3 |
| long-horizon RMSE | 0,8683 ± 0,0073 | **0,8487 ± 0,0039** | −0,020 | [−0,023, −0,017] | 3/3 |
| calibration penalty (|cov90−0,9|) | 0,124 ± 0,027 | **0,035 ± 0,002** | −0,089 | [−0,120, −0,069] | 3/3 |
| val SSL (latent) | 1,187 ± 0,019 | **1,064 ± 0,021** | −0,123 | — | 3/3 |
| sensibilité aux actions (shuffle/true) | 1,064 ± 0,024 | **1,179 ± 0,001** | +0,115 | [+0,100, +0,143] | 3/3 |
| NLL DS01 (espace modèle) | 3,02 | **1,49** | | | |

n = 3 paires : le test de signes exact ne peut descendre sous p = 0,125 ; lire les IC bootstrap et les 3/3. Variance inter-seeds divisée par ~5 à 10 avec RevIN.

**Réserve à déclarer** : les 3 runs RevIN sont marqués `invalid: ssl_latent_collapse` par la porte de `trainers.latent_health`, sur le seul sous-critère `zpred_std_min < 0,05` (0,040-0,041 ; contrôle 0,059-0,061, lui-même à la limite). Ce seuil est en unités brutes du latent (M03 n'a pas de LayerNorm latent) et dépend donc de l'échelle des entrées, que RevIN change. Le critère sans échelle (rang effectif) est deux fois meilleur avec RevIN (0,45-0,49 vs 0,22-0,23) et la santé latente après finetune est identique au contrôle (std_min 0,28-0,29, rang 0,46). Nous considérons la porte comme non pertinente ici mais nous ne l'avons pas modifiée ; à trancher avant toute sélection future.

## 3. DS03 zéro-shot — **ré-ouverture déclarée** (2e lecture du jeu cible)

Le verrou V1 avait consommé la lecture unique de DS03. Cette 2e lecture a été décidée avant les runs, conditionnée au verdict de validation (RevIN meilleur sur les 4 composantes RMSE), sans aucune sélection sur DS03 ; les 6 runs sont évalués (`outputs/revin_ablation/ds03_test.json`, protocole de `scripts/45`).

| modèle | RMSE DS03 (10 canaux, z-units source) | R² | NLL |
|---|---|---|---|
| Persistance | 0,654 | −0,42 | — |
| M03 V1 verrouillé (seed 0) | 0,546 | +0,012 | 0,52 |
| M03 contrôle, 3 seeds | 0,555 ± 0,015 | −0,02 | 0,89 |
| **M03 + RevIN, 3 seeds** | **0,495 ± 0,004** | **+0,19** | **20,6** |
| PatchTST officiel (RevIN, 1 seed) | 0,503 | — | — |
| iTransformer officiel (norm, 1 seed) | 0,498 | — | — |

Différences appariées RevIN − contrôle : −0,046, −0,079, −0,054 (3/3). **L'écart de ~8 % avec les baselines officielles est refermé** : SAAC-JEPA + RevIN est au niveau de PatchTST/iTransformer sur le RMSE brut, avec en plus actions, incertitude et adaptation. Pas de revendication SOTA (baselines à 1 seed, pas de sweep HP ; cf. `NOVELTY_GAP.md`).

**Mais la calibration s'effondre sur DS03** (NLL 20,6 vs 0,9 ; couverture 90 % : 0,874 vs 0,953). Diagnostic (seed 0, par canal) : 11,5 % des points RevIN sont au plancher de variance `logvar = −8` (σ = 0,018) contre 0 % au contrôle ; NLL par canal : spindle_torque 89, z_power 51, spindle_current 40, spindle_power 28. Mécanisme : fenêtre de contexte à l'arrêt (broche/puissance constantes) → σ_fenêtre = √eps ≈ 0,003 → `logvar + 2 log σ` très négatif → variance prédite écrasée → un démarrage dans l'horizon coûte des centaines de nats. C'est exactement le cas dégénéré identifié à l'implémentation (`MaskedRevIN._degenerate_policy`, TODO) et l'analogue du bug IQR de `z_power`. Le RMSE, lui, est protégé par la dé-normalisation. Répartition du gain RMSE : z_current 0,84 → 0,20, z_torque, x/y stables, mais spindle_current/torque légèrement dégradés (0,37 → 0,43 ; 0,60 → 0,67).

## 4. Conclusions et suite proposée

1. RevIN dans le JEPA est validé sur DS01 (3/3 seeds, toutes composantes) et referme l'écart DS03 avec les baselines RevIN : c'était bien la cause principale (PREP_NOTES §6 le prédisait).
2. Le prix est une sur-confiance sur les fenêtres de contexte à l'arrêt. Deux correctifs à comparer, chacun 6 runs (≈ 7,5 h) : (b) plancher sur σ_fenêtre en z-units (p. ex. 0,05-0,1) ; (c) fondu vers l'identité quand la variance de contexte est sous un seuil. Les deux gardent le RMSE, restaurent la calibration, et s'écartent du RevIN « pur » des baselines, ce qui doit être dit dans le papier. Alternative non intrusive : garder RevIN pur pour `mu` et calculer `logvar` dans l'espace global (tête de variance hors instance-norm).
3. Porte `ssl_latent_collapse` à rendre insensible à l'échelle (rang effectif, ou std_min après LayerNorm) avant de rejouer la sélection des 20 méthodes avec RevIN.
4. Verrou : M03 reste la méthode verrouillée V1 ; « M03 + RevIN » est un résultat V2 avec DS03 lu deux fois, à présenter comme tel.

Artefacts : `outputs/revin_ablation/{summary.md,summary.json,ds03_test.json}`, runs `outputs/revin_ablation/{M03,M03_revin}/seed_{0,1,2}`, configs `configs/revin/M03_revin.yaml`, code non commité (branche `main`, à revoir).
