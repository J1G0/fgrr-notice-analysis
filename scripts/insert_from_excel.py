"""Excel 데이터를 직접 DB에 삽입 — 지정된 번호 목록"""
import os, psycopg2, fitz, openpyxl
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

notices_dir = Path("data/notices")
pdf_map = {p.stem[:4]: p for p in notices_dir.glob("*.pdf")}

wb = openpyxl.load_workbook("docs/FGRR_DB_0605.xlsx")
ws = wb.active
headers = [c.value for c in ws[1]]

NUMS = [
    "0020","0172","0208","0214","0216","0268","0283","0311","0314","0322",
    "0324","0340","0341","0345","0355","0402","0433","0592","0608","0664",
    "0665","0690","0698","0703","0706","0710","0719","0739","0740","0741",
    "0742","0749","0760","0770","0778","0783","0787","0788","0789","0790",
    "0791","0792","0793","0798","0802","0803","0808","0814","0828","0836",
    "0838","0839","0840","0842","0844","0845","0847",
]

# Excel 로드
excel_by_num = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    d = dict(zip(headers, row))
    try:
        num = str(int(d.get("번호") or "")).zfill(4)
    except:
        continue
    if num in NUMS:
        excel_by_num.setdefault(num, []).append(d)

# PDF 텍스트 캐시
pdf_text_cache = {}
def get_pdf_text(num):
    if num in pdf_text_cache:
        return pdf_text_cache[num]
    pdf = pdf_map.get(num)
    if not pdf:
        pdf_text_cache[num] = None
        return None
    try:
        doc = fitz.open(str(pdf))
        text = "\n".join(p.get_text() for p in doc)
        # 깨진 텍스트면 None 처리
        if len([c for c in text if ord(c) > 0xAC00 and ord(c) < 0xD7A3]) < 10 and len(text) > 100:
            pdf_text_cache[num] = None
        else:
            pdf_text_cache[num] = text
    except:
        pdf_text_cache[num] = None
    return pdf_text_cache[num]

def fmt_date(v):
    if v is None:
        return None
    s = str(int(v))
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s

def fmt_num(v):
    if v is None:
        return None
    return str(v)

conn = psycopg2.connect(os.environ["DATABASE_URL"])

def insert_row(row):
    cols = list(row.keys())
    col_sql = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    with conn.cursor() as cur:
        cur.execute(
            f'INSERT INTO fgrr_notices ({col_sql}) VALUES ({placeholders})',
            [row[c] for c in cols]
        )

total = 0
for num in NUMS:
    rows = excel_by_num.get(num, [])
    if not rows:
        print(f"[{num}] Excel 데이터 없음")
        continue

    pdf = pdf_map.get(num)
    pdf_filename = pdf.name if pdf else rows[0].get("파일명", "")
    raw_text = get_pdf_text(num)

    count = 0
    for d in rows:
        # 파일명: PDF 실제 파일명 우선
        excel_fn = str(d.get("파일명") or "")
        filename = pdf_filename if pdf else excel_fn

        row = {
            "번호": num,
            "파일명": filename,
            "지방산림청": d.get("지방산림청"),
            "고시번호": str(d.get("고시번호") or "").replace("제", "").replace("호", "").strip(),
            "유형": d.get("유형"),
            "고시날짜": fmt_date(d.get("고시날짜")),
            "소재지": d.get("소재지"),
            "지번": str(d.get("지번") or "") if d.get("지번") is not None else None,
            "임반": str(d.get("임반") or "") if d.get("임반") is not None else None,
            "지목": d.get("지목"),
            "소유자": d.get("소유자"),
            "지적": fmt_num(d.get("지적")),
            "지정면적": fmt_num(d.get("지정면적(m2)")),
            "해제면적": fmt_num(d.get("해제면적")),
            "잔여면적": fmt_num(d.get("잔여면적")),
            "지정유형": d.get("지정유형"),
            "해제사유": d.get("해제사유"),
            "명칭": d.get("명칭"),
            "비고": d.get("비고"),
            "유전자원보호구역_여부": True,
        }
        if raw_text:
            row["raw_text"] = raw_text

        # None 값 제거
        row = {k: v for k, v in row.items() if v is not None and v != ""}

        insert_row(row)
        count += 1

    conn.commit()
    print(f"[{num}] {count}행 삽입 (PDF: {'있음' if pdf else '없음'})")
    total += count

with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM fgrr_notices")
    print(f"\n총계: {cur.fetchone()[0]} (삽입: {total})")
conn.close()
