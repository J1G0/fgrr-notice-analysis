import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.db import DB
from src.extractor import extract_parcels
from src.parser import extract_text, parse_filename

NOTICES_DIR = Path(__file__).parent / "data" / "notices"


def process_file(pdf_path: Path, db: DB) -> int:
    filename = pdf_path.name

    if db.already_processed(filename):
        print(f"[SKIP] {filename}")
        return 0

    print(f"[처리] {filename}")

    meta = parse_filename(filename)

    try:
        text = extract_text(str(pdf_path))
    except Exception as e:
        print(f"  [오류] PDF 추출 실패: {e}")
        return 0

    if not text.strip():
        print(f"  [경고] 텍스트 없음 (스캔본?)")
        return 0

    try:
        parcels = extract_parcels(text, meta)
    except Exception as e:
        print(f"  [오류] Claude 추출 실패: {e}")
        return 0

    if not parcels:
        print(f"  [경고] 필지 데이터 없음")
        db.insert_rows([{**meta, "raw_text": text}])
        return 0

    for parcel in parcels:
        parcel["raw_text"] = text
        if "유전자원보호구역_여부" not in parcel:
            parcel["유전자원보호구역_여부"] = meta.get("유전자원보호구역_여부")

    db.insert_rows(parcels)
    print(f"  → {len(parcels)}개 필지 저장")
    return len(parcels)


def main():
    db = DB(os.environ["DATABASE_URL"])

    pdf_files = sorted(NOTICES_DIR.glob("*.pdf"))
    print(f"총 {len(pdf_files)}개 PDF 처리 시작\n")

    total_parcels = 0
    failed = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}]", end=" ")
        try:
            count = process_file(pdf_path, db)
            total_parcels += count
        except Exception as e:
            print(f"  [오류] {e}")
            failed.append(pdf_path.name)

    db.close()

    print(f"\n완료: 총 {total_parcels}개 필지 저장")
    if failed:
        print(f"실패: {len(failed)}개")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    # 특정 파일만 테스트: python main.py <파일명>
    if len(sys.argv) > 1:
        load_dotenv()
        db = DB(os.environ["DATABASE_URL"])
        pdf_path = NOTICES_DIR / sys.argv[1]
        process_file(pdf_path, db)
        db.close()
    else:
        main()
