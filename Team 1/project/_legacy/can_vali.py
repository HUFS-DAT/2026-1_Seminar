import os
import xml.etree.ElementTree as ET
import random

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
success_file = os.path.join(target_dir, "filtering_success.txt")
output_file = os.path.join(target_dir, "rescued_validation_1000.txt")

def get_rescued_samples_1000(num_samples=1000):
    # 1. 기존 성공 ID (8.2만 건) 로드 -> 샘플링에서 제외
    if not os.path.exists(success_file):
        print("filtering_success.txt가 없습니다. 경로를 확인해주세요.")
        return

    with open(success_file, "r", encoding="utf-8") as f:
        original_success_ids = {line.split("|")[0].strip().replace("ID: ", "") for line in f}

    rescued_articles = []
    all_files = [f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f]
    
    print("구제된 기사 탐색 중 (Scope: Candidates only)...")
    for filename in all_files:
        file_path = os.path.join(target_dir, filename)
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            # [수정 포인트] try 블록 내부 또는 바로 다음에 올바르게 정렬되어야 함
            for article in root.findall("article"):
                art_id = article.get("id")
                sents_node = article.find("sentences")
                
                # 조건: <sentences>가 있고 + 기존 8.2만 건 목록엔 없는 '순수 구제 기사'
                if sents_node is not None and art_id not in original_success_ids:
                    s_tags = sents_node.findall("s")
                    if s_tags:
                        rescued_articles.append((art_id, s_tags))
        except Exception as e:
            continue

    print(f"발견된 총 구제 기사: {len(rescued_articles)}개")

    if not rescued_articles:
        print("구제된 기사가 하나도 없습니다. 이전에 구제 로직을 돌렸는지 확인해주세요.")
        return

    # 1000개 무작위 샘플링
    sample_size = min(len(rescued_articles), num_samples)
    samples = random.sample(rescued_articles, sample_size)

    # 파일 저장
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"=== 구제된(Rescued) 후보군 1000개 정밀 검증 ===\n")
        f.write("핵심 체크: 강제 병합된 문장(보통 긴 문장)의 한자와 한글 뜻이 1:1로 일치하는가?\n\n")
        
        for i, (art_id, s_tags) in enumerate(samples, 1):
            f.write(f"[{i}] 기사 ID: {art_id} (문장 수: {len(s_tags)})\n")
            for s in s_tags:
                sid = s.get('id')
                # 데이터가 없을 경우를 대비해 안전하게 추출
                orig_node = s.find('original')
                trans_node = s.find('translation')
                orig = orig_node.text if orig_node is not None else ""
                trans = trans_node.text if trans_node is not None else ""
                
                f.write(f"  s_id {sid}:\n")
                f.write(f"    [원문] {orig}\n")
                f.write(f"    [번역] {trans}\n")
            f.write("-" * 80 + "\n")

    print(f"완료! '{output_file}'에 {sample_size}개의 샘플이 저장되었습니다.")

if __name__ == "__main__":
    get_rescued_samples_1000(1000)