import os
import re
import xml.etree.ElementTree as ET
from glob import glob

# 현재 손상된 파일들이 있는 폴더 경로 (수정 필요)
TARGET_DIR = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final"
OUTPUT_LIST_FILE = "need_recrawl_list.txt"

def is_suspicious(trans_text, orig_text):
    if not trans_text or not orig_text:
        return True, "텍스트 누락"
        
    kr_len = len(trans_text.replace(" ", ""))
    hj_len = len(orig_text.replace(" ", ""))
    
    if hj_len == 0 or kr_len == 0:
        return True, "텍스트 길이 0"

    # 1. 글자 수 비율 및 절대 길이 검사
    length_ratio = kr_len / hj_len
    abs_len_diff = abs(kr_len - hj_len)
    
    if hj_len < 30:
        # 짧은 기사는 극단적인 차이일 때만 (예: 원문 10자, 번역 100자)
        if kr_len > 100 and length_ratio > 8.0:
            return True, "짧은 기사 길이 비정상"
    else:
        # 번역문이 원문보다 4배 이상 길고 100자 이상 차이남 (원문 대량 유실)
        if length_ratio >= 4.0 and abs_len_diff >= 100:
            return True, "원문 대량 유실 의심"
            
        # 원문이 번역문보다 길거나 너무 비슷함 (번역 대량 유실)
        if length_ratio < 0.8 and (hj_len - kr_len) >= 50:
            return True, "번역 대량 유실 의심"

    # 2. 마침표(문장 맺음) 개수 검사
    kr_periods = len(re.findall(r'[.?!]', trans_text))
    hj_periods = len(re.findall(r'[。?!]', orig_text))
    
    # 한쪽만 맺음 기호가 아예 없는 경우
    if hj_periods == 0 and kr_periods > 1: return True, "원문 맺음기호 누락"
    if kr_periods == 0 and hj_periods > 1: return True, "번역 맺음기호 누락"
    
    # 둘 다 맺음 기호가 있을 때, 비율이 2배 이상 & 개수 차이가 3개 이상인 경우
    if hj_periods > 0 and kr_periods > 0:
        period_ratio = max(kr_periods, hj_periods) / min(kr_periods, hj_periods)
        if period_ratio >= 2.0 and abs(kr_periods - hj_periods) >= 3:
            return True, "맺음기호 비율 불일치"
            
    return False, "정상"

def find_corrupted_articles():
    xml_files = glob(os.path.join(TARGET_DIR, "*.xml"))
    if not xml_files:
        print("지정된 경로에 XML 파일이 없습니다.")
        return

    corrupted_ids = []
    print(f"총 {len(xml_files)}개의 파일에서 깐깐한 이상 탐지를 시작합니다...\n")
    
    for file_path in xml_files:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            for article in root.findall('article'):
                trans_elem = article.find('translation')
                orig_elem = article.find('original')
                
                if trans_elem is not None and orig_elem is not None:
                    is_bad, reason = is_suspicious(trans_elem.text, orig_elem.text)
                    if is_bad:
                        article_id = article.get('id')
                        if article_id:
                            corrupted_ids.append(article_id)
                            # 디버깅 용도로 어떤 이유로 걸렸는지 출력 (너무 길면 주석 처리 가능)
                            print(f"[{reason}] ID: {article_id}")
                            
        except Exception as e:
            print(f"파일 읽기 오류 ({os.path.basename(file_path)}): {e}")

    # 다시 크롤링할 ID 목록 저장 (중복 제거 후 정렬)
    corrupted_ids = sorted(list(set(corrupted_ids)))
    with open(OUTPUT_LIST_FILE, "w", encoding="utf-8") as f:
        for aid in corrupted_ids:
            f.write(aid + "\n")

    print(f"\n수색 완료! 총 {len(corrupted_ids)}개의 의심 문서 ID를 '{OUTPUT_LIST_FILE}'에 저장했습니다.")

if __name__ == "__main__":
    find_corrupted_articles()