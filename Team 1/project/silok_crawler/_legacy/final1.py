import os
import xml.etree.ElementTree as ET
import re

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
# 사용자가 준 435건의 ID 리스트 (정밀 수술 대상)
TARGET_IDS = {
    "koa_10005024_001", "koa_10006015_008", "koa_10006019_003", "koa_10106001_005", 
    "koa_10108010_003", "koa_10201026_004", "koa_10203027_009", "koa_10509001_004",
    "kpa_12503020_001", "kqa_10103025_003", "kra_10006019_001" 
    # ... (생략된 435개 ID는 final_check_list.txt를 읽어서 자동 처리함)
}

def run_ultimate_fix():
    # 1. 점검 리스트에서 모든 타겟 ID 불러오기
    all_target_ids = set()
    check_list_path = "final_check_list.txt"
    if os.path.exists(check_list_path):
        with open(check_list_path, "r", encoding="utf-8") as f:
            for line in f:
                if "ID: " in line:
                    all_target_ids.add(line.split("ID: ")[1].split(" |")[0].strip())
    
    print(f"총 {len(all_target_ids)}건의 기사 정밀 수술 시작...")
    fix_count = 0

    for filename in os.listdir(target_dir):
        if not filename.endswith(".xml") or "filtering" in filename: continue
        file_path = os.path.join(target_dir, filename)
        try:
            tree = ET.parse(file_path); root = tree.getroot()
        except: continue

        modified = False
        for article in root.findall("article"):
            art_id = article.get("id")
            sents_node = article.find("sentences")
            if sents_node is None: continue
            
            s_tags = sents_node.findall("s")
            
            # [수술 핵심 로직] 
            # 1. 타겟 리스트에 있거나 
            # 2. 문장 간 글자 수 밀도 차이가 20배 이상 나는 경우 (명백한 밀림)
            is_bad_alignment = (art_id in all_target_ids)
            
            if not is_bad_alignment: # 밀도 재검사
                for s in s_tags:
                    o_len = len(s.find("original").text or "")
                    t_len = len(s.find("translation").text or "")
                    if o_len > 10 and (t_len / o_len > 20 or t_len / o_len < 0.05):
                        is_bad_alignment = True
                        break

            if is_bad_alignment:
                # [안전 통합 전략] 억지로 쪼개진 문장을 하나로 합쳐서 의미를 100% 보존함
                full_o = " ".join([s.find("original").text for s in s_tags if s.find("original") is not None]).strip()
                full_t = " ".join([s.find("translation").text for s in s_tags if s.find("translation") is not None]).strip()
                
                # 기존 s 태그 삭제 후 s_id 1로 재구성
                for s in list(sents_node): sents_node.remove(s)
                new_s = ET.SubElement(sents_node, "s", id="1")
                ET.SubElement(new_s, "original").text = full_o
                ET.SubElement(new_s, "translation").text = full_t
                
                modified = True
                fix_count += 1

        if modified:
            ET.indent(tree, space="  ")
            tree.write(file_path, encoding="utf-8", xml_declaration=True)

    print(f"수술 완료! 총 {fix_count}건의 기사가 '의미 무결성 100%' 상태로 교정되었습니다.")

if __name__ == "__main__":
    run_ultimate_fix()