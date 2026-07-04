"""특정 파일 목록만 삭제 후 재처리"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import DB
from src.extractor import extract_parcels
from src.parser import extract_text, parse_filename

NOTICES_DIR = Path(__file__).parent.parent / "data" / "notices"

FILES = [
    "0038_북부지방산림청고시제2025-4호(산림보호구역 지정해제 고시).pdf",
    "0043_북부지방산림청고시제2024-18호(산림보호구역(산림유전자원보호구역) 지정 고시).pdf",
    "0066_북부지방산림청고시제2023-28호(산림보호구역 지정해제 고시).pdf",
    "0117_북부지방산림청고시제2022-2호(산림보호구역 신규·재지정 고시).pdf",
    "0208_북부지방산림청고시제2020-4호(산림보호구역 신규·재지정).pdf",
    "0500_남부지방산림청고시제2013-10호(산림유전자원보호구역 지정 및 지형도면).pdf",
    "0514_북부지방산림청고시제2013-8호(산림보호구역 지정해제).pdf",
    "0525_북부지방산림청고시제2013-3호(산림유전자원보호구역 지정).pdf",
    "0539_서부지방산림청고시제2012-4호(산림유전자원보호구역 지정 및 지형도면).pdf",
    "0590_남부지방산림청고시제2011-18호(산림보호구역 지정_산림유전자원보호구역_).pdf",
    "0646_동부지방산림청고시제2010-8호(산림유전자원보호구역 지정·해제 및 도면).pdf",
    "0674_동부지방산림청고시제2010-4호(산림유전자원보호구역 해제, 통합 재고시).pdf",
    "0689_동부지방산림청고시제2009-14호(산림유전자원보호림 지정 및 지형도면).pdf",
    "0774_남부지방산림청고시제2007-10호(산림유전자원보호림지정).pdf",
    "0801_동부지방산림청고시제2006-11호(산림유전자원보호림 지정).pdf",
    "0819_남부지방산림관리청고시제2005-7호(산림유전자원보호림지정).pdf",
    "0820_동부지방산림관리청고시제2005-5호(산림유전자원보호림 지정).pdf",
    "0841_서부지방산림관리청고시제2002-9호(산림유전자원보호림지정).pdf",
    "0843_서부지방산림관리청고시제2001-4호(산림유전자원보호림지정).pdf",
    "0846_남부지방산림관리청고시제2001-2호(산림유전자원보호림및입산통제구역지정).pdf",
]

def main():
    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])

    # 삭제
    with conn.cursor() as cur:
        for f in FILES:
            cur.execute('DELETE FROM fgrr_notices WHERE "파일명" = %s', (f,))
            print(f"[삭제] {f} ({cur.rowcount}행)")
    conn.commit()
    conn.close()

    # 재처리
    db = DB(os.environ["DATABASE_URL"])
    total = 0
    for i, filename in enumerate(FILES, 1):
        pdf_path = NOTICES_DIR / filename
        print(f"\n[{i}/{len(FILES)}] {filename}")
        meta = parse_filename(filename)
        try:
            text = extract_text(str(pdf_path))
        except Exception as e:
            print(f"  [오류] PDF 추출: {e}")
            continue
        if not text.strip():
            print(f"  [경고] 텍스트 없음")
            continue
        try:
            parcels = extract_parcels(text, meta)
        except Exception as e:
            print(f"  [오류] Claude 추출: {e}")
            continue
        if not parcels:
            print(f"  [경고] 필지 없음")
            db.insert_rows([{**meta, "raw_text": text}])
            continue
        for p in parcels:
            p["raw_text"] = text
            if "유전자원보호구역_여부" not in p:
                p["유전자원보호구역_여부"] = meta.get("유전자원보호구역_여부")
        db.insert_rows(parcels)
        print(f"  → {len(parcels)}개 필지")
        total += len(parcels)

    # 유전자원보호구역_여부 업데이트
    import psycopg2
    conn2 = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn2.cursor() as cur:
        cur.execute('UPDATE fgrr_notices SET "유전자원보호구역_여부" = ("지정유형" LIKE \'%유전자원%\') WHERE "유전자원보호구역_여부" IS NULL')
    conn2.commit()
    conn2.close()

    db.close()
    print(f"\n완료: 총 {total}개 필지 저장")

if __name__ == "__main__":
    main()
