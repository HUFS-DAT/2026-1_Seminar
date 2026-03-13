import os
import xml.etree.ElementTree as ET
import re

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
mismatch_file = "filtering_mismatch.txt"

def get_refined_indices(text, is_original=False):
    if not text: return []
    pattern = r'[。\.?!]' if is_original else r'[.?!]'
    matches = list(re.finditer(pattern, text))
    indices = [m.end() for m in matches]
    return indices

def split_into_parts(text, indices):
    parts = []
    start = 0
    for idx in indices:
        part = text[start:idx].strip()
        if part: parts.append(part)
        start = idx
    if start < len(text):
        last = text[start:].strip()
        if last: parts.append(last)
    return parts

def force_merge_to_target(parts, target_count):
    """가장 짧은 조각을 인접 조각과 합쳐서 개수를 target_count로 맞춤"""
    while len(parts) > target_count and len(parts) > 1:
        # 가장 짧은 조각 찾기
        min_idx = 0
        min_len = len(parts[0])
        for i in range(1, len(parts)):
            if len(parts[i]) < min_len:
                min_len = len(parts[i])
                min_idx = i
        
        # 합칠 파트너 정하기 (앞뒤 중 더 짧은 쪽)
        if min_idx == 0:
            parts[0] = parts[0] + " " + parts[1]
            parts.pop(1)
        elif min_idx == len(parts) - 1:
            parts[min_idx-1] = parts[min_idx-1] + " " + parts[min_idx]
            parts.pop(min_idx)
        else:
            if len(parts[min_idx-1]) < len(parts[min_idx+1]):
                parts[min_idx-1] = parts[min_idx-1] + " " + parts[min_idx]
                parts.pop(min_idx)
            else:
                parts[min_idx] = parts[min_idx] + " " + parts[min_idx+1]
                parts.pop(min_idx+1)
    return parts

def run_mismatch_fix():
    # 1. 미스매치 ID 리스트 확보
    target_ids = set()
    with open(mismatch_file, "r", encoding="utf-8") as f:
        for line in f:
            if "ID: " in line:
                target_ids.add(line.split("|")[0].replace("ID: ", "").strip())

    print(f"미스매치 타겟 {len(target_ids)}건 수술 시작...")
    fix_count = 0

    for filename in os.listdir(target_dir):
        if not filename.endswith(".xml") or "filtering" in filename: continue
        file_path = os.path.join(target_dir, filename)
        try:
            tree = ET.parse(file_path); root = tree.getroot()
        except: continue

        modified = False
        for article in root.findall(".//article"):
            art_id = article.get("id")
            if art_id not in target_ids: continue

            # 기존 데이터 확보 (이미 1문장으로 묶여있을 것임)
            sents_node = article.find("sentences")
            if sents_node is not None:
                s_tags = sents_node.findall("s")
                o_text = " ".join([s.find("original").text for s in s_tags if s.find("original") is not None])
                t_text = " ".join([s.find("translation").text for s in s_tags if s.find("translation") is not None])
                for s in list(sents_node): sents_node.remove(s)
            else:
                t_node, o_node = article.find("translation"), article.find("original")
                if t_node is None or o_node is None: continue
                o_text, t_text = o_node.text, t_node.text
                article.remove(t_node); article.remove(o_node)
                sents_node = ET.SubElement(article, "sentences")

            # 2. 강제 분리 로직 적용
            o_parts = split_into_parts(o_text, get_refined_indices(o_text, True))
            t_parts = split_into_parts(t_text, get_refined_indices(t_text, False))

            # 양쪽 중 더 적은 문장 수로 맞춤 (안전제일)
            target = min(len(o_parts), len(t_parts))
            if target == 0: target = 1
            
            o_final = force_merge_to_target(o_parts, target)
            t_final = force_merge_to_target(t_parts, target)

            # 3. 저장
            for i, (o, t) in enumerate(zip(o_final, t_final), 1):
                s_node = ET.SubElement(sents_node, "s", id=str(i))
                ET.SubElement(s_node, "original").text = o
                ET.SubElement(s_node, "translation").text = t
            
            modified = True
            fix_count += 1

        if modified:
            ET.indent(tree, space="  ")
            tree.write(file_path, encoding="utf-8", xml_declaration=True)

    print(f"수술 완료! {fix_count}개의 미스매치 기사가 문장 단위로 재탄생했습니다.")

if __name__ == "__main__":
    run_mismatch_fix()