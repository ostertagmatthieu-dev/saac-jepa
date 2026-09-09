# Ablation RevIN appariée — M03 vs M03+RevIN (validation DS01, espace commun)

Seeds : [0, 1, 2] ; paires complètes : [0, 1, 2]. n=3 paired seeds: the exact sign-flip p cannot go below 0.125; read the bootstrap CI and the per-seed wins, not p-values.

| composante | M03 (contrôle) | M03+RevIN | Δ (RevIN−ctrl) | IC95 bootstrap | RevIN gagne |
|---|---|---|---|---|---|
| clean_rmse | 0.8190 ± 0.0103 | 0.7663 ± 0.0012 | -0.0527 | [-0.0640, -0.0457] | 3/3 |
| schema_drop_rmse | 0.9180 ± 0.0047 | 0.8867 ± 0.0034 | -0.0313 | [-0.0357, -0.0248] | 3/3 |
| masked_rmse | 0.8272 ± 0.0096 | 0.7862 ± 0.0023 | -0.0409 | [-0.0508, -0.0335] | 3/3 |
| long_horizon_rmse | 0.8683 ± 0.0073 | 0.8487 ± 0.0039 | -0.0196 | [-0.0234, -0.0167] | 3/3 |
| calibration_penalty | 0.1242 ± 0.0270 | 0.0349 ± 0.0022 | -0.0892 | [-0.1201, -0.0691] | 3/3 |
| ssl_latent_val | 1.1874 ± 0.0189 | 1.0640 ± 0.0214 | -0.1234 | [-0.1660, -0.0952] | 3/3 |
| action_sensitivity | 1.0639 ± 0.0243 | 1.1790 ± 0.0013 | +0.1151 | [+0.1004, +0.1426] | 3/3 |
| eff_rank_frac | 0.4266 ± 0.0717 | 0.4626 ± 0.0062 | +0.0360 | [-0.0028, +0.1118] | 1/3 |
| eval_space_anchor_rmse | 0.9575 ± 0.0000 | 0.9575 ± 0.0000 | +0.0000 | [+0.0000, +0.0000] | 0/3 |

Invalides : contrôle [] ; RevIN [0, 1, 2]. Collapse : contrôle [0, 0, 0] ; RevIN [1, 1, 1].

| porte collapse (zpred) | seed | std_min SSL | eff_rank SSL | std_min FT | eff_rank FT | ssl/ft collapse |
|---|---|---|---|---|---|---|
| M03 | 0 | 0.061 | 0.223 | 0.391 | 0.468 | 0/0 |
| M03 | 1 | 0.060 | 0.227 | 0.327 | 0.344 | 0/0 |
| M03 | 2 | 0.059 | 0.231 | 0.365 | 0.468 | 0/0 |
| M03_revin | 0 | 0.040 | 0.488 | 0.280 | 0.467 | 1/0 |
| M03_revin | 1 | 0.041 | 0.470 | 0.291 | 0.456 | 1/0 |
| M03_revin | 2 | 0.041 | 0.446 | 0.294 | 0.465 | 1/0 |

Seuils (trainers.latent_health) : std_min < 0,05 (unités brutes du latent, dépend de l'échelle des entrées) ou eff_rank_frac < 0,10 (sans échelle).
NLL DS01 (espace modèle) : contrôle 3.018 ; RevIN 1.490. Couverture 90 % : 0.776 vs 0.865.

**Verdict validation** : RevIN meilleur sur ['clean_rmse', 'schema_drop_rmse', 'masked_rmse', 'long_horizon_rmse'] parmi ['clean_rmse', 'schema_drop_rmse', 'masked_rmse', 'long_horizon_rmse']. → critère DS03 rempli (stage `ds03` à déclarer).
