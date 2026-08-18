import json

data = json.load(open("data/chunks.json", "r", encoding="utf-8"))

# 1. Check for Grief / Bereavement / PGD disorders
grief = [c for c in data if any(kw in c.get("disorder_name", "").lower() for kw in ["grief", "bereavement", "prolonged"])]
print(f"=== Grief/Bereavement/PGD related chunks: {len(grief)} ===")
for c in grief:
    print(f"  [{c['disorder_name']}] - {c['section_name']} ({len(c.get('text',''))} chars)")

# 2. Check for Schizophrenia (timeline example)
schiz = [c for c in data if "schizophrenia" == c.get("disorder_name", "").lower()]
print(f"\n=== Schizophrenia chunks: {len(schiz)} ===")
for c in schiz:
    print(f"  [{c['disorder_name']}] - {c['section_name']} ({len(c.get('text',''))} chars)")

# 3. Check for MDD
mdd = [c for c in data if "major depressive" in c.get("disorder_name", "").lower()]
print(f"\n=== Major Depressive Disorder chunks: {len(mdd)} ===")
for c in mdd:
    print(f"  [{c['disorder_name']}] - {c['section_name']} ({len(c.get('text',''))} chars)")

# 4. Check for substance-induced psychotic
subst = [c for c in data if "substance" in c.get("disorder_name", "").lower() and "psychotic" in c.get("disorder_name", "").lower()]
print(f"\n=== Substance-Induced Psychotic chunks: {len(subst)} ===")
for c in subst:
    print(f"  [{c['disorder_name']}] - {c['section_name']} ({len(c.get('text',''))} chars)")

# 5. Print full list of all disorder names
all_disorders = sorted(set(c.get("disorder_name", "") for c in data))
print(f"\n=== ALL {len(all_disorders)} Disorder Names ===")
for d in all_disorders:
    print(f"  - {d}")
