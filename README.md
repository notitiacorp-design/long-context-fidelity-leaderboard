# Long-Context Fidelity Leaderboard

**Empirical needle-in-haystack stress tests for LLM context windows.**

We measure exactly *where* and *when* a language model loses information in long contexts. Not a benchmark — a diagnostic instrument.

## 🔥 Key Finding: Terminal Boundary Bias

**DeepSeek V4 Pro and DeepSeek Chat both exhibit 100% recall across all context positions — except position 1.00 (immediately before the query), where recall drops to 0% in 87.5% of cases.**

This is **not** a reasoning-token artifact. The non-reasoning Chat model has the identical failure pattern. The bias is architectural.

## 📊 Results

| Model | Recall | Contexts Tested | Blind Spot |
|-------|--------|-----------------|------------|
| DeepSeek V4 Pro (reasoning) | 88.9% | 512–131K tokens | Position 1.00 (7/8 failures) |
| DeepSeek Chat (non-reasoning) | 88.1% | 512–65K tokens | Position 1.00 (5/6 failures) |

**Full heatmaps:** [long-context-fidelity-leaderboard](https://notitiacorp-design.github.io/long-context-fidelity-leaderboard/)

## 🔬 Methodology

- **Haystack:** 250 KB neutral multi-domain text (economics, physics, biology, CS)
- **Needle:** Single fact — "The secret verification code is MARMALADE-SUNSET-42"
- **Grid:** 56–63 cells (8–9 context lengths × 7 positions)
- **Positions:** 0.00 (start), 0.10, 0.25, 0.50 (middle), 0.75, 0.90, 1.00 (end)
- **Scoring:** Deterministic case-insensitive substring match
- **Temperature:** 0.0 for reproducibility

## 🚀 Reproduce

```bash
pip install httpx pyyaml
export DEEPSEEK_API_KEY="sk-your-key"
python benchmark.py
```

Or use your own provider — the protocol works with any OpenAI-compatible endpoint.

## 📁 Files

- `benchmark.py` — Standalone reproducible test script
- `data/` — Raw JSON results per model
- `index.html` — Live leaderboard with interactive heatmaps

## 🏷️ Notitia Context Fidelity Audit

Commercial audit for production RAG pipelines and AI agents. 990€ one-shot. Includes:

- Full 100+ cell stress test on your documents
- Boundary bias analysis
- Optimization recommendations
- PDF report

Contact: `q@notitia.co`
