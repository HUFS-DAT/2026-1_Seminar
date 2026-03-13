import os
import xml.etree.ElementTree as ET
import re

target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
# 아직 문장 시작에 남아있을지 모르는 꼬리 패턴
BRIDGE_PATTERN = re.compile(r'^"?\s*(?:하였으나|하니|함에|하매|하사|하였다|했다|하고|라 하고|고 하니|이라 하여|라고 하니)')

def run_self_diagnosis():
    print("100% 완성을 위한 최종 오류 추적 시작...")
    error_cases = []

    for filename in os.listdir(target_dir):
        if not filename.endswith(".xml") or "filtering" in filename: continue
        try:
            tree = ET.parse(os.path.join(target_dir, filename))
            root = tree.getroot()
        except: continue

        for article in root.findall("article"):
            art_id = article.get("id")
            sents_node = article.find("sentences")
            if sents_node is None: continue
            
            s_tags = sents_node.findall("s")
            for i, s in enumerate(s_tags):
                o_text = s.find("original").text or ""
                t_text = s.find("translation").text or ""
                
                # 1. 밀도 체크 (의미 밀림 의심)
                o_len, t_len = len(o_text), len(t_text)
                if o_len > 0:
                    ratio = t_len / o_len
                    if ratio > 15 or ratio < 0.2: # 너무 길거나 너무 짧음
                        error_cases.append(f"[의미밀림 의심] ID: {art_id} | s_id: {s.get('id')} | 비율: {ratio:.2f}")

                # 2. 잔여 꼬리 체크 (s_id 2번부터 시작이 '하였으나' 등인지)
                if i > 0 and BRIDGE_PATTERN.match(t_text):
                    error_cases.append(f"[잔여꼬리 발견] ID: {art_id} | s_id: {s.get('id')} | 내용: {t_text[:20]}...")

    with open("final_check_list.txt", "w", encoding="utf-8") as f:
        f.write(f"=== 최종 100% 달성을 위한 점검 리스트 (총 {len(error_cases)}건) ===\n")
        f.write("이 리스트가 0건이 될 때까지 로직을 수정해야 합니다.\n\n")
        for case in error_cases:
            f.write(case + "\n")

    print(f"진단 완료! 총 {len(error_cases)}개의 잠재적 오류를 'final_check_list.txt'에 저장했습니다.")

if __name__ == "__main__":
    run_self_diagnosis()