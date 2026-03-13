import os
import xml.etree.ElementTree as ET
import re
import random
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ==========================================
# 1. 사용자 설정 및 타겟 년도 지정
# ==========================================
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
sealed_log_path = os.path.join(target_dir, "sealed_articles.txt")
sample_output_path = os.path.join(target_dir, "verification_samples.txt")

# --- V56 타겟: 광해 5, 인조 14, 숙종 15, 정조 18 ---
TARGET_YEAR_FILES = ["sillok_o_05"]

# --- 정밀도 파라미터 ---
SIMILARITY_THRESHOLD = 0.75
QUOTE_CHARS = r'["”’“‘]'
AI_SENTENCE_LIMIT = 30 # 30문장 넘는 AI 대상 기사는 가성비를 위해 봉인

model = None
if os.path.exists(sealed_log_path): os.remove(sealed_log_path)

def load_filter_ids(filename):
    path = os.path.join(target_dir, filename)
    if not os.path.exists(path): return set()
    with open(path, "r", encoding="utf-8") as f:
        # ID만 추출 (부가 정보 제외)
        return {line.split("|")[0].replace("ID:", "").strip() for line in f if "ID:" in line}

DIRECT_IDS = load_filter_ids("list_direct.txt")
AI_IDS     = load_filter_ids("list_ai.txt")
SEAL_IDS   = load_filter_ids("list_seal.txt")

# --- 정규표현식 보강 ---
BRIDGE_KO = re.compile(r'^"?\s*(?:하였더니|하였더라|하였거늘|하였으니|하니|함에|하매|하사|하였다|했다|하고|라 하고|고 하니|이라 하여|라고 하니|이라 하며|라 하며|이라 하였다|이라 했다|라고 하였다|라고 했다|라고 하며|고 하였다|고 했다|고 하며|고 하매|고 하여|아뢰기를|이르기를|답하기를|전교하였다|하소서|하오니|이와 같으니|했으므로|한지라|함이다)[.,\s]*')
BRIDGE_HJ = re.compile(r'^\s*(?:曰|云|答曰|啓曰|傳曰|议啓曰|判曰|供|供云|供曰|題|題曰|矣|也|焉|乎):?\s*["”’]?')

def load_model():
    global model
    if model is None:
        print("\n AI 모델 로딩 중 (V56 LLM Pure Gold)..."); model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# ------------------------------------------
#  2. 핵심 유틸리티 (Jean's Rule 통합)
# ------------------------------------------
def count_quotes(text): return len(re.findall(QUOTE_CHARS, text))

def get_refined_indices(text, is_original=False):
    if not text: return []
    pattern = r'[。\.?!\uFF1F\uFF01:]' if is_original else r'[.?!\uFF1F\uFF01]'
    quote_ranges = []
    quotes = [m.start() for m in re.finditer(QUOTE_CHARS, text)]
    for i in range(0, len(quotes) - 1, 2): quote_ranges.append((quotes[i], quotes[i+1]))
        
    all_matches = list(re.finditer(pattern, text))
    final_indices = []
    for m in all_matches:
        idx = m.end()
        if any(start < m.start() < end for start, end in quote_ranges): continue
        if not is_original: # 7글자 보호 룰
            if any(q_end < m.start() <= q_end + 7 for _, q_end in quote_ranges): continue
        final_indices.append(idx)
    return sorted(list(set(final_indices)))

def split_and_clean(text, indices, is_original=False):
    parts, start = [], 0
    for idx in indices:
        part = text[start:idx].strip()
        if part: parts.append(part)
        start = idx
    if start < len(text) and text[start:].strip(): parts.append(text[start:].strip())
    
    cleaned = []
    for p in parts:
        if not re.search(r'[가-힣a-zA-Z0-9\u4E00-\u9FD5]', p):
            if cleaned: cleaned[-1] += p
            else: cleaned.append(p)
        else:
            if cleaned and not re.search(r'[가-힣a-zA-Z0-9\u4E00-\u9FD5]', cleaned[-1]):
                prev = cleaned.pop(); cleaned.append(prev + p)
            else: cleaned.append(p)
    regex = BRIDGE_HJ if is_original else BRIDGE_KO
    final_parts = list(cleaned)
    for i in range(1, len(final_parts)):
        match = regex.match(final_parts[i])
        if match:
            bridge = match.group().strip()
            final_parts[i-1] = f"{final_parts[i-1]} {bridge}"
            final_parts[i] = final_parts[i][match.end():].strip()
    return [p.strip() for p in final_parts if p.strip()]

def update_xml_article(article, of, tf):
    sents = article.find("sentences")
    if sents is not None: [sents.remove(s) for s in list(sents)]
    else:
        for tag in ["original", "translation"]:
            node = article.find(tag)
            if node is not None: article.remove(node)
        sents = ET.SubElement(article, "sentences")
    for i, (o, t) in enumerate(zip(of, tf), 1):
        sn = ET.SubElement(sents, "s", id=str(i))
        ET.SubElement(sn, "original").text = o.strip()
        ET.SubElement(sn, "translation").text = t.strip()

# ==========================================
#  3. 통합 정제 프로세스 (Direct/AI 분기)
# ==========================================
def run_clean_v56():
    print(f"\n 주요 4개년도 정제 작업 시작")
    all_files = sorted([f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f])
    target_files = [f for f in all_files if any(t in f for t in TARGET_YEAR_FILES)]
    
    for filename in target_files:
        file_path = os.path.join(target_dir, filename)
        try: tree = ET.parse(file_path); root = tree.getroot()
        except: continue
        
        modified = False
        file_total, file_sealed = 0, 0
        
        for article in root.findall(".//article"):
            art_id = article.get("id")
            file_total += 1
            
            ot = article.find("original").text.strip() if article.find("original") is not None else ""
            tt = article.find("translation").text.strip() if article.find("translation") is not None else ""
            if not ot or not tt: continue

            of, tf = [], []
            reason = ""

            # 1. Direct 명단: 즉시 분할
            if art_id in DIRECT_IDS:
                of = split_and_clean(ot, get_refined_indices(ot, True), True)
                tf = split_and_clean(tt, get_refined_indices(tt, False), False)
                if len(of) != len(tf): of, tf = [ot], [tt]; reason = "패리티불일치"

            # 2. AI 명단: 정밀 수술
            elif art_id in AI_IDS:
                load_model()
                op_raw = split_and_clean(ot, get_refined_indices(ot, True), True)
                tp_raw = split_and_clean(tt, get_refined_indices(tt, False), False)
                
                # 가성비 체크: 문장 너무 많으면 패스
                if len(op_raw) > AI_SENTENCE_LIMIT:
                    of, tf = [ot], [tt]; reason = "AI문장초과"
                else:
                    print(f"  [정제 중] {art_id}          ", end="\r")
                    o_sync, t_sync = [], []
                    oi, ti = 0, 0
                    while oi < len(op_raw) and ti < len(tp_raw):
                        co, ct = op_raw[oi], tp_raw[ti]
                        while (count_quotes(co) % 2 != count_quotes(ct) % 2) and (oi + 1 < len(op_raw) or ti + 1 < len(tp_raw)):
                            if count_quotes(co) % 2 == 1 and oi + 1 < len(op_raw): oi += 1; co += " " + op_raw[oi]
                            elif count_quotes(ct) % 2 == 1 and ti + 1 < len(tp_raw): ti += 1; ct += " " + tp_raw[ti]
                            else: break
                        o_sync.append(co); t_sync.append(ct); oi += 1; ti += 1
                    
                    # SBERT 매칭 로직 (V55.1 기반)
                    v_t = model.encode(t_sync, show_progress_bar=False)
                    oi, ti = 0, 0
                    while ti < len(t_sync):
                        curr_v_t = v_t[ti].reshape(1, -1)
                        max_sim, best_step = -1, 1
                        for step in range(1, 4):
                            if oi + step > len(o_sync): break
                            sim = cosine_similarity(model.encode([" ".join(o_sync[oi:oi+step])], show_progress_bar=False), curr_v_t)[0][0]
                            if sim > max_sim: max_sim = sim; best_step = step
                        if max_sim < SIMILARITY_THRESHOLD: of, tf = [ot], [tt]; reason = "유사도부족"; break
                        of.append(" ".join(o_sync[oi:oi+best_step])); tf.append(t_sync[ti])
                        oi += best_step; ti += 1
                    if len(of) != len(tf): of, tf = [ot], [tt]; reason = "AI패리티실패"

            # 3. Seal 명단 혹은 기타
            else:
                of, tf = [ot], [tt]; reason = "강제봉인"

            if reason: 
                file_sealed += 1
                with open(sealed_log_path, "a", encoding="utf-8") as f: f.write(f"ID: {art_id} | 사유: {reason}\n")
            
            update_xml_article(article, of, tf); modified = True
        
        if file_total > 0: print(f"  📄 {filename}: 봉인율 {(file_sealed/file_total)*100:.1f}%")
        if modified: ET.indent(tree, space="  "); tree.write(file_path, encoding="utf-8", xml_declaration=True)
    print(f"✅ 정제 완료")

def export_samples(n=50):
    all_articles = []
    files = [f for f in os.listdir(target_dir) if any(t in f for t in TARGET_YEAR_FILES) and f.endswith(".xml")]
    for f in files:
        tree = ET.parse(os.path.join(target_dir, f))
        for art in tree.findall(".//article"):
            sents = art.find("sentences")
            if sents is not None and len(sents.findall("s")) > 0: all_articles.append(art)
    if not all_articles: return
    samples = random.sample(all_articles, min(n, len(all_articles)))
    with open(sample_output_path, "w", encoding="utf-8") as f:
        f.write("=== V56 LLM Pure Gold 샘플 50선 ===\n\n")
        for art in samples:
            f.write(f"ID: {art.get('id')}\n")
            for s in art.find("sentences").findall("s"):
                f.write(f"  [S {s.get('id')}]\n  O: {s.find('original').text}\n  T: {s.find('translation').text}\n")
            f.write("-" * 50 + "\n")

if __name__ == "__main__":
    run_clean_v56()
    export_samples(50)