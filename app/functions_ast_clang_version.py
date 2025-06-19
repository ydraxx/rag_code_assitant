from clang.cindex import Index, CursorKind, Config
import hashlib
from langchain_core.documents import Document
import os
import re

# TODO: Fix CALL_EXPR detection for used functions
# TODO: Ensure parent_class is always correctly tracked
# TODO: Factor out common chunk creation logic


def create_chunk(code, file_path, chunk_type, extent=None, includes=None, current_class=None,
                 defined=None, used=None, fields=None, ast=None, max_chunk_size=500,
                 generator="clang"):

    chunks = []
    if extent:
        chunk_code = code[extent.start.offset:extent.end.offset].strip()
    else:
        chunk_code = code.strip()

    def make_doc(sub_code):
        return Document(
            page_content=sub_code,
            metadata={
                "file_path": file_path,
                "type": chunk_type,
                "includes": includes or [],
                "parent_class": current_class,
                "defined_functions": defined or [],
                "used_functions": used or [],
                "defined_fields": fields or [],
                "hash": hashlib.sha256(sub_code.encode('utf-8')).hexdigest(),
                "start_point": (extent.start.line, extent.start.column) if extent else None,
                "end_point": (extent.end.line, extent.end.column) if extent else None,
                "ast": ast,
                "generated_by": generator
            }
        )

    if len(chunk_code) > max_chunk_size:
        for i in range(0, len(chunk_code), max_chunk_size):
            sub_chunk = chunk_code[i:i+max_chunk_size].strip()
            chunks.append(make_doc(sub_chunk))
    else:
        chunks.append(make_doc(chunk_code))

    return chunks


def node_to_string(node, indent_level=0):
    indent = "  " * indent_level
    result = f"{indent}{node.kind.name}: {node.spelling}\n"
    for child in node.get_children():
        result += node_to_string(child, indent_level + 1)
    return result


def extract_defined_and_used_functions(node):
    defined = set()
    used = set()

    def visit(n):
        if n.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]:
            defined.add(n.spelling)
        elif n.kind == CursorKind.CALL_EXPR:
            callee = n.referenced or n.get_definition()
            if callee and callee.spelling:
                used.add(callee.spelling)
        for c in n.get_children():
            visit(c)

    visit(node)
    return list(defined), list(used - defined)


def extract_chunks(tu, code: str, file_path: str):
    chunks = []
    includes = []

    def recurse(node, current_class=None):
        if node.kind == CursorKind.INCLUSION_DIRECTIVE:
            includes.append(node.spelling)

        elif node.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL] and node.is_definition():
            fields = [c.spelling for c in node.get_children() if c.kind == CursorKind.FIELD_DECL]
            ast_str = node_to_string(node)
            chunks.extend(create_chunk(code, file_path, "class" if node.kind == CursorKind.CLASS_DECL else "struct",
                                       extent=node.extent, includes=includes, fields=fields, ast=ast_str))
            current_class = node.spelling

        elif node.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD] and node.is_definition():
            defined, used = extract_defined_and_used_functions(node)
            ast_str = node_to_string(node)
            chunks.extend(create_chunk(code, file_path, "function", extent=node.extent,
                                       includes=includes, current_class=current_class,
                                       defined=defined, used=used, ast=ast_str))

        for child in node.get_children():
            recurse(child, current_class)

    recurse(tu.cursor)
    return chunks


def extract_defined_and_used_functions_regex(code: str):
    defined = re.findall(r'\b(?:explicit\s+)?(?:\w+::)?(\w+)\s*\([^)]*\)\s*(?:{[^}]*}|;)', code)
    used = re.findall(r'\b(?:\w+::)?(\w+)\s*\(', code)
    return defined, list(set(used) - set(defined))


def extract_header_chunks(code: str, file_path: str):
    chunks = []
    includes = re.findall(r'#include\s*["<](\w+\.\w+)[">]', code)

    class_matches = re.finditer(r'(class\s+\w+[^}]*};)', code, re.DOTALL)
    for match in class_matches:
        class_code = match.group(0)
        defined, used = extract_defined_and_used_functions_regex(class_code)
        chunks.extend(create_chunk(class_code, file_path, "class", includes=includes,
                                   defined=defined, used=used, generator="regex"))

    return chunks
