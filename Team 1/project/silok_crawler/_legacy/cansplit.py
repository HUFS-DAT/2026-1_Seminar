import os
import xml.etree.ElementTree as ET
import re

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
success_file = os.path.join(target_dir, "filtering_success.txt")

def get_refined_indices(text, is_original=False):
    if not text: return []
    pattern = r'[。\.?!]' if is_original else r'[.?!]'
    matches = list(re.finditer(pattern, text))
    indices = []
    tail_pattern = re.compile(r'^\s*"?\s*(?:라고|하고|하며|하매|하사|교하기를|아뢰기를)?\s*(?:하였다|했다|하니|함에|아뢰었다|전교하였다|말했다|이르기를|하소서|하노라|이다|입니다|하셨다)')
    for m in matches:
        idx = m.start()
        if tail_pattern.search(text[idx+1:]): continue
        indices.append(idx + 1)
    return sorted(list(set(indices)))

def split_and_balance(text, indices):
    raw_parts = []
    start = 0
    for idx in indices:
        part = text[start:idx].strip()
        if part: raw_parts.append(part)
        start = idx
    if start < len(text) and text[start:].strip(): raw_parts.append(text[start:].strip())
    final, buf = [], ""
    for p in raw_parts:
        buf = (buf + " " + p).strip()
        if buf.count('"') % 2 == 0:
            final.append(buf)
            buf = ""
    if buf: final.append(buf)
    return final

def get_speaker_anchors(sents, is_original=False):
    """문장 리스트에서 화자 교체 지점(曰, 말하기를 등)의 인덱스를 반환"""
    o_anchors = ["傳曰:", "啓曰:", "答曰:", "曰:", "諭曰:", "敎曰:", "史臣曰:"]
    t_anchors = ["전교하기를", "아뢰기를", "답하기를", "이르기를", "유시하기를", "하교하기를", "사신은 말한다", "비답하기를"]
    anchors = o_anchors if is_original else t_anchors
    
    found = []
    for i, s in enumerate(sents):
        if any(anchor in s for anchor in anchors):
            found.append(i)
    return found

def align_smartly(o_list, t_list):
    """앵커 포인트를 기준으로 문장들을 강제 동기화"""
    # 1. 화자 교체 지점 확인
    o_anchors = get_speaker_anchors(o_list, True)
    t_anchors = get_speaker_anchors(t_list, False)
    
    # 2. 앵커 개수가 다르면 (번역에서 하니, 로 합친 경우) 앵커를 기준으로 그룹화하여 병합
    if len(o_anchors) != len(t_anchors):
        # 앵커 개수가 안 맞으면 의미 밀림 위험 100%. 안전하게 통문장으로 리턴
        return [ " ".join(o_list) ], [ " ".join(t_list) ]

    # 3. 앵커 개수가 같으면 앵커 사이의 문장들을 병합하여 개수를 맞춤
    new_o, new_t = [], []
    o_idx, t_idx = 0, 0
    
    # 앵커 지점들을 경계로 삼아 구간별 매칭
    o_boundaries = o_anchors + [len(o_list)]
    t_boundaries = t_anchors + [len(t_list)]
    
    for ob, tb in zip(o_boundaries, t_boundaries):
        o_chunk = " ".join(o_list[o_idx:ob+1]).strip()
        t_chunk = " ".join(t_list[t_idx:tb+1]).strip()
        if o_chunk and t_chunk:
            new_o.append(o_chunk)
            new_t.append(t_chunk)
        o_idx, t_idx = ob+1, tb+1
        
    return new_o, new_t

def run_perfect_align():
    with open(success_file, "r", encoding="utf-8") as f:
        safe_ids = {line.split("|")[0].strip().replace("ID: ", "") for line in f}

    print("의미 기반 앵커 동기화(Speaker-based Alignment) 시작...")
    count = 0

    for filename in os.listdir(target_dir):
        if not filename.endswith(".xml") or "filtering" in filename: continue
        file_path = os.path.join(target_dir, filename)
        try:
            tree = ET.parse(file_path); root = tree.getroot()
        except: continue

        modified = False
        for article in root.findall("article"):
            if article.get("id") in safe_ids: continue
            
            sents_node = article.find("sentences")
            t_node, o_node = article.find("translation"), article.find("original")
            
            if sents_node is not None:
                s_tags = sents_node.findall("s")
                o_text = " ".join([s.find("original").text for s in s_tags if s.find("original") is not None])
                t_text = " ".join([s.find("translation").text for s in s_tags if s.find("translation") is not None])
                article.remove(sents_node)
            elif t_node is not None and o_node is not None:
                o_text, t_text = o_node.text, t_node.text
                article.remove(t_node); article.remove(o_node)
            else: continue

            o_parts = split_and_balance(o_text, get_refined_indices(o_text, True))
            t_parts = split_and_balance(t_text, get_refined_indices(t_text, False))

            # [핵심 로직] 의미 기반 앵커 정렬
            o_final, t_final = align_smartly(o_parts, t_parts)

            new_sents = ET.SubElement(article, "sentences")
            if len(o_final) == len(t_final) and len(o_final) > 0:
                for i, (o, t) in enumerate(zip(o_final, t_final), 1):
                    s_node = ET.SubElement(new_sents, "s", id=str(i))
                    ET.SubElement(s_node, "original").text = o
                    ET.SubElement(s_node, "translation").text = t
                count += 1
                modified = True

        if modified:
            ET.indent(tree, space="  ")
            tree.write(file_path, encoding="utf-8", xml_declaration=True)

    print(f"최종 완료! {count}개의 기사를 의미 기반으로 정밀 분리했습니다.")

if __name__ == "__main__":
    run_perfect_align()