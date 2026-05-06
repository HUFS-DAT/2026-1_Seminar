"""
NER Entity Recall: baseline / few-shot / v4 3-way
실행: ablation5way/ 폴더 안에서 python ner_recall_300.py
"""
import json, re, sys
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(__file__).parent

EVAL_FILE  = BASE / "eval300_1925.json"
NER_GT     = BASE / "ner_groundtruth_300.json"
CONDITIONS = {
    "baseline":  BASE / "results300_baseline.jsonl",
    "few-shot":  BASE / "results300_fewshot.jsonl",
    "v4":        BASE / "results300_v4.jsonl",
    "kb-inject": BASE / "results300_kbinject.jsonl",
}
OUTPUT_TXT = BASE / "ner_recall_300.txt"


def strip(text):
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
    text = re.sub(r"^○\s*", "", text.strip())
    text = re.sub(r"\s*○\s*", " ", text).strip()
    text = re.sub(r'\([^\)]*[一-鿿][^\)]*\)', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def load_results(path):
    results = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if "hypothesis" in r:
                        results[r["id"]] = strip(r["hypothesis"])
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return results


if not NER_GT.exists():
    print("⚠️  ner_groundtruth_300.json 없음 — build_ner_groundtruth_300.py 먼저 실행")
    sys.exit(1)

data = json.load(open(EVAL_FILE, encoding="utf-8"))
eval_ids = data["ids"]
groundtruth = json.load(open(NER_GT, encoding="utf-8"))
loaded = {cond: load_results(path) for cond, path in CONDITIONS.items()}

common_ids = [eid for eid in eval_ids
              if all(eid in loaded[c] for c in CONDITIONS) and eid in groundtruth]
ids_with_ent = [eid for eid in common_ids if groundtruth[eid]]
print(f"공통 완료: {len(common_ids)} | 엔티티 있는 항목: {len(ids_with_ent)}")


def calc_recall(hyp_map, ids):
    hits = defaultdict(int)
    total = defaultdict(int)
    for eid in ids:
        hyp = hyp_map.get(eid, "")
        for tag, hanja, korean in groundtruth[eid]:
            total[tag] += 1
            total["ALL"] += 1
            if korean in hyp:
                hits[tag] += 1
                hits["ALL"] += 1
    return {t: hits[t] / max(total[t], 1)
            for t in ["ALL", "PER", "LOC", "POH", "DAT"] if total[t] > 0}


W = 75
recalls = {}
lines = [
    "=" * W,
    f"NER Entity Recall | eval300 | n={len(ids_with_ent)} (엔티티 있는 항목)",
    "=" * W,
    f"{'':18s}  {'ALL':>8}  {'PER':>8}  {'LOC':>8}  {'POH':>8}",
    "─" * W,
]
for cond in CONDITIONS:
    r = calc_recall(loaded[cond], ids_with_ent)
    recalls[cond] = r
    lines.append(f"  {cond:16s}  {r.get('ALL',0):>8.3f}  {r.get('PER',0):>8.3f}  "
                 f"{r.get('LOC',0):>8.3f}  {r.get('POH',0):>8.3f}")
lines.append("─" * W)
b = recalls["baseline"]
for cond in ["few-shot", "v4"]:
    r = recalls[cond]
    lines.append(f"  Δ {cond:14s}  {r.get('ALL',0)-b.get('ALL',0):>+8.3f}  "
                 f"{r.get('PER',0)-b.get('PER',0):>+8.3f}  "
                 f"{r.get('LOC',0)-b.get('LOC',0):>+8.3f}  "
                 f"{r.get('POH',0)-b.get('POH',0):>+8.3f}")
lines.append("=" * W)

output = "\n".join(lines)
print("\n" + output)
with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    f.write(output + "\n")
print(f"\n저장: {OUTPUT_TXT}")
