from clang.cindex import Index, CursorKind, Config
import hashlib
from langchain_core.documents import Document
import os
import re


# TODO: some chunk are identical before indexation

def create_chunk_clang(code: str, file_path: str, chunk_type: str, extent, includes=None, current_class=None, \
                        defined=None, used=None, fields=None, ast=None):

    chunk_code = code[extent.start.offset:extent.end.offset].decode("utf-8", errors="replace").strip()
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
            "hash": hashlib.sha256(chunk_code.encode('utf-8')).hexdigest(),
            "start_point": (extent.start.line, extent.start.column),
            "end_point": (extent.end.line, extent.end.column),
            "ast": ast,
        }
    )


def node_to_string(node, indent_level=0):
    # Utilisez l'indentation pour rendre la structure hiérarchique plus lisible
    indent = "  " * indent_level
    # Commencez avec le type du noeud et le nom
    node_str = f"{indent}{node.kind.name}: {node.spelling}\n"
    # Récupérez les enfants du noeud
    for child in node.get_children():
        node_str += node_to_string(child, indent_level + 1)
    return node_str


def extract_chunks(tu, code: str, file_path: str):
    code_bytes = code.encode("utf-8")
    chunks = []
    includes = []  # TODO: gérer les includes si besoin
    root = tu.cursor

    def get_extent_code(extent):
        return code_bytes[extent.start.offset:extent.end.offset].decode("utf-8", errors="replace")

    def extract_defined_and_used_functions(node, extent_code):
        defined = set()
        used = set()

        def visit(n):
            if n.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]:
                defined.add(n.spelling)
            elif n.kind == CursorKind.CALL_EXPR:
                if n.referenced and n.referenced.spelling:
                    used.add(n.referenced.spelling)
            for child in n.get_children():
                visit(child)

        visit(node)
        return list(defined), list(used - defined)

    def recurse(node, current_class=None):
        kind = node.kind
        spelling = node.spelling

        if kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL] and node.is_definition():
            extent_code = get_extent_code(node.extent)
            fields = [c.spelling for c in node.get_children() if c.kind == CursorKind.FIELD_DECL]
            ast_str = node_to_string(node)

            chunks.append(create_chunk_clang(
                code=code_bytes,
                file_path=file_path,
                chunk_type="class" if kind == CursorKind.CLASS_DECL else "struct",
                extent=node.extent,
                includes=includes,
                current_class=None,
                fields=fields,
                ast=ast_str
            ))

        elif kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD] and node.is_definition():
            extent_code = get_extent_code(node.extent)
            defined, used = extract_defined_and_used_functions(node, extent_code)
            ast_str = node_to_string(node)

            chunks.append(create_chunk_clang(
                code=code_bytes,
                file_path=file_path,
                chunk_type="function",
                extent=node.extent,
                includes=includes,
                current_class=current_class,
                defined=defined,
                used=used,
                ast=ast_str
            ))

        elif kind in {
            CursorKind.NAMESPACE,
            CursorKind.ENUM_DECL,
            CursorKind.TYPEDEF_DECL,
            CursorKind.USING_DECLARATION,
            CursorKind.FUNCTION_TEMPLATE
        }:
            # Ces éléments ne sont pas chunkés seuls sauf si hors d’une classe
            pass

        for child in node.get_children():
            recurse(child, current_class if kind != CursorKind.CLASS_DECL else spelling)

    recurse(root)
    print(f"Chunks generated for {file_path}: {len(chunks)}")
    return chunks


def extract_header_chunks(code: str, file_path: str):

    import re
from langchain_core.documents import Document

def extract_header_chunks(code: str, file_path: str) -> list[Document]:
    
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
    func_pattern = r'(?:^[\w:\*\&<>\s]+?\s+(\w+)\s*\([^\)]*\)\s*;)' 
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

    print(f"Chunks generated for {file_path}, chunks: {len(chunks)}")
    return chunks
