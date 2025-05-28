import re
from langchain_core.documents import Document

def extract_header_chunks(code: str, file_path: str) -> list[Document]:
    """
    Extrait les classes, structs, fonctions et le texte global d'un header .h/.hpp.
    Chaque élément est transformé en chunk indexable.
    """
    chunks = []

    # Match les classes
    class_pattern = r'(class\s+\w+\s*(?:[:\w\s,]*?)?\s*{[^}]*};)'
    class_matches = re.findall(class_pattern, code, re.DOTALL)
    for i, match in enumerate(class_matches):
        chunks.append(Document(
            page_content=match.strip(),
            metadata={"source": file_path, "type": "class", "chunk_id": f"class_{i}"}
        ))

    # Match les structs
    struct_pattern = r'(struct\s+\w+\s*{[^}]*};)'
    struct_matches = re.findall(struct_pattern, code, re.DOTALL)
    for i, match in enumerate(struct_matches):
        chunks.append(Document(
            page_content=match.strip(),
            metadata={"source": file_path, "type": "struct", "chunk_id": f"struct_{i}"}
        ))

    # Match les enums
    enum_pattern = r'(enum\s+(class\s+)?\w+\s*{[^}]*};?)'
    enum_matches = re.findall(enum_pattern, code, re.DOTALL)
    for i, match in enumerate(enum_matches):
        chunks.append(Document(
            page_content=match[0].strip(),
            metadata={"source": file_path, "type": "enum", "chunk_id": f"enum_{i}"}
        ))

    # Match les fonctions globales (hors classe)
    func_pattern = r'(?:^[\w:\*\&<>\s]+?\s+(\w+)\s*\([^\)]*\)\s*;)'  # déclaration de fonction
    func_matches = re.finditer(func_pattern, code, re.MULTILINE)
    for i, match in enumerate(func_matches):
        full_match = match.group(0)
        chunks.append(Document(
            page_content=full_match.strip(),
            metadata={"source": file_path, "type": "function_decl", "chunk_id": f"func_{i}"}
        ))

    # En dernier recours : chunk global du header
    chunks.append(Document(
        page_content=code.strip(),
        metadata={"source": file_path, "type": "full_header", "chunk_id": "all"}
    ))

    return chunks
