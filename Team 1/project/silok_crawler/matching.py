import os
import xml.etree.ElementTree as ET
import re

# ==========================================
#  1. 사용자 설정 (원본으로 덮어쓴 경로)
# ==========================================
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
output_direct = os.path.join(target_dir, "list_direct.txt") 
output_ai     = os.path.join(target_dir, "list_ai.txt")     
output_seal   = os.path.join(target_dir, "list_seal.txt")   

RATIO_LOWER_BOUND = 0.15
RATIO_UPPER_BOUND = 8.0
MAX_SENTENCE_LIMIT = 45 # 45문장 넘어가면 AI 연산 효율 급감으로 봉인
QUOTE_CHARS = r'["”’“‘]'

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text).strip()

def get_sentence_count(text, is_original=False):
    if not text: return 0
    # 원문은 '。', 번역문은 '.' 기준
    pattern = r'[。?!]' if is_original else r'[.?!]'
    
    # 따옴표 성역 계산
    quote_ranges = []
    quotes = [m.start() for m in re.finditer(QUOTE_CHARS, text)]
    for i in range(0, len(quotes) - 1, 2):
        quote_ranges.append((quotes[i], quotes[i+1]))
        
    all_ends = list(re.finditer(pattern, text))
    count = 0
    for m in all_ends:
        # 1. 따옴표 내부 무시
        if any(start < m.start() < end for start, end in quote_ranges):
            continue
        
        # 2. 번역문일 경우 따옴표 뒤 7글자 보호 (Jean's Rule)
        if not is_original:
            is_7char_protected = False
            for q_end in [r[1] for r in quote_ranges]:
                if q_end < m.start() <= q_end + 7:
                    is_7char_protected = True; break
            if is_7char_protected: continue
            
        count += 1
    return max(1, count)

def run_triage():
    direct, ai, seal = [], [], []
    
    # 폴더 내 모든 XML 파일 스캔
    files = [f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f]
    print(f"📂 총 {len(files)}개 파일 원본 데이터 분석 시작...")

    for filename in files:
        try:
            tree = ET.parse(os.path.join(target_dir, filename))
            root = tree.getroot()
        except: continue

        for article in root.findall(".//article"):
            art_id = article.get("id")
            
            # 원문/번역문 텍스트 추출 (None 방지)
            orig_node = article.find("original")
            trans_node = article.find("translation")
            
            ot = clean_text(orig_node.text) if orig_node is not None else ""
            tt = clean_text(trans_node.text) if trans_node is not None else ""

            if not ot or not tt: continue

            o_cnt = get_sentence_count(ot, True)
            t_cnt = get_sentence_count(tt, False)
            ratio = len(tt) / len(ot) if len(ot) > 0 else 1

            # 🛡️ 분류 로직: 순도 100%를 위한 선별
            if o_cnt >= MAX_SENTENCE_LIMIT or ratio > RATIO_UPPER_BOUND or ratio < RATIO_LOWER_BOUND:
                seal.append(f"ID: {art_id} | O:{o_cnt}, T:{t_cnt}, R:{ratio:.2f}")
            elif o_cnt == t_cnt:
                direct.append(f"ID: {art_id} | Count: {o_cnt}")
            else:
                ai.append(f"ID: {art_id} | O:{o_cnt}, T:{t_cnt}")

    # 결과 저장
    for path, data in zip([output_direct, output_ai, output_seal], [direct, ai, seal]):
        with open(path, "w", encoding="utf-8") as f: f.write("\n".join(data))

    # 📊 최종 비율 보고
    total = len(direct) + len(ai) + len(seal)
    print("\n" + "="*45)
    print(f"📊 실록 코퍼스 전수 분류 결과 (총 {total}개)")
    print(f"✅ Direct (즉시 매칭) : {len(direct):>6}개 ({len(direct)/total*100:>5.1f}%)")
    print(f"🔬 AI (정제 대상)     : {len(ai):>6}개 ({len(ai)/total*100:>5.1f}%)")
    print(f"🔒 Seal (강제 봉인)    : {len(seal):>6}개 ({len(seal)/total*100:>5.1f}%)")
    print("="*45)

if __name__ == "__main__":
    run_triage()