import os
import xml.etree.ElementTree as ET
import random

target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
sample_output_file = "ai_audit_100.txt"
sample_count = 100

def extract_hardcore_100():
    print(f"🔥 AI 한계 테스트: 초고난도 {sample_count}건 샘플링 중...")
    hardcore_candidates = []
    
    xml_files = [f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f]
    
    for filename in xml_files:
        try:
            tree = ET.parse(os.path.join(target_dir, filename))
            for article in tree.getroot().findall(".//article"):
                sents = article.find("sentences")
                if sents is not None:
                    s_tags = sents.findall("s")
                    # 조건: 문장이 10개 이상으로 아주 잘게 쪼개졌거나, 
                    # 원문/번역문 전체 길이 차이가 3배 이상 나는 '의심스러운' 기사
                    o_len = sum(len(s.find("original").text or "") for s in s_tags)
                    t_len = sum(len(s.find("translation").text or "") for s in s_tags)
                    
                    if len(s_tags) >= 10 or (o_len > 0 and (t_len/o_len > 3 or t_len/o_len < 0.8)):
                        hardcore_candidates.append((os.path.join(target_dir, filename), article.get("id")))
        except: continue

    print(f"발견된 고난도 후보군: {len(hardcore_candidates)}건")
    
    sampled = random.sample(hardcore_candidates, min(len(hardcore_candidates), sample_count))
    sampled.sort()

    with open(sample_output_file, "w", encoding="utf-8") as f:
        f.write(f"=== AI 극한 독해 검증 샘플 (악질 {len(sampled)}건) ===\n\n")
        for i, (path, aid) in enumerate(sampled, 1):
            article = ET.parse(path).getroot().find(f".//article[@id='{aid}']")
            f.write(f"[{i}] ID: {aid}\n")
            for s in article.find("sentences").findall("s"):
                f.write(f"  s_id {s.get('id')}:\n    [원문] {s.find('original').text}\n    [번역] {s.find('translation').text}\n")
            f.write("-" * 80 + "\n")
            
    print(f"✅ 완료! '{sample_output_file}' 파일이 생성되었습니다.")

if __name__ == "__main__":
    extract_hardcore_100()