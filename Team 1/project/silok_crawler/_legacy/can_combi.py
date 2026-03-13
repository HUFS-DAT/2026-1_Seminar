import os
import xml.etree.ElementTree as ET

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
success_file = os.path.join(target_dir, "filtering_success.txt")

def run_rollback():
    # 1. '진짜 성공' 목록(8.2만 건) 로드 - 이들은 건드리지 않음
    if not os.path.exists(success_file):
        print("filtering_success.txt가 없습니다. 경로를 확인해주세요.")
        return

    with open(success_file, "r", encoding="utf-8") as f:
        # ID만 깨끗하게 추출
        safe_ids = {line.split("|")[0].strip().replace("ID: ", "") for line in f}

    print(f"안전 목록 {len(safe_ids)}건 확인됨. 나머지 기사 롤백 시작...")
    rollback_count = 0

    for filename in os.listdir(target_dir):
        if not filename.endswith(".xml") or "filtering" in filename:
            continue
            
        file_path = os.path.join(target_dir, filename)
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except:
            continue

        modified = False
        for article in root.findall("article"):
            art_id = article.get("id")
            
            # [롤백 조건]
            # 1. 현재 <sentences> 태그가 달려 있어야 함
            # 2. 그런데 그 ID가 '안전 목록(8.2만 건)'에는 없어야 함
            sents_node = article.find("sentences")
            
            if sents_node is not None and art_id not in safe_ids:
                # <s> 태그들 안에 흩어진 텍스트를 하나로 합침
                s_tags = sents_node.findall("s")
                full_o = " ".join([s.find("original").text for s in s_tags if s.find("original") is not None]).strip()
                full_t = " ".join([s.find("translation").text for s in s_tags if s.find("translation") is not None]).strip()
                
                # <sentences> 태그 삭제
                article.remove(sents_node)
                
                # 원본 형태인 <original>과 <translation> 태그 다시 생성
                new_o = ET.SubElement(article, "original")
                new_o.text = full_o
                new_t = ET.SubElement(article, "translation")
                new_t.text = full_t
                
                modified = True
                rollback_count += 1

        if modified:
            # XML 파일 예쁘게 정렬하여 저장
            ET.indent(tree, space="  ")
            tree.write(file_path, encoding="utf-8", xml_declaration=True)

    print(f"작업 완료! 총 {rollback_count}개의 기사가 원본 태그(<original>, <translation>)로 롤백되었습니다.")

if __name__ == "__main__":
    run_rollback()