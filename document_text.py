"""Text extraction for the document reader. Files are processed in memory."""

from io import BytesIO
import re
from pathlib import PurePath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 120_000
MAX_PDF_PAGES = 80
MAX_XML_BYTES = 8 * 1024 * 1024

FILE_PACKAGES = {
    ".pdf": ("pypdf", "pypdf-7.1.1-py3-none-any.whl"),
    ".rtf": ("striprtf", "striprtf-0.0.29-py3-none-any.whl"),
}
SUPPORTED = {".txt", ".md", ".csv", ".docx", ".odt", *FILE_PACKAGES}

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WORD_STRICT = "{http://purl.oclc.org/ooxml/wordprocessingml/main}"
ODF = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


def file_suffix(filename):
    return PurePath(filename).suffix.lower()


def decode_text(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1251")
    if any(not (char.isprintable() or char.isspace()) for char in text):
        raise ValueError("В файле не удалось распознать обычный текст.")
    return text


def read_xml(data, part):
    with ZipFile(BytesIO(data)) as archive:
        info = archive.getinfo(part)
        if info.file_size > MAX_XML_BYTES:
            raise ValueError("Текстовая часть документа слишком велика. Разделите документ на части.")
        xml = archive.read(info)
    if b"<!DOCTYPE" in xml.replace(b"\0", b"").upper():
        raise ValueError("Не удалось безопасно прочитать структуру документа.")
    return ElementTree.fromstring(xml)


def read_docx(data):
    root = read_xml(data, "word/document.xml")
    paragraphs = []
    for node in root.iter():
        if node.tag not in (WORD + "p", WORD_STRICT + "p"):
            continue
        namespace = node.tag[:-1]
        text = []
        for item in node.iter():
            if item.tag == namespace + "t":
                text.append(item.text or "")
            elif item.tag in (namespace + "tab", namespace + "br", namespace + "cr"):
                text.append(" ")
        paragraphs.append("".join(text))
    return "\n".join(paragraphs)


def read_odt(data):
    root = read_xml(data, "content.xml")

    def content(node):
        if node.tag in (ODF + "s", ODF + "tab", ODF + "line-break"):
            return " "
        return (node.text or "") + "".join(content(child) + (child.tail or "") for child in node)

    return "\n".join(content(node) for node in root.iter() if node.tag in (ODF + "p", ODF + "h"))


def read_pdf(data):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("PDF защищён паролем. Сохраните копию без пароля.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError("Разделите PDF на файлы до 80 страниц.")
        text = "\n".join(" ".join(page.extract_text().split()) for page in reader.pages)
    except PdfReadError as error:
        raise ValueError("Не удалось открыть PDF. Проверьте, что файл не повреждён.") from error
    if not text.strip():
        raise ValueError("В PDF нет извлекаемого текста. Для скана сначала понадобится распознавание текста.")
    return text


def read_document(filename, data):
    suffix = file_suffix(filename)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Выберите файл до 8 МБ.")
    try:
        if suffix == ".docx":
            text = read_docx(data)
        elif suffix == ".odt":
            text = read_odt(data)
        elif suffix == ".pdf":
            text = read_pdf(data)
        elif suffix == ".rtf":
            from striprtf.striprtf import rtf_to_text

            raw = decode_text(data)
            if not raw.lstrip().startswith("{\\rtf"):
                raise ValueError("Выберите документ в формате RTF.")
            text = rtf_to_text(raw, errors="strict")
        elif suffix in (".txt", ".md", ".csv"):
            text = decode_text(data)
        else:
            raise ValueError("Выберите DOCX, PDF, ODT, RTF, TXT, Markdown или CSV.")
    except (BadZipFile, KeyError, ElementTree.ParseError, RuntimeError) as error:
        raise ValueError("Документ не удалось прочитать. Попробуйте сохранить его заново.") from error
    except UnicodeError as error:
        raise ValueError("Не удалось прочитать кодировку текста. Попробуйте сохранить файл в UTF-8.") from error

    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        raise ValueError("В документе нет текста.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("В документе слишком много текста. Разделите его на части.")
    return text
