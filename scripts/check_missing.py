import fitz, openpyxl
from pathlib import Path

notices_dir = Path('data/notices')
wb = openpyxl.load_workbook('docs/FGRR_DB_0605.xlsx')
ws = wb.active
headers = [c.value for c in ws[1]]

excel_by_num = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    d = dict(zip(headers, row))
    if d.get('번호'):
        try:
            k = str(int(d['번호'])).zfill(4)
            excel_by_num.setdefault(k, []).append(d)
        except: pass

NUMS = [
    '0020','0172','0208','0214','0216','0268','0283','0311','0314','0322',
    '0324','0340','0341','0345','0355','0402','0433','0592','0608','0664',
    '0665','0690','0698','0703','0706','0710','0719','0739','0740','0741',
    '0742','0749','0760','0770','0778','0783','0787','0788','0789','0790',
    '0791','0792','0793','0798','0802','0803','0808','0814','0828','0836',
    '0838','0839','0840','0842','0844','0845','0847',
]

for num in NUMS:
    pdfs = list(notices_dir.glob(f'{num}_*.pdf'))
    if not pdfs: continue
    pdf_path = pdfs[0]

    print(f'\n{"="*60}')
    print(f'[{num}] {pdf_path.name}')
    print(f'Excel 기대값:')
    for r in excel_by_num.get(num, []):
        print(f'  소재지={r.get("소재지")} 지번={r.get("지번")} 지정={r.get("지정면적(m2)")} 해제={r.get("해제면적")} 유형={r.get("지정유형")} 고시날짜={r.get("고시날짜")}')

    doc = fitz.open(str(pdf_path))
    text = '\n'.join(p.get_text() for p in doc)
    print(f'PDF 텍스트 (첫 3000자):')
    print(text[:3000])
