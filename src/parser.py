import re
import pdfplumber


def parse_filename(filename: str) -> dict:
    """파일명에서 메타데이터 추출"""
    stem = filename.replace(".pdf", "")

    # 번호
    번호 = stem.split("_")[0] if "_" in stem else ""

    # 기관명
    기관_match = re.search(r"(\w+지방산림(?:관리)?청)", stem)
    지방산림청 = 기관_match.group(1) if 기관_match else ""

    # 고시번호
    고시번호_match = re.search(r"고시제(\d{4}-\d+)호", stem)
    고시번호 = 고시번호_match.group(1) if 고시번호_match else ""

    # 유형 (괄호 안 내용)
    유형_match = re.search(r"\((.+)\)", stem)
    유형_raw = 유형_match.group(1) if 유형_match else ""
    유형 = _classify_type(유형_raw)

    # 파일명에 유전자원보호구역 명시 여부
    유전자원_명시 = "유전자원" in stem

    return {
        "번호": 번호,
        "파일명": filename,
        "지방산림청": 지방산림청,
        "고시번호": 고시번호,
        "유형": 유형,
        "유전자원보호구역_여부": 유전자원_명시,
    }


def _classify_type(text: str) -> str:
    if "정정" in text:
        return "정정"
    if "공고" in text or "예정" in text:
        return "공고"
    if "변경" in text and "해제" not in text:
        return "변경"
    if "해제" in text:
        return "해제"
    if "지정" in text:
        return "지정"
    return text


def extract_text(pdf_path: str) -> str:
    """PDF 텍스트 추출 - pdfplumber 시도 후 CID 인코딩 감지 시 pymupdf로 fallback"""
    text = _extract_pdfplumber(pdf_path)
    if _is_cid_encoded(text):
        text = _extract_pymupdf(pdf_path)
    return text


def _extract_pdfplumber(pdf_path: str) -> str:
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text(x_tolerance=2, y_tolerance=2)
            if t:
                texts.append(t)
    return "\n".join(texts)


def _extract_pymupdf(pdf_path: str) -> str:
    import fitz
    doc = fitz.open(pdf_path)
    texts = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(texts)


def _is_cid_encoded(text: str) -> bool:
    """CID 인코딩 깨짐 여부 감지"""
    return "(cid:" in text and text.count("(cid:") > 5
