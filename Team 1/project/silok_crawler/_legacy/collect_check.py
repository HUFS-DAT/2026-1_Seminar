import os
import xml.etree.ElementTree as ET

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
check_list_path = "final_check_list.txt"
output_file = "final_check_contents_for_gpt.txt"

def extract_targets():
    # 1. 파이널 체크 리스트에서 유니크한 ID만 뽑기
    target_ids = set()
    if not os.path.exists(check_list_path):
        print("final_check_list.txt 파일이 없습니다.")
        return

    with open(check_list_path, "r", encoding="utf-8") as f:
        for line in f:
            if "ID: " in line:
                # ID 추출 (예: koa_10005024_001)
                parts = line.split("ID: ")
                if len(parts) > 1:
                    art_id = parts[1].split(" |")[0].strip()
                    target_ids.add(art_id)

    print(f"추출 대상 ID {len(target_ids)}건 확인됨. 본문 수집 시작...")

    # 2. XML 파일을 뒤져서 해당 ID의 기사 본문 수집
    collected_data = []
    files = [f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f]

    for filename in files:
        file_path = os.path.join(target_dir, filename)
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            for article in root.findall(".//article"):
                art_id = article.get("id")
                if art_id in target_ids:
                    # 현재 상태(sentences가 있는지, 아니면 original/translation만 있는지) 확인
                    sents_node = article.find("sentences")
                    t_node = article.find("translation")
                    o_node = article.find("original")
                    
                    content_str = f"ID: {art_id}\n"
                    
                    if sents_node is not None:
                        # 이미 쪼개진 경우, s_id별로 수집
                        for s in sents_node.findall("s"):
                            sid = s.get("id")
                            orig = s.find("original").text if s.find("original") is not None else ""
                            trans = s.find("translation").text if s.find("translation") is not None else ""
                            content_str += f"  [s_id {sid}]\n  원문: {orig.strip()}\n  번역: {trans.strip()}\n"
                    elif t_node is not None and o_node is not None:
                        # 아직 안 쪼개진 경우
                        content_str += f"  [통문장]\n  원문: {o_node.text.strip()}\n  번역: {t_node.text.strip()}\n"
                    
                    collected_data.append(content_str + "-"*50 + "\n")
                    # 찾은 ID는 세트에서 제거 (중복 방지 및 속도 향상)
                    # target_ids.remove(art_id) # 루프 중 제거는 위험하므로 생략
        except:
            continue

    # 3. 결과 저장
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"=== 파이널 체크 대상 {len(collected_data)}건 본문 데이터 ===\n\n")
        f.writelines(collected_data)

    print(f"수집 완료! '{output_file}' 파일을 저에게 보내주시면 됩니다.")

if __name__ == "__main__":
    extract_targets()