import os
import re
import xml.etree.ElementTree as ET
from glob import glob

TARGET_DIR = r"C:\Users\kevin\OneDrive\Desktop\sillok_crawler\Sillok_Corpus_Final"

def clean_ml_corpus_safe(text, is_translation):
    if not text: return ""
    text = text.strip()

    # 1. 원문/국역 공통 꼬리표 통째로 날리기
    text = re.sub(r"【(태백산|정족산|오대산|적상산)사고본】.*", "", text)
    text = re.sub(r"【국편영인본】.*", "", text)
    text = re.sub(r"【분류】.*", "", text)

    if is_translation:
        # [수정 1] 저작권자가 누구든 'ⓒ' 뒤는 전부 싹둑! (세종대왕기념사업회 완벽 차단)
        text = re.sub(r"\[註\s*\d+\].*", "", text)
        text = re.sub(r"ⓒ.*", "", text) 
        text = re.sub(r"^국역\s*", "", text)
        text = re.sub(r"^\d{3}\)?", "", text)
        
        # [수정 2] 국역본에 섞여 있는 한자 완전 제거 (판부사判府事 -> 판부사)
        # 어차피 원문에 한자가 있으니 번역문에서는 한자를 싹 날려줍니다.
        text = re.sub(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\U00020000-\U0002FFFF]", "", text)
        
        # [수정 3] 주석 번호(예: 원서191) 찌꺼기 핀포인트 제거
        # 한글 뒤에 딱 붙은 2자리 이상의 숫자만 안전하게 날려버립니다.
        text = re.sub(r"(?<=[가-힣])\d{2,}(?=[ \t.,!?\n]|은|는|이|가|을|를|에|의|와|과|로|도)", "", text)

        # 설명충 문장 제거
        text = re.sub(r"(?:은|는|란|이란)\s+[^.!?]*(?:지칭함|뜻함)\.", "", text)
        text = re.sub(r"(?:은|는|란|이란)\s+[^.!?]+(?:을|를)\s+말함\.", "", text)
    else:
        # 원문 앞머리 및 기호 정리
        text = re.sub(r"^원문\s*", "", text).strip()
        text = text.replace("○", "") 
        text = re.sub(r"^[^/]{1,15}/.*?(?=\s)", "", text) # 날짜 헤더 제거

    # 2. 알맹이는 살리고 괄호 '기호' 자체만 지우기
    text = re.sub(r"[\(\)\[\]\{\}【】〈〉《》『』〔〕]", "", text)

    # 3. 다중 공백 정리
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
def process_corpus_files():
    if not os.path.exists(TARGET_DIR):
        print(f"경로가 존재하지 않습니다: {TARGET_DIR}")
        return

    xml_files = glob(os.path.join(TARGET_DIR, "*.xml"))
    print(f"총 {len(xml_files)}개 파일을 AI 학습용으로 정밀(안전) 정제합니다...\n")
    success_count = 0

    for file_path in xml_files:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            modified = False

            for article in root.findall('article'):
                for tag in ['translation', 'original']:
                    elem = article.find(tag)
                    if elem is not None and elem.text:
                        old_text = elem.text
                        cleaned_text = clean_ml_corpus_safe(old_text, is_translation=(tag == 'translation'))
                        
                        if cleaned_text != re.sub(r'\s+', ' ', old_text.strip()):
                            elem.text = cleaned_text
                            modified = True

            if modified:
                tree.write(file_path, encoding="utf-8", xml_declaration=True)
                print(f"✨ 정제 완료: {os.path.basename(file_path)}")
                success_count += 1

        except Exception as e:
            print(f"오류 발생 ({os.path.basename(file_path)}): {e}")

    print(f"\n🎉 작업 완료! {success_count}개 파일의 미세 노이즈가 완벽하게 제거되었습니다.")

if __name__ == "__main__":
    process_corpus_files()