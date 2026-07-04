"""0283 파일 직접 파싱 — Claude 없이 regex로 처리"""
import os
import re
import psycopg2
from dotenv import load_dotenv
import fitz

load_dotenv()

PDF_PATH = "data/notices/0283_북부지방산림청고시제2018-20호(산림유전자원보호구역 지정).pdf"
FILENAME = os.path.basename(PDF_PATH)

META = {
    "번호": "0283",
    "파일명": FILENAME,
    "지방산림청": "북부지방산림청",
    "고시번호": "2018-20",
    "유형": "지정",
    "고시날짜": "2018-07-19",
    "지정유형": "산림유전자원보호구역",
    "유전자원보호구역_여부": True,
}

def parse_pdf():
    doc = fitz.open(PDF_PATH)
    full_text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return full_text

def extract_rows(text):
    """
    테이블 행 패턴:
    연번  시도  시군  읍면  리동  지번  지목  소유자  지적  지정면적
    """
    rows = []
    # 페이지 헤더/푸터 제거
    text = re.sub(r'제\d+호\s*관\s*보.*?\(.*?\)', '', text, flags=re.DOTALL)
    text = re.sub(r'연번\s*소재지\s*지번.*?지정면적', '', text, flags=re.DOTALL)
    text = re.sub(r'시·도\s*시·군\s*읍·면\s*리·동', '', text)
    text = re.sub(r'합\s*계.*?필', '', text, flags=re.DOTALL)

    # 행 패턴: 숫자로 시작하는 줄 (연번)
    # 연번  시도  시군  읍면  리동  지번  지목  소유자  지적  지정면적
    pattern = re.compile(
        r'(\d+)\s+'                          # 연번
        r'(강원|경기|경북|경남|전북|전남|충북|충남|인천|서울|부산|대구|광주|대전|울산|제주|세종)\s+'  # 시도
        r'(\S+)\s+'                          # 시군
        r'(\S+)\s+'                          # 읍면
        r'(\S+)\s+'                          # 리동
        r'(\S+)\s+'                          # 지번
        r'(임야|전|답|대|잡종지|도로|하천|구거|임|묘|종교용지)\s+'   # 지목
        r'(국\(산림청\)|국유|사유|국|[^\d\s]+)\s+'  # 소유자
        r'([\d,]+)\s+'                       # 지적
        r'([\d,]+)'                          # 지정면적
    )

    for m in pattern.finditer(text):
        rows.append({
            **META,
            "연번": m.group(1),
            "시도": m.group(2),
            "시군": m.group(3),
            "읍면": m.group(4),
            "리동": m.group(5),
            "소재지": f"{m.group(2)} {m.group(3)} {m.group(4)} {m.group(5)}",
            "지번": m.group(6),
            "지목": m.group(7),
            "소유자": m.group(8),
            "지적": m.group(9),
            "지정면적": m.group(10),
        })

    return rows

def main():
    text = parse_pdf()
    rows = extract_rows(text)
    print(f"추출된 필지: {len(rows)}개")

    if not rows:
        print("데이터 없음")
        return

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        for row in rows:
            cols = list(row.keys())
            vals = [row[c] for c in cols]
            col_sql = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(["%s"] * len(cols))
            cur.execute(f'INSERT INTO fgrr_notices ({col_sql}) VALUES ({placeholders})', vals)
    conn.commit()
    conn.close()
    print(f"저장 완료: {len(rows)}개")

    # raw_text도 업데이트
    conn2 = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn2.cursor() as cur:
        cur.execute('UPDATE fgrr_notices SET "raw_text" = %s WHERE "파일명" = %s AND "raw_text" IS NULL', (text, FILENAME))
    conn2.commit()
    conn2.close()

if __name__ == "__main__":
    main()
