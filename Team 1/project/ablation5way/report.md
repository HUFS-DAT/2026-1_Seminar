# Gemma-4-26B 승정원일기 번역 프롬프트 튜닝 보고서

## 1. 개요

- **모델**: `gemma-4-26b-a4b-it` (Google Generative Language API, temperature=0.0)
- **태스크**: 승정원일기 한문 원문 → 현대 한국어 번역
- **코퍼스**: Merged_Corpus_Final.json (인조 재위 전체, 62,476개)
- **실험 방식**: 파라미터 튜닝 없이 프롬프트 엔지니어링 + 후처리만 사용

---

## 2. Eval Set 설계

### eval300 (eval300_1925.json)

- **모집단**: eval_set_1925.json — 62K 전체에서 설계한 대표 샘플 1,925개
- **샘플링**: 길이 버킷(XS/S/M/L) × 패턴 교차 셀 비례 샘플링, `random.seed(42)`
- **크기**: 300개

| 길이 | 기준 | n | 비율 |
|------|------|---|------|
| XS | <50자 | 133 | 44.3% |
| S | 50–149자 | 104 | 34.7% |
| M | 150–349자 | 43 | 14.3% |
| L | 350자+ | 20 | 6.7% |

| 패턴 | n | 비율 |
|------|---|------|
| GEN (일반) | 142 | 47.3% |
| REP (아뢰기, 啓曰) | 135 | 45.0% |
| DEN (불허, 不許) | 9 | 3.0% |
| MEM (장계/서계) | 7 | 2.3% |
| ROY/APT/APR | 7 | 2.3% |

### NER 정답지 (ner_groundtruth_300.json)

- **방법**: SillokBERT-NER (`ddokbaro/SillokBert-NER`) → 한문 원문에서 개체명 자동 추출
- **말모이 매핑**: 한자 개체명 → 한글명 (person_master.json, 33,002개)
- **결과**: 300개 중 188개 항목에 엔티티 존재, 총 385개 개체명
- **공정성**: 정답 번역문(reference) 미사용 — 원문 + KB만으로 구성

---

## 3. 실험 조건

### 3.1 Baseline

단순 번역 지시만 포함, 예시·스타일 가이드 없음.

```
다음 한문을 현대 한국어로 번역하세요. 번역문만 출력하세요:
{원문}
```

### 3.2 Few-shot

고정 예시 삽입. 아뢰기/전교/윤허/제수/장계/거둥/일반 등 다양한 패턴 포함.

**프롬프트 구성**:
- 역할: "승정원일기 전문 번역가"
- 번역 원칙 5개 (종결어미, 왕 지칭, 신하 자칭, 인용 형식, 관직·인명)
- 현대어 금지 7쌍 (임명→제수, 허락→윤허, 행차→거둥 등)
- 고정 예시 8개 (패턴 다양성 확보)
- 원문 패턴 동적 주입 (9개 규칙, 예: 傳敎曰 감지 시 "전교하기를" 사용 명시)

**오버피팅 방지**: 예시는 eval set과 완전 독립 수동 작성, eval 점수 보고 프롬프트 수정 없음.

### 3.3 Few-shot + NER 후처리

Few-shot 번역 결과에 말모이 기반 개체명 교정을 후처리로 적용.

**파이프라인**:
1. SillokBERT-NER로 한문 원문에서 개체명 추출 (ner_groundtruth_300.json에 사전 계산)
2. person_master.json(말모이)에서 한자명 → 한글명 조회
3. 번역문 내 해당 개체명 미존재 시 교정 시도:
   - `hanja` 라이브러리로 한자 → 표준 음독 변환
   - 성씨 앵커 + 이름 길이 기반 오독(誤讀) 탐색
   - 발견 시 정답 한글명으로 치환

**교정 결과**:
- 전체 385개 엔티티 중 88개 누락
- 교정 성공: 54개 (단순 음독 오류 케이스)
- 교정 불가: 34개 (이름 아예 생략된 케이스)

---

## 4. 최종 결과 (n=300)

| 조건 | BLEU(c) | chrF(c) | BLEU(m) | chrF(m) | NER |
|------|---------|---------|---------|---------|-----|
| baseline | 35.57 | 30.86 | 27.38 | 32.50 | 0.787 |
| few-shot | 39.59 | 34.46 | 31.95 | 35.83 | 0.771 |
| **few+nerfix** | **39.75** | **34.61** | **32.12** | **35.97** | **0.909** |

| Δ (vs baseline) | BLEU(c) | chrF(c) | BLEU(m) | chrF(m) | NER |
|------|---------|---------|---------|---------|-----|
| Δ few-shot | +4.02 | +3.60 | +4.57 | +3.32 | −0.016 |
| Δ few+nerfix | **+4.18** | **+3.76** | **+4.74** | **+3.47** | **+0.122** |

> BLEU(c): 문자 단위, BLEU(m): 형태소(Kiwi) 단위, chrF: chrF++, NER: 개체명 포함률

---

## 5. 분석

### 5.1 Few-shot 효과

- BLEU(char) +4.02, chrF +3.60로 baseline 대비 유의미한 향상
- 종결어미(-하였다), 왕/신하 지칭, 실록 어투 전반이 개선
- NER recall은 오히려 소폭 하락 (−0.016): 예시가 어투에 집중하는 경향으로 인물명 음독 정확도는 개선 없음

### 5.2 NER 후처리 효과

- NER recall **0.771 → 0.909 (+12.2pp)**: 가장 큰 단일 개선
- 번역문 내 음독 오류 유형 확인: 한자를 틀린 음으로 읽는 케이스 (張維→장위/정답 장유, 李景曾→이경정/정답 이경증 등)
- BLEU/chrF도 소폭 추가 향상 (개체명 교정이 텍스트 정확도에도 기여)
- 후처리 공정성: 정답 번역문 미사용, 원문 + 말모이 KB만 사용

### 5.3 미교정 케이스 (34개)

- 번역문에 인물이 아예 누락된 경우 (장문 원문 번역 시 일부 생략)
- 후처리로 해결 불가 — 번역 단계에서 KB 주입(kb-inject 방식)으로 대응 가능

---

## 6. 재현 방법

```bash
# ablation5way/ 폴더에서 실행

# 1. 번역 실행
python run_fewshot.py          # few-shot 번역 (resume 지원)

# 2. NER 후처리
python postprocess_ner.py      # results300_fewshot_nerfix.jsonl 생성

# 3. 채점
python score_300.py            # 전체 지표 출력
```

**의존성**:
```
pip install openai tqdm sacrebleu kiwipiepy hanja transformers
```

API: Google Generative Language API, `gemma-4-26b-a4b-it`, temperature=0.0

---

## 7. 파일 구조

```
ablation5way/
├── eval300_1925.json                  # eval set (300개)
├── ner_groundtruth_300.json           # NER 정답지 (SillokBERT-NER + 말모이)
├── person_master.json                 # 말모이 인물 KB (33,002개)
├── fewshot_config.json                # few-shot 프롬프트 템플릿
│
├── results300_baseline.jsonl          # baseline 결과 (300개)
├── results300_fewshot.jsonl           # few-shot 결과 (300개)
├── results300_fewshot_nerfix.jsonl    # few+nerfix 결과 (300개)
│
├── run_fewshot.py                     # few-shot 번역 실행
├── postprocess_ner.py                 # NER 후처리
└── score_300.py                       # BLEU + chrF + NER 채점
```
