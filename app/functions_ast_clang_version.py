import hashlib
from clang.cindex import Index, CursorKind, Config
from langchain_core.documents import Document
import os
import re

def create_chunk_clang(code: str, file_path: str, chunk_type: str, extent, includes=None, current_class=None, defined=None, used=None, fields=None, ast=None):
    chunk_code = code[extent.start.offset:extent.end.offset].strip()
    return Document(
        page_content=chunk_code,
        metadata={
            "file_path": file_path,
            "type": chunk_type,
            "includes": includes or [],
            "parent_class": current_class,
            "defined_functions": defined or [],
            "used_functions": used or [],
            "defined_fields": fields or [],
            "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
            "start_point": (extent.start.line, extent.start.column),
            "end_point": (extent.end.line, extent.end.column),
            "ast": ast,
        }
    )


def extract_used_functions(code: str):
    pattern = r'\b([a-zA-Z_]\w*)\s*\('
    candidates = re.findall(pattern, code)
    keywords = {'if', 'for', 'while', 'switch', 'return', 'sizeof', 'catch', 'throw', 'new', 'delete'}
    return list(set(c for c in candidates if c not in keywords))


def extract_chunks_with_clang(file_path: str):
    index = Index.create()
    tu = index.parse(file_path, args=['-std=c++17'])

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    chunks = []
    includes = [i.spelling for i in tu.get_includes()]  # simple include extraction
    current_class = None

    def recurse(node, current_class=None):
        if node.kind == CursorKind.CLASS_DECL or node.kind == CursorKind.STRUCT_DECL:
            class_name = node.spelling
            fields = [c.spelling for c in node.get_children() if c.kind == CursorKind.FIELD_DECL]

            chunks.append(create_chunk_clang(
                code, file_path, chunk_type="class" if node.kind == CursorKind.CLASS_DECL else "struct",
                extent=node.extent,
                current_class=None,
                fields=fields,
                ast=str(node.kind)
            ))

            for child in node.get_children():
                recurse(child, current_class=class_name)

        elif node.kind == CursorKind.FUNCTION_DECL or node.kind == CursorKind.CXX_METHOD:
            defined = [node.spelling]
            extent_code = code[node.extent.start.offset:node.extent.end.offset]
            used = extract_used_functions(extent_code)

            chunks.append(create_chunk_clang(
                code, file_path, chunk_type="function",
                extent=node.extent,
                current_class=current_class,
                defined=defined,
                used=used,
                ast=str(node.kind)
            ))

        elif node.kind in {
            CursorKind.NAMESPACE,
            CursorKind.ENUM_DECL,
            CursorKind.TYPEDEF_DECL,
            CursorKind.USING_DECLARATION,
            CursorKind.TEMPLATE_DECL
        }:
            chunks.append(create_chunk_clang(
                code, file_path, chunk_type=node.kind.name.lower(),
                extent=node.extent,
                current_class=current_class,
                ast=str(node.kind)
            ))

        for child in node.get_children():
            recurse(child, current_class)

    recurse(tu.cursor)
    return chunks
