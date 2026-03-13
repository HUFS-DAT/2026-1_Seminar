import os
import xml.etree.ElementTree as ET
import re

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"

# 역이사 보낼 꼬리 단어들
BRIDGE_WORDS = re.compile(r'^"?\s*(?:하였으나|하니|함에|하매|하사|하였다|했다|하고|라 하고|고 하니|이라 하여|라고 하니)[.,\s]*')

def run_final_cleaning():
    print("전체 데이터 의미 밀림 검사 및 문장 꼬리 보정 시작...")
    drift_fix = 0
    bridge_fix = 0

    for filename in os.listdir(target_dir):
        if not filename.endswith(".xml") or "filtering" in filename: continue
        try:
            tree = ET.parse(os.path.join(target_dir, filename))
            root = tree.getroot()
        except: continue

        modified = False
        for article in root.findall("article"):
            sents_node = article.find("sentences")
            if sents_node is None: continue
            
            s_tags = sents_node.findall("s")
            if not s_tags: continue

            # [1] 의미 밀림 검사 (글자 수 비율 불균형 체크)
            is_drifted = False
            for s in s_tags:
                o_len = len(s.find("original").text or "")
                t_len = len(s.find("translation").text or "")
                if o_len > 0 and (t_len / o_len > 20 or t_len / o_len < 0.05): # 심각한 불균형
                    is_drifted = True
                    break
            
            if is_drifted:
                # 안전하게 통문장으로 롤백 (의미 파괴 방지)
                full_o = " ".join([s.find("original").text for s in s_tags]).strip()
                full_t = " ".join([s.find("translation").text for s in s_tags]).strip()
                article.remove(sents_node)
                new_sents = ET.SubElement(article, "sentences")
                new_s = ET.SubElement(new_sents, "s", id="1")
                ET.SubElement(new_s, "original").text = full_o
                ET.SubElement(new_s, "translation").text = full_t
                drift_fix += 1
                modified = True
                continue

            # [2] 문장 꼬리 보정 (이사 보내기)
            for i in range(1, len(s_tags)):
                curr_t = s_tags[i].find("translation").text or ""
                match = BRIDGE_WORDS.match(curr_t)
                if match:
                    bridge = match.group().strip()
                    # 앞 문장 끝으로 보냄
                    prev_t = s_tags[i-1].find("translation").text.strip()
                    s_tags[i-1].find("translation").text = f"{prev_t} {bridge}"
                    # 현재 문장에서 삭제
                    s_tags[i].find("translation").text = curr_t[match.end():].strip()
                    bridge_fix += 1
                    modified = True

        if modified:
            ET.indent(tree, space="  ")
            tree.write(os.path.join(target_dir, filename), encoding="utf-8", xml_declaration=True)

    print(f"작업 완료! 의미 밀림 롤백: {drift_fix}건 / 문장 꼬리 보정: {bridge_fix}건")

if __name__ == "__main__":
    run_final_cleaning()