# Africa Ascendant — Demographic Expansion &amp; the Global African Diaspora (2000–2500)

A fixed-position, webapp-style **world map dashboard** built with the **Veles (Fable-5 × DeepSeek)** pipeline for **H Heuristics**.

It visualizes the research report *"Africa's Demographic Expansion and the Global African Diaspora Through the Twenty-First Century"* (H Heuristics, September 2026) on a 300-year horizon.

---

## What it shows

- **World choropleth map** — projected population for every country, animated 2000 → 2500 with playback controls, with Africa outlined in amber.
- **Three map layers** — `Population` (log scale), `Δ since 2000` (diverging growth/decline), and `Diaspora` (African-ancestry footprint hubs outside Africa).
- **Africa KPI panel** — Africa's population, share of humanity, Africa-born stock abroad, broad mixed-ancestry scenario, and Africa's share of the world's under-25s.
- **Continental ledger** — all six UN regions at the selected year.
- **Top African countries in 2100** — Nigeria, DRC, Ethiopia, Tanzania, Egypt, Sudan.
- **Chart panel** — Trajectory (regions + world), Africa's rising share, diaspora envelopes (1.47% / 2% / 3% mobility + broad-ancestry scenario + **worldwide any-African-ancestry low/central/high**), top-12 countries in 2100, and age/fertility.

## Data & horizon honesty

| Span | Basis |
|---|---|
| 2000–2100 | **UN World Population Prospects 2024** medium variant, via Our World in Data |
| 2105–2500 | **H Heuristics extended scenario** — each UN region is eased from its 2100 value toward a 2500 anchor in which Africa approaches half of humanity (per the report's "Beyond 2100" note). Country values scale with their region. |

The UI flags every post-2100 value with an **EXTENDED SCENARIO** badge. The diaspora figures are transparently labeled: the 1.47% / 2% / 3% envelopes are arithmetic scale illustrations, and the "any African ancestry abroad" series is an illustrative directional scenario — not a UN or IOM forecast.

## Project structure

```
├── index.html          # self-contained dashboard (committed, deploy-ready)
├── template.html       # UI/JS/CSS source with a data placeholder
├── build.py            # rebuilds index.html from UN data + extended scenario
├── .github/workflows/  # GitHub Pages deploy (on push to main)
└── fable.toml          # Veles / Fable-5 config
```

## Rebuild

```bash
python3 build.py
```

`build.py` uses cached CSVs in `data/` (git-ignored) or re-downloads them from Our World in Data, preprocesses 2000–2500 series, and injects them into `template.html` to produce `index.html`.

## Deploy

Push to `main` — the included GitHub Actions workflow deploys to GitHub Pages automatically. In the repository's **Settings → Pages**, set **Source** to **GitHub Actions**.

---

© H Heuristics · Built with Veles (Fable-5 × DeepSeek)
