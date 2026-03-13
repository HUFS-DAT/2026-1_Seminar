import os
import xml.etree.ElementTree as ET
import re
import random

# 설정 (사용자님 경로에 맞게 수정하세요)
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
output_file = os.path.join(target_dir, "candidate_samples_500.txt")

def count_refined_sentences(text, is_original=False):
    if not text: return 0
    text = text.strip()
    pattern = r'[。\.?!]' if is_original else r'[.?!]'
    matches = list(re.finditer(pattern, text))
    
    if is_original: return len(matches)
    
    # 번역문 정밀 카운트 (최종 로직 반영)
    indices = []
    tail_pattern = re.compile(r'^\s*"?\s*(?:라고|하고|하며|하매|하사|교하기를|아뢰기를)?\s*(?:하였다|했다|하니|함에|아뢰었다|전교하였다|말했다|이르기를|하소서|하노라|이다|입니다|하셨다|했노라)')
    for m in matches:
        idx = m.start()
        if not tail_pattern.search(text[idx+1:]):
            indices.append(idx + 1)

    # 따옴표 및 도입부 밸런싱 적용
    parts = []
    start = 0
    for idx in sorted(list(set(indices))):
        parts.append(text[start:idx].strip())
        start = idx
    if text[start:].strip(): parts.append(text[start:].strip())

    count = 0
    buf = ""
    for p in parts:
        buf += p
        if buf.count('"') % 2 == 0:
            if not (buf.strip().endswith('.') and any(k in buf for k in ("전교하였다", "아뢰었다", "하였다") if k in buf) and len(buf) < 20):
                count += 1
                buf = ""
    if buf: count += 1
    return count

def extract_candidates():
    candidates = []
    print("후보군 탐색 중...")
    
    for filename in os.listdir(target_dir):
        if filename.endswith(".xml") and "filtering" not in filename:
            file_path = os.path.join(target_dir, filename)
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                for article in root.findall("article"):
                    # 이미 변환된 것은 제외
                    if article.find("sentences") is not None: continue
                    t_node, o_node = article.find("translation"), article.find("original")
                    if t_node is None or o_node is None: continue
                    
                    o_cnt = count_refined_sentences(o_node.text, True)
                    t_cnt = count_refined_sentences(t_node.text, False)
                    
                    if abs(o_cnt - t_cnt) == 1 and o_cnt > 0:
                        candidates.append({
                            "id": article.get("id"),
                            "o_text": o_node.text.strip(),
                            "t_text": t_node.text.strip(),
                            "o_cnt": o_cnt,
                            "t_cnt": t_cnt
                        })
            except: continue

    sample_size = min(len(candidates), 500)
    samples = random.sample(candidates, sample_size)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"=== 1개 차이 후보군 샘플 ({sample_size}건) ===\n\n")
        for i, item in enumerate(samples, 1):
            f.write(f"[{i}] ID: {item['id']} (원문 {item['o_cnt']} vs 번역 {item['t_cnt']})\n")
            f.write(f"  [원문]\n  {item['o_text']}\n")
            f.write(f"  [번역]\n  {item['t_text']}\n")
            f.write("-" * 80 + "\n")
    print(f"완료! {output_file}에 저장되었습니다.")

if __name__ == "__main__":
    extract_candidates()