"""
Long-Context Fidelity Benchmark — Reproducible needle-in-haystack stress test.
Usage: DEEPSEEK_API_KEY=sk-... python benchmark.py
"""
import asyncio, json, os, sys

import httpx

# ── Config ──────────────────────────────────────────
MODEL = os.environ.get("MODEL", "deepseek-v4-pro")
BASE_URL = os.environ.get("BASE_URL", "https://api.deepseek.com/v1")
API_KEY = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
OUTPUT = os.environ.get("OUTPUT", "results.json")

LENGTHS = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
POSITIONS = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]

# ── Needle & Haystack ──────────────────────────────
NEEDLE = "IMPORTANT MEMORANDUM: The secret verification code is MARMALADE-SUNSET-42."
QUESTION = "What is the secret verification code? Answer ONLY the code, nothing else."
ANSWER = "MARMALADE-SUNSET-42"

HAYSTACK_PARAGRAPHS = [
    "The economic impact of renewable energy adoption in developing nations has been studied extensively. Solar photovoltaic installations have grown by 34% annually.",
    "Quantum computing architectures based on superconducting qubits require operating temperatures below 15 millikelvin. Dilution refrigerators achieve this using helium isotopes.",
    "The molecular mechanisms of CRISPR-Cas9 gene editing involve a guide RNA complementary to the target DNA sequence. Cas9 induces a double-strand break.",
    "Urban transportation networks are being transformed by autonomous electric vehicles. Waymo operates driverless taxi services in multiple US cities.",
    "The thermohaline circulation of the oceans is driven by differences in water density. The Atlantic Meridional Overturning Circulation transports 18 Sverdrups.",
    "Deep reinforcement learning algorithms have achieved superhuman performance in Go, chess, shogi, and StarCraft II through Monte Carlo tree search.",
    "Metal-organic frameworks for carbon capture require precise control over pore size and surface chemistry. UiO-66 derivatives show CO2 uptake exceeding 4 mmol/g.",
    "The James Webb Space Telescope has revealed galaxies at redshift z>13 that appear too massive for standard Lambda-CDM cosmology.",
    "The gut-brain axis links the enteric nervous system with the CNS via the vagus nerve. Short-chain fatty acids cross the blood-brain barrier.",
    "Transformer architectures drive modern NLP through self-attention mechanisms. Quadratic complexity with sequence length remains the fundamental bottleneck.",
    "Solid-state batteries promise energy densities exceeding 500 Wh/kg. Toyota and Samsung target 2027-2028 for automotive production.",
    "Climate models project 2.7°C warming by 2100 under current policies. Methane reduction is the most cost-effective near-term lever.",
    "Immunotherapy has been revolutionized by checkpoint inhibitors targeting PD-1 and CTLA-4. CAR-T therapies show remission rates above 80%.",
    "The semiconductor industry transition to 3nm gate-all-around transistors represents a fundamental shift from FinFET architectures.",
    "Archaeological evidence from Gobekli Tepe suggests monumental architecture predated agriculture, challenging the Neolithic Revolution narrative.",
    "Blockchain consensus has evolved from proof-of-work to proof-of-stake, reducing energy consumption by 99.95% in Ethereum's transition.",
    "Nuclear fusion achieved scientific breakeven in December 2022 at NIF, producing 3.15 MJ from 2.05 MJ of laser input.",
    "CRISPR-Cas9 therapy for sickle cell disease was approved in the UK and US in late 2023, using ex vivo hematopoietic stem cell editing.",
    "Satellite constellations in LEO raise concerns about space debris and astronomical interference. The IAU has called for regulatory frameworks.",
    "The polymerase chain reaction amplifies DNA through cycles of denaturation, annealing, and extension using Taq polymerase from Thermus aquaticus."
]

def generate_haystack(target_tokens):
    """Generate neutral haystack of ~target_tokens tokens."""
    import random
    random.seed(42)
    haystack = ""
    while len(haystack.encode('utf-8')) < target_tokens * 4:
        haystack += random.choice(HAYSTACK_PARAGRAPHS) + "\n\n"
    return haystack

# ── API ─────────────────────────────────────────────
async def call_api(context, question, sem):
    async with sem:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as c:
            user = f"DOCUMENT:\n{context}\n\nQUESTION: {question}"
            if not API_KEY:
                raise RuntimeError("Set DEEPSEEK_API_KEY or OPENAI_API_KEY")
            for attempt in range(3):
                try:
                    resp = await c.post(
                        f"{BASE_URL}/chat/completions",
                        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                        json={"model": MODEL, "messages": [
                            {"role": "system", "content": "You are a precise assistant. Answer only what is asked."},
                            {"role": "user", "content": user}
                        ], "max_tokens": 500, "temperature": 0.0},
                    )
                    if resp.status_code == 200:
                        d = resp.json()
                        return d["choices"][0]["message"]["content"] or "", d.get("usage",{}).get("total_tokens",0)
                    elif resp.status_code == 429:
                        await asyncio.sleep(2 ** attempt * 3)
                    else:
                        if attempt < 2: await asyncio.sleep(3)
                except Exception as e:
                    if attempt < 2: await asyncio.sleep(3)
            return "ERROR", 0

def score(text):
    return 1.0 if ANSWER.lower() in text.lower() else 0.0

# ── Main ────────────────────────────────────────────
async def main():
    if not API_KEY:
        print("Error: Set DEEPSEEK_API_KEY or OPENAI_API_KEY")
        print("Example: DEEPSEEK_API_KEY=sk-... python benchmark.py")
        sys.exit(1)
    
    haystack = generate_haystack(max(LENGTHS))
    sem = asyncio.Semaphore(2)
    results = {}
    
    print(f"Benchmark: {MODEL} @ {BASE_URL}")
    print(f"Grid: {len(LENGTHS)} lengths x {len(POSITIONS)} positions = {len(LENGTHS)*len(POSITIONS)} cells\n")
    
    total = len(LENGTHS) * len(POSITIONS)
    done = 0
    for L in LENGTHS:
        chars = L * 4
        for P in POSITIONS:
            ctx = haystack[:chars]
            ins = int(P * len(ctx))
            ctx = ctx[:ins] + "\n\n" + NEEDLE + "\n\n" + ctx[ins:]
            ctx = ctx[:chars]
            
            txt, tk = await call_api(ctx, QUESTION, sem)
            rec = score(txt)
            done += 1
            
            pct = done/total*100
            bar = "=" * int(pct/5) + "-" * (20-int(pct/5))
            st = "HIT" if rec else "MISS"
            print(f"[{bar}] {done}/{total} {pct:.0f}% | {L:>5}t P={P:.2f} | {st} | {tk}t")
            
            results[f"{L}_{P}"] = {"L": L, "P": P, "recall": rec, "tokens": tk}
    
    # Summary
    hits = sum(1 for v in results.values() if v["recall"] == 1)
    print(f"\n{'='*50}")
    print(f"Results: {hits}/{total} HIT ({hits/total:.1%})")
    print(f"Saved: {OUTPUT}")
    
    with open(OUTPUT, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
