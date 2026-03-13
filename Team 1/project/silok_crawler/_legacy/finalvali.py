import os
import xml.etree.ElementTree as ET
import random

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
output_file = "final_full_sample_10000.txt"
sample_count = 10000

def run_full_sampling():
    all_article_refs = []
    print("1. 전체 XML 파일에서 기사 위치 정보 수집 중...")

    # 파일 목록 확보
    xml_files = [f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f]
    
    for filename in xml_files:
        file_path = os.path.join(target_dir, filename)
        try:
            # 기사 ID만 먼저 수집 (메모리 절약)
            tree = ET.parse(file_path)
            root = tree.getroot()
            for article in root.findall(".//article"):
                art_id = article.get("id")
                # 파일명과 기사 ID를 튜플로 저장
                all_article_refs.append((file_path, art_id))
        except Exception as e:
            print(f"파일 읽기 오류 ({filename}): {e}")

    total_articles = len(all_article_refs)
    print(f"총 발견된 기사: {total_articles}건")

    if total_articles < sample_count:
        print(f"경고: 전체 기사가 {sample_count}건보다 적습니다. 전체를 추출합니다.")
        sampled_refs = all_article_refs
    else:
        # 2. 10,000건 무작위 샘플링
        print(f"2. {sample_count}건 무작위 샘플링 중...")
        sampled_refs = random.sample(all_article_refs, sample_count)

    # 빠른 조회를 위해 파일별로 정렬
    sampled_refs.sort()

    # 3. 샘플링된 기사 본문 추출 및 저장
    print("3. 샘플링된 기사 본문 추출 및 리포트 작성 중...")
    
    current_file = ""
    current_root = None
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"=== 조선왕조실록 전체 데이터셋 최종 샘플 (무작위 {len(sampled_refs)}건) ===\n")
        f.write(f"총 기사 수: {total_articles} | 샘플 수: {len(sampled_refs)}\n\n")

        for i, (file_path, target_id) in enumerate(sampled_refs, 1):
            # 파일이 바뀔 때만 새로 파싱 (속도 최적화)
            if file_path != current_file:
                current_file = file_path
                tree = ET.parse(file_path)
                current_root = tree.getroot()
            
            # 해당 ID 기사 찾기
            article = current_root.find(f".//article[@id='{target_id}']")
            if article is not None:
                f.write(f"[{i}] 기사 ID: {target_id}\n")
                sents_node = article.find("sentences")
                
                if sents_node is not None:
                    s_tags = sents_node.findall("s")
                    for s in s_tags:
                        sid = s.get("id")
                        orig = s.find("original").text.strip() if s.find("original") is not None else ""
                        trans = s.find("translation").text.strip() if s.find("translation") is not None else ""
                        f.write(f"  s_id {sid}:\n    [원문] {orig}\n    [번역] {trans}\n")
                else:
                    # 혹시 sentences가 없는 경우 (통문장 대비)
                    orig = article.find("original").text.strip() if article.find("original") is not None else ""
                    trans = article.find("translation").text.strip() if article.find("translation") is not None else ""
                    f.write(f"  [통문장]\n    [원문] {orig}\n    [번역] {trans}\n")
                
                f.write("-" * 80 + "\n")
            
            if i % 500 == 0:
                print(f"진행 상황: {i}/{len(sampled_refs)}건 추출 완료")

    print(f"\n✨ 완료! '{output_file}' 파일에 10,000건의 샘플이 저장되었습니다.")

if __name__ == "__main__":
    run_full_sampling()