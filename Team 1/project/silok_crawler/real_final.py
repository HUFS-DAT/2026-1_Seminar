import os
import xml.etree.ElementTree as ET
import re

# ==========================================
# 1. 사용자 설정
# ==========================================
target_dir = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final - 복사본"
TARGET_YEAR_FILES = ["sillok_"]  # 광해군일기 등 대상 파일 접두사

def load_direct_ids():
    path = os.path.join(target_dir, "list_direct.txt")
    if not os.path.exists(path):
        print("❌ list_direct.txt 파일을 찾을 수 없습니다. matching.py를 먼저 실행하세요.")
        return set()
    with open(path, "r", encoding="utf-8") as f:
        # "ID: koa_10002001_001 | Count: 5" 형태에서 ID만 추출
        return {line.split("|")[0].replace("ID:", "").strip() for line in f if "ID:" in line}

# ==========================================
# 2. V71 통합 코어 엔진 (리스트 복구 & 정밀 봉인)
# ==========================================
QUOTE_CHARS = r'["”’“‘]'

# 💡 [forward merge] 다음 문장과 합침 (화자 선언)
SPEAKER_KO = re.compile(r'(?:전교하였다|아뢰기를|답하였다|계하였다|이르기를|하였다|했다|가로되|논의는|의논은)[.?,!\s]*$')

# 💡 [backward merge] 앞 문장과 합침 (인사 발령 파편)
APPOINT_KO = re.compile(r'^(?:삼았다|제수하였다|임명하였다|하였다|했다)')
APPOINT_ZH = re.compile(r'^(?:爲|授|除|以)')

# 💡 [V71 핵심] BRIDGE_KO 최적화
# '했고', '했으며', '했으므로'를 제거하여 리스트형 기사의 1:1 매칭을 복구함.
# '하였으며'는 남겨두어 내용 밀림이 의심되는 기사를 안전하게 Seal(봉인) 처리하도록 유도함.
BRIDGE_KO = re.compile(r'^"?\s*(?:(?:하였으며|였으며|하니|하고|하매|하사|하오니|하소서|고 하니|라고 하니|이라 하여|라고 하니|이라 하며|라 하며|고 하여|고 하매)[.,\s]*)+')

FORCE_SPLIT_KO = ["따랐다.", "알았다.", "따르지 않았다."]

def get_refined_indices(text, is_original=False):
    if not text: return []
    # 문장부호 뒤에 따옴표가 붙은 경우까지 포함해서 자름
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
    if start < len(text) and text[start:].strip():
        parts.append(text[start:].strip())
    
    # 기호 파편 유실 방지 로직 (데이터 누락 방어)
    cleaned = []
    for p in parts:
        if cleaned and not re.search(r'[가-힣a-zA-Z0-9\u4E00-\u9FD5]', p):
            cleaned[-1] += " " + p
        else:
            cleaned.append(p)
            
    res = []
    i = 0
    while i < len(cleaned):
        curr = cleaned[i]
        
        # 1️⃣ 원문 콜론(:) 전방 결합
        if is_original and i < len(cleaned) - 1 and re.search(r'[:：]["”’]?$', curr):
            cleaned[i+1] = curr + " " + cleaned[i+1]; i += 1; continue

        # 2️⃣ 국문 화자 선언문 전방 결합
        if not is_original and i < len(cleaned) - 1 and SPEAKER_KO.search(curr):
            cleaned[i+1] = curr + " " + cleaned[i+1]; i += 1; continue
            
        # 3️⃣ 인사 기사 파편 후방 결합
        if len(res) > 0:
            is_frag = (is_original and APPOINT_ZH.match(curr)) or (not is_original and APPOINT_KO.match(curr))
            if is_frag:
                res[-1] = f"{res[-1]} {curr}"; i += 1; continue

        # 4️⃣ 국문 브릿지(연결어미) 후방 결합
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

def update_xml_article(article, of, tf):
    sents = article.find("sentences")
    if sents is not None:
        [sents.remove(s) for s in list(sents)]
    else:
        sents = ET.SubElement(article, "sentences")
    
    # 기존 원본 노드들 제거
    for tag in ["original", "translation"]:
        node = article.find(tag)
        if node is not None:
            article.remove(node)
            
    for i, (o, t) in enumerate(zip(of, tf), 1):
        sn = ET.SubElement(sents, "s", id=str(i))
        ET.SubElement(sn, "original").text = o
        ET.SubElement(sn, "translation").text = t

# ==========================================
# 3. 메인 실행 로직
# ==========================================
def run_save():
    direct_ids = load_direct_ids()
    all_files = sorted([f for f in os.listdir(target_dir) if f.endswith(".xml") and "filtering" not in f])
    target_files = [f for f in all_files if any(t in f for t in TARGET_YEAR_FILES)]
    
    print(f"🚀 총 {len(target_files)}개 파일 V71 엔진 XML 반영 시작...")

    for filename in target_files:
        file_path = os.path.join(target_dir, filename)
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            modified = False

            for article in root.findall(".//article"):
                art_id = article.get("id")
                orig_node = article.find("original")
                trans_node = article.find("translation")
                
                # 이미 sentences로 변환된 기사는 건너뜀 (안전 장치)
                if orig_node is None or trans_node is None:
                    continue
                    
                ot = orig_node.text or ""
                tt = trans_node.text or ""
                
                # 💡 Direct 리스트에 있으면 정밀 분할, 없으면 통블록 보존
                if art_id in direct_ids:
                    o_p = split_and_clean(ot, True)
                    t_p = split_and_clean(tt, False)
                    update_xml_article(article, o_p, t_p)
                else:
                    update_xml_article(article, [ot], [tt])
                
                modified = True
            
            if modified:
                ET.indent(tree, space="  ")
                tree.write(file_path, encoding="utf-8", xml_declaration=True)
                print(f"✅ {filename} 반영 완료")
                
        except Exception as e:
            print(f"❌ {filename} 처리 중 오류 발생: {e}")
            continue

if __name__ == "__main__":
    run_save()