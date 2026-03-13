import os
import xml.etree.ElementTree as ET
import random

# 설정
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
output_file = os.path.join(target_dir, "validation_samples.txt")

def get_large_samples(num_samples=1000):
    all_files = [f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f]
    
    all_valid_articles = []
    
    print("데이터 수집 중... 잠시만 기다려 주세요.")
    
    for filename in all_files:
        file_path = os.path.join(target_dir, filename)
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except: continue

        articles = root.findall("article")
        for article in articles:
            sents_node = article.find("sentences")
            if sents_node is not None:
                s_tags = sents_node.findall("s")
                # 문장이 2개 이상으로 쪼개진 의미 있는 샘플들만 수집
                if len(s_tags) > 1:
                    all_valid_articles.append((article.get("id"), s_tags))

    # 무작위로 100개 선택 (전체 개수가 1000개보다 적으면 전체 선택)
    sample_size = min(len(all_valid_articles), num_samples)
    samples = random.sample(all_valid_articles, sample_size)

    # 파일로 저장
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"=== 조선왕조실록 문장 분리 검증 샘플 (총 {sample_size}건) ===\n")
        f.write("주의 깊게 볼 점: 따옴표 뒤 서술어 붙음 현상, 원문-번역 매칭 정확도\n\n")
        
        for i, (art_id, s_tags) in enumerate(samples, 1):
            f.write(f"[{i}] 기사 ID: {art_id}\n")
            for s in s_tags:
                sid = s.get('id')
                orig = s.find('original').text
                trans = s.find('translation').text
                f.write(f"  s_id {sid}:\n")
                f.write(f"    [원문] {orig}\n")
                f.write(f"    [번역] {trans}\n")
            f.write("-" * 60 + "\n")

    print(f"작업 완료! '{output_file}' 파일에 1000개의 샘플이 저장되었습니다.")

if __name__ == "__main__":
    get_large_samples(1000)