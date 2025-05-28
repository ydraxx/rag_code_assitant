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

    node = tu.cursor
    code = code.encode(("utf-8"))
    chunks = []
    # includes = [i for i in tu.get_includes()] # TODO : fix includes
    includes = []
    current_class = None

    def visit_and_extract_functions(node, extent_code):
        defined_functions = []
        used_functions = []

        def visit(node):
            if node.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]:
                # Vérifiez si la fonction est définie dans le code du chunk (extent)
                if node.extent.start.offset >= node.extent.start.offset and node.extent.end.offset <= node.extent.end.offset:
                    defined_functions.append(node.spelling)

            if node.kind == CursorKind.CALL_EXPR:
                referenced_function = node.referenced
                if referenced_function and referenced_function.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]:
                    if referenced_function.spelling not in defined_functions:
                        used_functions.append(referenced_function.spelling)

            for child in node.get_children():
                visit(child)

        visit(node)
        return defined_functions, used_functions

    def recurse(node, current_class=None):
        if node.kind == CursorKind.CLASS_DECL or node.kind == CursorKind.STRUCT_DECL:
            class_name = node.spelling
            fields = [c.spelling for c in node.get_children() if c.kind == CursorKind.FIELD_DECL]

            extent_code = code[node.extent.start.offset:node.extent.end.offset].decode("utf-8", errors="replace")
            defined, used = visit_and_extract_functions(node, extent_code)

            chunks.append(create_chunk_clang(
                code, file_path, chunk_type="class" if node.kind == CursorKind.CLASS_DECL else "struct",
                extent=node.extent,
                includes=includes,
                current_class=None,
                fields=fields,
                ast=node_to_string(node)
            ))

            for child in node.get_children():
                recurse(child, current_class=class_name)

        elif node.kind == CursorKind.FUNCTION_DECL or node.kind == CursorKind.CXX_METHOD:
            defined = [node.spelling]
            extent_code = code[node.extent.start.offset:node.extent.end.offset].decode("utf-8", errors="replace")
            defined, used = visit_and_extract_functions(node, extent_code)

            chunks.append(create_chunk_clang(
                code, file_path, chunk_type="function",
                extent=node.extent,
                includes=includes,
                current_class=current_class,
                defined=defined,
                used=used,
                ast=node_to_string(node)
            ))

        elif node.kind in {
            CursorKind.NAMESPACE,
            CursorKind.ENUM_DECL,
            CursorKind.TYPEDEF_DECL,
            CursorKind.USING_DECLARATION,
            CursorKind.FUNCTION_TEMPLATE
        }:
            extent_code = code[node.extent.start.offset:node.extent.end.offset].decode("utf-8", errors="replace")
            defined, used = visit_and_extract_functions(node, extent_code)

            chunks.append(create_chunk_clang(
                code, file_path, chunk_type=node.kind.name.lower(),
                extent=node.extent,
                includes=includes,
                current_class=current_class,
                ast=node_to_string(node)
            ))

        for child in node.get_children():
            recurse(child, current_class)

    recurse(node=node)
    print(f"Chunks generated for {file_path}, chunks: {len(chunks)}")
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
