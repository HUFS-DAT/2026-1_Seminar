import os
import xml.etree.ElementTree as ET
import re

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
success_file = os.path.join(target_dir, "filtering_success.txt")

def get_refined_indices(text, is_original=False):
    if not text: return []
    # 1. 종결 부호 패턴
    pattern = r'[。\.?!]' if is_original else r'[.?!]'
    matches = list(re.finditer(pattern, text))
    
    indices = []
    # 인용구 서술어 패턴 (하였다, 하니 등)
    tail_pattern = re.compile(r'^\s*"?\s*(?:라고|하고|하며|하매|하사|교하기를|아뢰기를)?\s*(?:하였다|했다|하니|함에|아뢰었다|전교하였다|말했다|이르기를|하소서|하노라|이다|입니다|하셨다|했노라)')

    for m in matches:
        idx = m.start()
        after_text = text[idx+1:]
        
        # 서술어 패턴이 바로 오면 자르지 않음 (병합 대상)
        if tail_pattern.search(after_text):
            continue
        
        # 부호 뒤에 따옴표가 붙어 있으면 따옴표까지 포함
        strip_after = after_text.strip()
        if strip_after.startswith('"'):
            q_pos = after_text.find('"') + idx + 2
            indices.append(q_pos)
        else:
            indices.append(idx + 1)
    
    return sorted(list(set(indices)))

def split_and_align(text, indices):
    """인용구 밸런싱 및 파편 병합을 통한 정밀 분리"""
    raw_parts = []
    start = 0
    for idx in indices:
        part = text[start:idx].strip()
        if part: raw_parts.append(part)
        start = idx
    if start < len(text):
        rem = text[start:].strip()
        if rem: 
            if not raw_parts: return [rem]
            raw_parts[-1] = raw_parts[-1] + " " + rem

    # --- [2단계: 따옴표 밸런싱 및 도입부 병합] ---
    final_merged = []
    temp_buffer = ""
    
    intro_keywords = ("전교하였다", "아뢰었다", "답하였다", "말하였다", "이르기를", "하였다")

    for p in raw_parts:
        if not temp_buffer:
            temp_buffer = p
        else:
            temp_buffer = (temp_buffer + " " + p).replace("  ", " ")
        
        # 현재 버퍼의 따옴표 개수 확인
        quote_count = temp_buffer.count('"')
        
        # 따옴표가 짝수이고, 문장이 너무 짧지 않으며(도입부 방지), 
        # "전교하였다. \"" 처럼 끝나지 않는 경우에만 확정
        is_intro = any(temp_buffer.strip().endswith(k + '.') for k in intro_keywords) or temp_buffer.strip().endswith('"')
        # 따옴표가 닫혔거나 아예 없는 경우에만 문장 종료 인정
        if quote_count % 2 == 0:
            # 단, "전교하였다." 처럼 도입부로 끝나는 경우 다음 따옴표 문장과 합치기 위해 대기
            if not (temp_buffer.strip().endswith('.') and any(k in temp_buffer for k in intro_keywords) and len(temp_buffer) < 20):
                final_merged.append(temp_buffer.strip())
                temp_buffer = ""
    
    if temp_buffer:
        if final_merged:
            final_merged[-1] = (final_merged[-1] + " " + temp_buffer).strip()
        else:
            final_merged.append(temp_buffer.strip())
            
    return final_merged

def run_ultimate_aligner():
    with open(success_file, "r", encoding="utf-8") as f:
        success_ids = {line.split("|")[0].strip().replace("ID: ", "") for line in f}

    print(f"대상 {len(success_ids)}개 기사 정렬 무결성 작업 시작...")

    for filename in os.listdir(target_dir):
        if filename.endswith(".xml") and "filtering" not in filename:
            file_path = os.path.join(target_dir, filename)
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
            except: continue

            modified = False
            for article in root.findall("article"):
                article_id = article.get("id")
                if article_id in success_ids:
                    # 기존 구조 초기화
                    old_sents = article.find("sentences")
                    if old_sents is not None: article.remove(old_sents)
                    t_node, o_node = article.find("translation"), article.find("original")
                    if t_node is None or o_node is None: continue

                    t_text, o_text = t_node.text.strip(), o_node.text.strip()

                    # 1. 원문은 단순 분리 (원문은 인용구 기호가 엄격하지 않음)
                    o_sents = split_and_align(o_text, get_refined_indices(o_text, True))
                    # 2. 번역문은 인용구 밸런싱 적용
                    t_sents = split_and_align(t_text, get_refined_indices(t_text, False))

                    article.remove(t_node)
                    article.remove(o_node)
                    sents_node = ET.SubElement(article, "sentences")
                    
                    # [최종 무결성 검사] 개수가 정확히 일치할 때만 쪼갬
                    if len(o_sents) == len(t_sents) and len(o_sents) > 0:
                        for i, (o, t) in enumerate(zip(o_sents, t_sents), 1):
                            s_node = ET.SubElement(sents_node, "s", id=str(i))
                            ET.SubElement(s_node, "translation").text = t
                            ET.SubElement(s_node, "original").text = o
                    else:
                        # 개수가 하나라도 어긋나면 100% 확률로 정렬이 깨진 것이므로
                        # 절대 쪼개지 않고 통째로 보존 (AI 학습용 데이터의 순도 보장)
                        s_node = ET.SubElement(sents_node, "s", id="1")
                        ET.SubElement(s_node, "translation").text = t_text
                        ET.SubElement(s_node, "original").text = o_text
                    
                    modified = True

            if modified:
                ET.indent(tree, space="  ")
                tree.write(file_path, encoding="utf-8", xml_declaration=True)

    print("작업 완료. 인용구 밸런싱을 통한 문장 정렬 무결성이 확보되었습니다.")

if __name__ == "__main__":
    run_ultimate_aligner()