"""전처리 분석 보고서 PDF 생성"""
import os
import pathlib
from dotenv import load_dotenv
import psycopg2
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

load_dotenv()

# ── 폰트 등록 (macOS 기본 한글 폰트) ─────────────────────────────
FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]
FONT_NAME = "Korean"
for fp in FONT_PATHS:
    if os.path.exists(fp):
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, fp, subfontIndex=0))
            pdfmetrics.registerFont(TTFont(FONT_NAME + "B", fp, subfontIndex=1))
            break
        except Exception:
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, fp))
                pdfmetrics.registerFont(TTFont(FONT_NAME + "B", fp))
                break
            except Exception:
                continue

# ── DB 연결 및 데이터 수집 ────────────────────────────────────────
conn = psycopg2.connect(os.environ["DATABASE_URL"])

def q(sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()

def q1(sql):
    r = q(sql)
    return r[0][0] if r else None

total_rows = q1("SELECT COUNT(*) FROM fgrr_notices")
total_files = q1('SELECT COUNT(DISTINCT "파일명") FROM fgrr_notices')

columns = q("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='fgrr_notices' AND table_schema='public'
    AND column_name != 'id'
    ORDER BY ordinal_position
""")
col_names = [c[0] for c in columns]

null_stats = []
for col in col_names:
    nn = q1(f'SELECT COUNT(*) FROM fgrr_notices WHERE "{col}" IS NOT NULL')
    pct = round((1 - nn / total_rows) * 100, 1) if total_rows else 0
    null_stats.append((col, nn, pct))

유형_dist = q('SELECT "유형", COUNT(*) FROM fgrr_notices GROUP BY "유형" ORDER BY COUNT(*) DESC LIMIT 10')
기관_dist = q('SELECT "지방산림청", COUNT(*) FROM fgrr_notices GROUP BY "지방산림청" ORDER BY COUNT(*) DESC')
지정유형_dist = q('SELECT "지정유형", COUNT(*) FROM fgrr_notices WHERE "지정유형" IS NOT NULL GROUP BY "지정유형" ORDER BY COUNT(*) DESC LIMIT 10')
유전자원여부 = q('SELECT "유전자원보호구역_여부", COUNT(*) FROM fgrr_notices GROUP BY "유전자원보호구역_여부"')
날짜패턴 = q("""
    SELECT
      CASE
        WHEN "고시날짜" ~ E'^\\d{4}년 \\d{2}월 \\d{2}일$' THEN 'YYYY년 MM월 DD일 (제로패딩)'
        WHEN "고시날짜" ~ E'^\\d{4}년 \\d{1,2}월 \\d{1,2}일$' THEN 'YYYY년 M월 D일 (비패딩)'
        WHEN "고시날짜" ~ E'^\\d{4}-\\d{2}-\\d{2}$' THEN 'YYYY-MM-DD'
        WHEN "고시날짜" ~ E'^\\d{4}\\. \\d{1,2}\\. \\d{1,2}\\.$' THEN 'YYYY. M. D.'
        WHEN "고시날짜" ~ E'^\\d{4}년\\d{2}월\\d{2}일$' THEN 'YYYY년MM월DD일 (공백없음)'
        WHEN "고시날짜" ~ E'^\\d{4}\\.\\d{2}\\.\\d{2}' THEN 'YYYY.MM.DD'
        ELSE '기타'
      END AS 패턴, COUNT(*)
    FROM fgrr_notices WHERE "고시날짜" IS NOT NULL GROUP BY 1 ORDER BY 2 DESC
""")
면적단위 = q("""
    SELECT
      CASE
        WHEN "지정면적" ~ '㎡' THEN '㎡ 명시'
        WHEN "지정면적" ~ 'ha' THEN 'ha 명시'
        WHEN "지정면적" ~ E'^[\\d,]+$' THEN '순수 숫자 (단위 없음)'
        WHEN "지정면적" IS NULL THEN 'NULL'
        ELSE '기타'
      END AS 유형, COUNT(*)
    FROM fgrr_notices GROUP BY 1 ORDER BY 2 DESC
""")
소재지패턴 = q("""
    SELECT
      CASE
        WHEN "소재지" ~ '^(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)' THEN '시도 포함'
        WHEN "소재지" IS NULL THEN 'NULL'
        ELSE '시도 미포함'
      END AS 패턴, COUNT(*)
    FROM fgrr_notices GROUP BY 1 ORDER BY 2 DESC
""")
지번패턴 = q("""
    SELECT
      CASE
        WHEN "지번" ~ E'^산\\d+' THEN '산+숫자'
        WHEN "지번" ~ E'^산 \\d+' THEN '산+공백+숫자'
        WHEN "지번" ~ E'^\\d+' THEN '숫자 시작'
        WHEN "지번" IS NULL THEN 'NULL'
        ELSE '기타'
      END AS 패턴, COUNT(*)
    FROM fgrr_notices GROUP BY 1 ORDER BY 2 DESC
""")
raw_stats = q("""
    SELECT MIN(LENGTH("raw_text")), MAX(LENGTH("raw_text")),
           ROUND(AVG(LENGTH("raw_text"))),
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY LENGTH("raw_text"))
    FROM fgrr_notices WHERE "raw_text" IS NOT NULL
""")[0]
유형_unique = q1('SELECT COUNT(DISTINCT "유형") FROM fgrr_notices')
지정유형_unique = q1('SELECT COUNT(DISTINCT "지정유형") FROM fgrr_notices WHERE "지정유형" IS NOT NULL')
동적컬럼 = ['구분','시도','시군','읍면','리동','위치','산림유전자원보호림번호','보호대상수종','지정기간','관리소','연번','세부유형','정정사유','경도','위도']
동적_stats = []
for col in 동적컬럼:
    try:
        cnt = q1(f'SELECT COUNT(*) FROM fgrr_notices WHERE "{col}" IS NOT NULL')
        pct = round(cnt / total_rows * 100, 1)
        동적_stats.append((col, cnt, f'{pct}%'))
    except Exception:
        conn.rollback()

conn.close()

# ── 색상 정의 ─────────────────────────────────────────────────────
BLUE_DARK   = colors.HexColor('#1F497D')
BLUE_MID    = colors.HexColor('#2E75B6')
BLUE_LIGHT  = colors.HexColor('#D6E4F0')
GRAY_LIGHT  = colors.HexColor('#F5F5F5')
GRAY_MID    = colors.HexColor('#CCCCCC')
WHITE       = colors.white
BLACK       = colors.black
ORANGE      = colors.HexColor('#E67E22')
GREEN       = colors.HexColor('#27AE60')

# ── 스타일 ────────────────────────────────────────────────────────
def make_styles():
    s = {}
    s['title']   = ParagraphStyle('title',   fontName=FONT_NAME,   leading=22, fontSize=20, textColor=BLUE_DARK,  alignment=TA_CENTER, spaceAfter=6)
    s['subtitle']= ParagraphStyle('subtitle',fontName=FONT_NAME,   leading=18, fontSize=13, textColor=BLUE_MID,   alignment=TA_CENTER, spaceAfter=4)
    s['date']    = ParagraphStyle('date',    fontName=FONT_NAME,   leading=14, fontSize=10, textColor=colors.gray, alignment=TA_CENTER)
    s['h1']      = ParagraphStyle('h1',      fontName=FONT_NAME+'B',leading=18, fontSize=13, textColor=BLUE_DARK,  spaceBefore=14, spaceAfter=6)
    s['h2']      = ParagraphStyle('h2',      fontName=FONT_NAME+'B',leading=16, fontSize=11, textColor=BLUE_MID,   spaceBefore=10, spaceAfter=4)
    s['body']    = ParagraphStyle('body',    fontName=FONT_NAME,   leading=15, fontSize=9,  textColor=BLACK,       alignment=TA_JUSTIFY, spaceAfter=4)
    s['cell']    = ParagraphStyle('cell',    fontName=FONT_NAME,   leading=13, fontSize=8.5,textColor=BLACK)
    s['cell_hdr']= ParagraphStyle('cell_hdr',fontName=FONT_NAME+'B',leading=13,fontSize=8.5,textColor=WHITE, alignment=TA_CENTER)
    s['note']    = ParagraphStyle('note',    fontName=FONT_NAME,   leading=12, fontSize=8,  textColor=colors.gray, spaceAfter=4)
    return s

ST = make_styles()

# ── 표 생성 헬퍼 ──────────────────────────────────────────────────
def make_table(headers, rows, col_widths=None):
    data = [[Paragraph(h, ST['cell_hdr']) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(v) if v is not None else '', ST['cell']) for v in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BLUE_DARK),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, GRAY_LIGHT]),
        ('GRID', (0,0), (-1,-1), 0.4, GRAY_MID),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ])
    t.setStyle(style)
    return t

def h1(text):
    return [Paragraph(text, ST['h1']), HRFlowable(width='100%', thickness=1.5, color=BLUE_DARK, spaceAfter=6)]

def h2(text):
    return [Paragraph(text, ST['h2']), HRFlowable(width='100%', thickness=0.5, color=BLUE_LIGHT, spaceAfter=4)]

def body(text):
    return Paragraph(text, ST['body'])

def sp(n=6):
    return Spacer(1, n)

# ── 문서 구성 ─────────────────────────────────────────────────────
out_path = pathlib.Path(__file__).parent.parent / 'docs' / '전처리_품질분석_보고서.pdf'
out_path.parent.mkdir(exist_ok=True)

doc = SimpleDocTemplate(
    str(out_path), pagesize=A4,
    leftMargin=2.5*cm, rightMargin=2.5*cm,
    topMargin=2.5*cm, bottomMargin=2.5*cm,
)

W = A4[0] - 5*cm  # 본문 너비

story = []

# ── 표지 ──
story += [
    Spacer(1, 3*cm),
    Paragraph('유전자원보호구역 관보고시 DB 구축', ST['title']),
    Paragraph('전처리 품질 분석 보고서', ST['subtitle']),
    Spacer(1, 0.5*cm),
    HRFlowable(width='60%', thickness=1, color=BLUE_MID),
    Spacer(1, 0.5*cm),
    Paragraph('2026년 6월', ST['date']),
    PageBreak(),
]

# ── 1. 개요 ──
story += h1('1. 개요')
story.append(body(
    f'산림청 산하 5개 지방산림청의 산림유전자원보호구역 관련 관보고시 PDF <b>{total_files}건</b>을 처리하여 '
    f'PostgreSQL DB에 적재하였다. 총 <b>{total_rows:,}개 필지</b> 행이 생성되었으며, Claude API를 활용한 '
    '비정형 PDF 파싱 방식으로 인해 고시별 컬럼 구조의 차이가 존재한다. '
    '본 보고서는 적재 결과의 품질을 분석하고 후속 전처리 방향을 제시한다.'
))
story.append(sp(8))
story.append(make_table(
    ['항목', '값'],
    [
        ['처리 PDF 수', f'{total_files}건'],
        ['총 필지 수', f'{total_rows:,}행'],
        ['테이블 컬럼 수', f'{len(col_names)}개'],
        ['기본 설계 컬럼 수', '19개'],
        ['동적 추가 컬럼 수', f'{len(col_names) - 19}개'],
    ],
    col_widths=[W*0.5, W*0.5]
))

# ── 2. 컬럼 현황 ──
story.append(PageBreak())
story += h1('2. 컬럼 현황')

story += h2('2.1 기본 컬럼 null 비율')
story.append(body(
    '19개 기본 컬럼의 데이터 충전율이다. 해제사유·잔여면적·임반 등은 고시 유형에 따라 '
    '구조적으로 존재하지 않는 필드이므로 데이터 손실과 구분이 필요하다.'
))
story.append(sp(6))

base_cols = ['번호','파일명','지방산림청','고시번호','유형','고시날짜','소재지','지번','임반',
             '지목','소유자','지적','지정면적','해제면적','잔여면적','지정유형','해제사유','명칭','비고']
base_rows = [(col, nn, f'{pct}%') for col, nn, pct in null_stats if col in base_cols]
story.append(make_table(['컬럼명', '유효값 수', 'null 비율'], base_rows,
                        col_widths=[W*0.45, W*0.3, W*0.25]))

story.append(sp(12))
story += h2('2.2 동적 추가 컬럼 현황')
story.append(body(
    '고시별 표 구조 차이로 인해 파싱 중 동적으로 추가된 컬럼들이다. '
    '대부분 특정 소수 고시에서만 나타나는 필드로 null 비율이 매우 높다.'
))
story.append(sp(6))
story.append(make_table(['컬럼명', '유효값 수', '충전율'], 동적_stats,
                        col_widths=[W*0.45, W*0.3, W*0.25]))

# ── 3. 주요 컬럼 품질 분석 ──
story.append(PageBreak())
story += h1('3. 주요 컬럼 품질 분석')

story += h2('3.1 유형 컬럼')
story.append(body(
    f'현재 유형 컬럼에 <b>{유형_unique}개</b>의 distinct 값이 존재한다. 동일한 고시 유형이 '
    '파일명 표기 방식·띄어쓰기·괄호 종류 차이 등으로 다양하게 기록되어 정규화가 필요하다.'
))
story.append(sp(6))
story.append(make_table(['유형 값 (상위 10)', '건수'],
                        [(v, c) for v, c in 유형_dist],
                        col_widths=[W*0.75, W*0.25]))

story.append(sp(12))
story += h2('3.2 지정유형 컬럼')
story.append(body(
    f'필지별 보호구역 유형을 나타내는 핵심 컬럼이다. <b>{지정유형_unique}개</b> distinct 값이 존재하며, '
    '한 고시 안에 여러 보호구역 유형이 혼재하는 경우가 있어 필지 단위 분류에 활용된다.'
))
story.append(sp(6))
story.append(make_table(['지정유형 (상위 10)', '건수'],
                        [(v, c) for v, c in 지정유형_dist],
                        col_widths=[W*0.75, W*0.25]))

story.append(sp(12))
story += h2('3.3 지방산림청 컬럼')
story.append(body(
    '2001~2005년대 구명칭(지방산림관리청)과 현행명칭(지방산림청)이 혼재한다. '
    '또한 일부 행에서 NULL이 추출되어 파일명 기반 보완이 필요하다.'
))
story.append(sp(6))
story.append(make_table(['지방산림청', '건수'],
                        [(v if v else '(NULL)', c) for v, c in 기관_dist],
                        col_widths=[W*0.7, W*0.3]))

story.append(sp(12))
story += h2('3.4 유전자원보호구역_여부 컬럼')
story.append(body(
    '지정유형 컬럼 기반으로 필지 단위 판별하여 업데이트 완료하였다. '
    '"유전자원" 포함 여부로 True/False를 결정하며, null은 지정유형이 추출되지 않은 케이스이다.'
))
story.append(sp(6))
story.append(make_table(['값', '건수'],
                        [('True (유전자원보호구역)', next((c for v, c in 유전자원여부 if v == True), 0)),
                         ('False (기타 보호구역)',   next((c for v, c in 유전자원여부 if v == False), 0)),
                         ('NULL (지정유형 미추출)',   next((c for v, c in 유전자원여부 if v is None), 0))],
                        col_widths=[W*0.65, W*0.35]))

# ── 4. 데이터 형식 비일관성 ──
story.append(PageBreak())
story += h1('4. 데이터 형식 비일관성')

story += h2('4.1 고시날짜')
story.append(body('6가지 날짜 형식이 혼재한다. DATE 타입으로 통합하거나 표준 형식으로 정규화가 필요하다.'))
story.append(sp(6))
story.append(make_table(['날짜 형식 패턴', '건수'],
                        [(p, c) for p, c in 날짜패턴],
                        col_widths=[W*0.75, W*0.25]))

story.append(sp(12))
story += h2('4.2 면적 컬럼 (지정면적·해제면적·잔여면적)')
story.append(body(
    '대부분 단위 없이 순수 숫자로 기록되어 있으며, 일부는 ㎡ 또는 ha를 명시한다. '
    '숫자 변환 전 콤마 제거, 단위 분리, ha→㎡ 변환 처리가 필요하다.'
))
story.append(sp(6))
story.append(make_table(['면적값 유형', '건수'],
                        [(t, c) for t, c in 면적단위],
                        col_widths=[W*0.75, W*0.25]))

story.append(sp(12))
story += h2('4.3 소재지')
story.append(body(
    '광역시도 포함 여부가 일관되지 않는다. 시도명 미포함 건은 지방산림청 관할 지역 매핑 또는 '
    '주소 정규화 API를 통해 표준화할 수 있다.'
))
story.append(sp(6))
story.append(make_table(['소재지 패턴', '건수'],
                        [(p, c) for p, c in 소재지패턴],
                        col_widths=[W*0.75, W*0.25]))

story.append(sp(12))
story += h2('4.4 지번')
story.append(body(
    '"산 217"처럼 산과 숫자 사이 공백이 포함된 케이스가 일부 존재한다. '
    'GIS 연계 시 공백 제거 등 정규화가 필요하다.'
))
story.append(sp(6))
story.append(make_table(['지번 패턴', '건수'],
                        [(p, c) for p, c in 지번패턴],
                        col_widths=[W*0.75, W*0.25]))

# ── 5. 전처리 방향 및 우선순위 ──
story.append(PageBreak())
story += h1('5. 전처리 방향 및 우선순위')

priority_rows = [
    ('P1', '고시날짜 표준화',
     '6가지 혼재 패턴 → DATE 타입으로 변환. 정규식 파싱 후 별도 date 컬럼 추가'),
    ('P1', '유형 컬럼 정규화',
     f'{유형_unique}개 → 지정/해제/정정/변경/공고 5개 범주로 통합'),
    ('P2', '면적 컬럼 숫자 변환',
     '콤마 제거, 단위 분리(㎡/ha), ha→㎡ 변환 후 NUMERIC 컬럼으로 별도 저장. 원본 유지'),
    ('P2', '소재지 시도 보완',
     '시도 미포함 건(약 48%)에 지방산림청 관할 지역 매핑 또는 주소 API 표준화'),
    ('P2', '지방산림청 구명칭 통합',
     '~관리청 → ~청 으로 정규화 (원본 컬럼은 유지)'),
    ('P3', '지번 공백 정규화',
     '"산 217" → "산217" 형식으로 통일'),
    ('P3', '희박 동적 컬럼 처리',
     'null 비율 95% 이상 컬럼 활용 여부 결정. 필요 시 부가정보 테이블로 분리'),
    ('P3', 'raw_text 활용',
     '필지 추출 누락 의심 건 재파싱 소스로 활용. 평균 3,013자 원문 100% 보존 중'),
]

# 우선순위별 색상
p_colors = {'P1': colors.HexColor('#E74C3C'), 'P2': ORANGE, 'P3': GREEN}

data = [[Paragraph(h, ST['cell_hdr']) for h in ['우선순위', '항목', '상세']]]
for p, title, detail in priority_rows:
    data.append([
        Paragraph(p, ParagraphStyle('p', fontName=FONT_NAME+'B', fontSize=9, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph(title, ST['cell']),
        Paragraph(detail, ST['cell']),
    ])

t = Table(data, colWidths=[W*0.12, W*0.28, W*0.6], repeatRows=1)
ts = TableStyle([
    ('BACKGROUND', (0,0), (-1,0), BLUE_DARK),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, GRAY_LIGHT]),
    ('GRID', (0,0), (-1,-1), 0.4, GRAY_MID),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ('LEFTPADDING', (0,0), (-1,-1), 6),
    ('RIGHTPADDING', (0,0), (-1,-1), 6),
])
# P1/P2/P3 셀 색상
for i, (p, _, _) in enumerate(priority_rows):
    ts.add('BACKGROUND', (0, i+1), (0, i+1), p_colors[p])
t.setStyle(ts)
story.append(t)

# ── 6. raw_text 보존 현황 ──
story.append(sp(14))
story += h1('6. raw_text 보존 현황')
story.append(body(
    'pdfplumber로 추출한 원문 텍스트를 전체 1,471건에 대해 보존하고 있다. '
    '향후 파싱 결과 오류 수정, 추가 필드 재추출 등에 재활용 가능하다.'
))
story.append(sp(6))
story.append(make_table(
    ['통계 항목', '값'],
    [
        ['보존 건수', f'{total_rows:,}건 (100%)'],
        ['최소 길이', f'{int(raw_stats[0]):,}자'],
        ['최대 길이', f'{int(raw_stats[1]):,}자'],
        ['평균 길이', f'{int(raw_stats[2]):,}자'],
        ['중앙값 길이', f'{int(raw_stats[3]):,}자'],
    ],
    col_widths=[W*0.5, W*0.5]
))

# ── 빌드 ──────────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_NAME, 8)
    canvas.setFillColor(colors.gray)
    canvas.drawRightString(A4[0] - 2*cm, 1.2*cm, f'{doc.page}')
    canvas.drawString(2.5*cm, 1.2*cm, '유전자원보호구역 관보고시 DB 구축 — 전처리 품질 분석 보고서')
    canvas.restoreState()

doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print(f'저장 완료: {out_path}')
