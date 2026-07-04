import json
import os
import re

import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """당신은 한국 산림유전자원보호구역 관련 관보 고시 문서에서 데이터를 추출하는 전문가입니다.

PDF 텍스트를 분석하여 필지(토지 단위)별 데이터를 JSON 배열로 반환하세요.

## 추출 규칙
1. 표에서 각 행(필지)을 하나의 JSON 객체로 만드세요
2. 고시 메타데이터(날짜, 명칭 등)는 모든 row에 동일하게 포함하세요
3. 컬럼명이 아래 표준과 다르더라도 의미를 파악하여 표준 이름으로 매핑하세요
4. 표준에 없는 컬럼이 있으면 원래 이름 그대로 키로 사용하세요
5. 값이 없으면 null로 표시하세요
6. 어떤 데이터인지 애매하거나 표준 컬럼에 딱 맞지 않으면 버리지 말고 적절한 이름을 붙여 그대로 포함하세요 (데이터 손실 금지)

## 표준 컬럼명 매핑
- 소재지, 위치, 지역, 소재, 소재지(행정구역) → 소재지
- 지번, 번지, 필지번호 → 지번
- 임반, 소반 → 임반
- 지목, 지종 → 지목
- 소유자, 토지소유자, 성명 → 소유자
- 지적, 지적면적 → 지적
- 지정면적, 지정면적(㎡), 지정(㎡), 지정면적(m²) → 지정면적
- 해제면적, 해제(㎡), 해제면적(㎡) → 해제면적
- 잔여면적, 잔여(㎡), 잔여면적(㎡) → 잔여면적
- 해제사유, 해제이유, 지정해제사유, 사유 → 해제사유
- 명칭, 구역명, 보호구역명 → 명칭
- 고시날짜, 고시일, 고시일자, 날짜 → 고시날짜
- 비고, 참고, 기타 → 비고

## 지정유형 추출 (매우 중요)
- 각 필지마다 보호구역 유형을 반드시 `지정유형` 필드에 기록하세요
- 예: "산림유전자원보호구역", "제1종 수원함양보호구역", "경관보호구역" 등
- 한 고시 안에 여러 유형이 섞여 있을 수 있으므로 필지별로 개별 판단하세요
- 문서에 명시되지 않았다면 문맥에서 유추하세요

## 주의사항
- 면적 수치는 단위 포함 그대로 문자열로 저장하세요 (예: "1,234")
- 행이 여러 줄에 걸쳐 있을 수 있으니 주의하세요
- 반드시 JSON 배열만 반환하고 다른 설명 텍스트는 포함하지 마세요
- 추출할 데이터가 없으면 빈 배열 []을 반환하세요"""


CHUNK_SIZE = 6000  # 청크당 최대 글자 수 (필지 ~130개 기준)


def extract_parcels(text: str, meta: dict) -> list[dict]:
    """Claude API로 필지 데이터 추출 — 대용량은 청킹 처리"""
    if len(text) > CHUNK_SIZE:
        return _extract_chunked(text, meta)
    return _extract_single(text, meta)


def _extract_single(text: str, meta: dict) -> list[dict]:
    meta_str = f"""파일명: {meta.get('파일명', '')}
지방산림청: {meta.get('지방산림청', '')}
고시번호: {meta.get('고시번호', '')}
유형: {meta.get('유형', '')}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"{meta_str}\n\n--- 문서 내용 ---\n{text}",
            }
        ],
    )

    return _parse_response(response.content[0].text, meta)


def _extract_chunked(text: str, meta: dict) -> list[dict]:
    """긴 텍스트를 청크로 나눠 순차 처리"""
    chunks = _split_chunks(text, CHUNK_SIZE)
    all_parcels = []
    print(f"  [청킹] {len(chunks)}개 청크로 분할 처리")

    for i, chunk in enumerate(chunks, 1):
        meta_str = f"""파일명: {meta.get('파일명', '')}
지방산림청: {meta.get('지방산림청', '')}
고시번호: {meta.get('고시번호', '')}
유형: {meta.get('유형', '')}
[청크 {i}/{len(chunks)}] 이 텍스트는 전체 문서의 일부입니다. 이 청크에 있는 필지만 추출하세요."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"{meta_str}\n\n--- 문서 내용 (청크 {i}/{len(chunks)}) ---\n{chunk}",
                }
            ],
        )

        parcels = _parse_response(response.content[0].text, meta)
        print(f"    청크 {i}: {len(parcels)}개 필지")
        all_parcels.extend(parcels)

    return all_parcels


def _split_chunks(text: str, size: int) -> list[str]:
    """줄 단위로 청크 분할 (단어 중간 자르기 방지)"""
    lines = text.splitlines(keepends=True)
    chunks, current = [], ""
    for line in lines:
        if len(current) + len(line) > size and current:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


def _parse_response(raw: str, meta: dict) -> list[dict]:
    raw = raw.strip()
    json_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if json_match:
        raw = json_match.group(1)

    try:
        parcels = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [경고] JSON 파싱 실패: {raw[:200]}")
        return []

    if not isinstance(parcels, list):
        return []

    for parcel in parcels:
        for key in ["번호", "파일명", "지방산림청", "고시번호", "유형"]:
            if key not in parcel or not parcel[key]:
                parcel[key] = meta.get(key)

    return parcels
