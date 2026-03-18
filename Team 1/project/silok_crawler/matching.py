import os
import xml.etree.ElementTree as ET
import re

# ==========================================
# 1. 사용자 설정
# ==========================================
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
output_direct = os.path.join(target_dir, "list_direct.txt") 
output_seal   = os.path.join(target_dir, "list_seal.txt")   

RATIO_LOWER_BOUND = 0.15
RATIO_UPPER_BOUND = 8.0
MAX_SENTENCE_LIMIT = 25

# ==========================================
# 2. V71 통합 코어 엔진 (리스트 복구 & 정밀 봉인)
# ==========================================
QUOTE_CHARS = r'["”’“‘]'

# 💡 [ forward merge ] 다음 문장과 합침 (화자 선언)
SPEAKER_KO = re.compile(r'(?:전교하였다|아뢰기를|답하였다|계하였다|이르기를|하였다|했다|가로되|논의는|의논은)[.?,!\s]*$')

# 💡 [ backward merge ] 앞 문장과 합침 (인사 발령)
APPOINT_KO = re.compile(r'^(?:삼았다|제수하였다|임명하였다|하였다|했다)')
APPOINT_ZH = re.compile(r'^(?:爲|授|除|以)')

# 💡 [V71 핵심 수정] BRIDGE_KO 다이어트
# '했고', '했으며'는 리스트에서 문장을 새로 시작하므로 제거했습니다 (1:1 매칭 복구)
# '하였으며', '였으며'는 도미노를 유발하므로 남겨서 'Seal' 처리를 유도합니다.
BRIDGE_KO = re.compile(r'^"?\s*(?:(?:하였으며|였으며|하니|하고|하매|하사|하오니|하소서|고 하니|라고 하니|이라 하여|라고 하니|이라 하며|라 하며|고 하여|고 하매)[.,\s]*)+')

FORCE_SPLIT_KO = ["따랐다.", "알았다.", "따르지 않았다."]

def get_refined_indices(text, is_original=False):
    if not text: return []
    # 문장부호 + 닫는 따옴표에서 일단 다 자름
    pattern = r'[。\.?!\uFF1F\uFF01:：]+["”’]?'
    matches = list(re.finditer(pattern, text))
    return sorted(list(set([m.end() for m in matches])))

def split_and_clean(text, is_original=False):
    indices = get_refined_indices(text, is_original)
    parts, start = [], 0
    for idx in indices:
        part = text[start:idx].strip()
        if part: parts.append(part)
        start = idx
    if start < len(text) and text[start:].strip(): parts.append(text[start:].strip())
    
    cleaned = []
    for p in parts:
        if cleaned and not re.search(r'[가-힣a-zA-Z0-9\u4E00-\u9FD5]', p):
            cleaned[-1] += " " + p
        else: cleaned.append(p)
            
    res = []
    i = 0
    while i < len(cleaned):
        curr = cleaned[i]
        # 1. 원문 콜론 전방 결합
        if is_original and i < len(cleaned) - 1 and re.search(r'[:：]["”’]?$', curr):
            cleaned[i+1] = curr + " " + cleaned[i+1]; i += 1; continue
        # 2. 국문 화자 전방 결합
        if not is_original and i < len(cleaned) - 1 and SPEAKER_KO.search(curr):
            cleaned[i+1] = curr + " " + cleaned[i+1]; i += 1; continue
        # 3. 인사 발령 후방 결합
        if len(res) > 0:
            is_frag = (is_original and APPOINT_ZH.match(curr)) or (not is_original and APPOINT_KO.match(curr))
            if is_frag: res[-1] = f"{res[-1]} {curr}"; i += 1; continue
        # 4. 국문 브릿지 후방 결합 (정밀 타격용)
        if not is_original and len(res) > 0:
            is_forced = any(res[-1].endswith(w) for w in FORCE_SPLIT_KO)
            if not is_forced and BRIDGE_KO.match(curr):
                match = BRIDGE_KO.match(curr)
                res[-1] = f"{res[-1]} {match.group().strip()}"
                remained = curr[match.end():].strip()
                if remained: res.append(remained)
                i += 1; continue
        res.append(curr); i += 1
    return [p.strip() for p in res if p.strip()]

def run_triage():
    direct, seal = [], []
    files = [f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f]
    for filename in files:
        try:
            tree = ET.parse(os.path.join(target_dir, filename))
            for article in tree.findall(".//article"):
                art_id = article.get("id")
                ot, tt = article.find("original").text or "", article.find("translation").text or ""
                o_p, t_p = split_and_clean(ot, True), split_and_clean(tt, False)
                o_cnt, t_cnt = len(o_p), len(t_p)
                
                # 💡 [V72 판정 로직 수정]
                # 1. 개수가 같고 (o_cnt == t_cnt)
                # 2. 문장 수가 제한(25개) 이하이며 (o_cnt <= MAX_SENTENCE_LIMIT)
                # 3. 전체 글자 비율이 정상 범위일 때만 Direct
                if o_cnt == t_cnt and 0 < o_cnt <= MAX_SENTENCE_LIMIT and RATIO_LOWER_BOUND < len(tt)/len(ot) < RATIO_UPPER_BOUND:
                    direct.append(f"ID: {art_id} | Count: {o_cnt}")
                else:
                    seal.append(f"ID: {art_id} | O:{o_cnt}, T:{t_cnt}")
        except: continue
    with open(output_direct, "w", encoding="utf-8") as f: f.write("\n".join(direct))
    with open(output_seal, "w", encoding="utf-8") as f: f.write("\n".join(seal))
    print(f"✅ V72 정밀 분석 완료: Direct {len(direct)}, Seal {len(seal)}")

if __name__ == "__main__":
    run_triage()