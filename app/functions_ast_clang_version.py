from clang.cindex import Index, CursorKind, Config
import hashlib
from langchain_core.documents import Document
import os
import re


# TODO: some chunk are identical before indexation
# TODO: factoriser le code partie regex
# TODO: uniformiser le découpage du code


def create_chunk_clang(code: str, file_path: str, chunk_type: str, extent, includes=None, current_class=None, \
                        defined=None, used=None, fields=None, ast=None, max_chunk_size=500):

    chunk = []
    chunk_code = code[extent.start.offset:extent.end.offset].strip()

    if len(chunk_code) > max_chunk_size:
        current_offset = extent.start.offset
        while current_offset < extent.end.offset:
            next_offset = min(current_offset + max_chunk_size, extent.end.offset)
            sub_chunk_code = code[current_offset:next_offset].strip()
            chunk.append(Document(
                page_content=sub_chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": chunk_type,
                    "includes": includes or [],
                    "parent_class": current_class,
                    "defined_functions": defined or [],
                    "used_functions": used or [],
                    "defined_fields": fields or [],
                    "hash": hashlib.sha256(sub_chunk_code.encode('utf-8')).hexdigest(),
                    "start_point": (extent.start.line, extent.start.column),
                    "end_point": (extent.end.line, extent.end.column),
                    "ast": ast,
                    "generated_by": "clang"
                }
            ))
            current_offset = next_offset
    else:
        chunk.append(Document(
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
                "generated_by": "clang"
            }
        ))
    return chunk


def node_to_string(node, indent_level=0):
    # Utilisez l'indentation pour rendre la structure hiérarchique plus lisible
    indent = "  " * indent_level
    node_str = f"{indent}{node.kind.name}: {node.spelling}\n"
    for child in node.get_children():
        node_str += node_to_string(child, indent_level + 1)
    return node_str


def extract_chunks(tu, code: str, file_path: str):
    chunks = []
    includes = []
    root = tu.cursor

    def get_extent_code(extent):
        start_offset = extent.start.offset
        end_offset = extent.end.offset
        # print(f"Start Offset: {start_offset}, End Offset: {end_offset}")
        extracted_code = code[start_offset:end_offset]
        # print(f"Extracted Code: {extracted_code[:30]}...")
        return extracted_code

    def extract_defined_and_used_functions(node, extent_code):
        defined = set()
        used = set()

        def visit(n):
            if n.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]:
                defined.add(n.spelling)
            elif n.kind == CursorKind.CALL_EXPR:
                print(n.spelling)
                if n.referenced and n.referenced.spelling:
                    used.add(n.referenced.spelling)
                    print(f"Found call to function: {n.referenced.spelling}")
                else:
                    print(f"Call expression without reference: {n.spelling}")
            for child in n.get_children():
                visit(child)

        visit(node)
        return list(defined), list(used - defined)

    def recurse(node, current_class=None):
        kind = node.kind
        spelling = node.spelling

        # Capture les directives #include
        if kind == CursorKind.INCLUSION_DIRECTIVE:
            includes.append(spelling)

        if kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL] and node.is_definition():
            extent_code = get_extent_code(node.extent)
            fields = [c.spelling for c in node.get_children() if c.kind == CursorKind.FIELD_DECL]
            ast_str = node_to_string(node)

            chunks.extend(create_chunk_clang(
                code=code,
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

            chunks.extend(create_chunk_clang(
                code=code,
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
            # pas chunkés seuls sauf si hors d’une classe
            pass

        for child in node.get_children():
            recurse(child, current_class if kind != CursorKind.CLASS_DECL else spelling)

    recurse(root)
    print(f"Chunks generated for {file_path}: {len(chunks)}")
    return chunks


# HEADERS FILES PARSE WITH REGEX
def create_chunk_regex(code: str, file_path: str, chunk_type: str, includes=None, current_class=None, \
                       defined=None, used=None, fields=None, max_chunk_size=500):

    chunk = []

    if len(code) > max_chunk_size:
        current_offset = 0
        while current_offset < len(code):
            next_offset = min(current_offset + max_chunk_size, len(code))
            sub_chunk_code = code[current_offset:next_offset].strip()
            chunk.append(Document(
                page_content=sub_chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": chunk_type,
                    "includes": includes or [],
                    "parent_class": current_class,
                    "defined_functions": defined or [],
                    "used_functions": used or [],
                    "defined_fields": fields or [],
                    "hash": hashlib.sha256(sub_chunk_code.encode('utf-8')).hexdigest(),
                    "generated_by": "regex"
                }
            ))
            current_offset = next_offset
    else:
        chunk.append(Document(
            page_content=code,
            metadata={
                "file_path": file_path,
                "type": chunk_type,
                "includes": includes or [],
                "parent_class": current_class,
                "defined_functions": defined or [],
                "used_functions": used or [],
                "defined_fields": fields or [],
                "hash": hashlib.sha256(code.encode('utf-8')).hexdigest(),
                "generated_by": "regex"
            }
        ))
    return chunk


def extract_defined_and_used_functions_regex(code: str):
    # Regex pour capturer les définitions de fonctions, incluant les méthodes de classes et les fonctions globales
    defined_pattern = r'\b(?:explicit\s+)?\b(?:\w+::)?(\w+)\s*\([^)]*\)\s*(?:{[^}]*}|;)'
    defined_functions = re.findall(defined_pattern, code)

    # Regex pour capturer les appels de fonctions
    used_pattern = r'\b(?:\w+::)?(\w+)\s*\('
    used_functions = re.findall(used_pattern, code)

    # Utilisation d'un set pour éviter les doublons et soustraire les fonctions définies des utilisées
    used_functions_set = set(used_functions) - set(defined_functions)

    return defined_functions, list(used_functions_set)


def extract_header_chunks(code: str, file_path: str):
    
    chunks = []

    # Extraire les directives #include
    include_pattern = r'#include\s*["<](\w+\.\w+)[">]'
    includes = re.findall(include_pattern, code)

    # Match les classes
    class_pattern = r'(class\s+\w+\s*(?:[:\w\s,]*?)?\s*{[^}]*};)'
    class_matches = re.finditer(class_pattern, code, re.DOTALL)
    for i, match in enumerate(class_matches):
        class_name = match.group(1)
        class_code = match.group(0)

        defined, used = extract_defined_and_used_functions_regex(class_code)

        chunks.extend(create_chunk_regex(
            code=class_code.strip(), 
            file_path=file_path, 
            chunk_type="class", 
            includes=includes, 
            current_class=None,
            defined=defined,
            used=used,
            fields=None
        ))

        # Capturer les fonctions membres
        func_member_pattern = r'(\w+\s*::\s*\w+\s*\([^\)]*\)\s*{[^}]*})'
        member_func_matches = re.finditer(func_member_pattern, class_code, re.DOTALL)
        for j, func_match in enumerate(member_func_matches):
            func_code = func_match.group(0)
            defined, used = extract_defined_and_used_functions_regex(func_code)
            chunks.extend(create_chunk_regex(
            code=class_code.strip(), 
            file_path=file_path, 
            chunk_type="member_function", 
            includes=includes, 
            current_class=class_name,
            defined=defined,
            used=used,
            fields=None
        ))


    # Match les structs
    struct_pattern = r'struct\s+(\w+)\s*{[^}]*};'
    struct_matches = re.finditer(struct_pattern, code, re.DOTALL)
    for i, match in enumerate(struct_matches):
        struct_name = match.group(1)
        struct_code = match.group(0)
        defined, used = extract_defined_and_used_functions_regex(struct_code)
        chunks.extend(create_chunk_regex(
            code=struct_code.strip(), 
            file_path=file_path, 
            chunk_type="struct", 
            includes=includes, 
            current_class=None,
            defined=defined,
            used=used,
            fields=None
        ))

    # Match les enums
    enum_pattern = r'enum\s+(class\s+)?(\w+)\s*{[^}]*};?'
    enum_matches = re.finditer(enum_pattern, code, re.DOTALL)
    for i, match in enumerate(enum_matches):
        enum_name = match.group(2)
        enum_code = match.group(0)
        chunks.extend(create_chunk_regex(
            code=enum_code.strip(), 
            file_path=file_path, 
            chunk_type="enum", 
            includes=includes, 
            current_class=None,
            defined=None,
            used=None,
            fields=None
        ))

    # Match les fonctions globales
    func_pattern = r'(?:^[\w:\*\&<>\s]+?\s+(\w+)\s*\([^\)]*\)\s*;)' 
    func_matches = re.finditer(func_pattern, code, re.MULTILINE)
    for i, match in enumerate(func_matches):
        func_code = match.group(0)
        defined, used = extract_defined_and_used_functions_regex(func_code)
        chunks.extend(create_chunk_regex(
            code=func_code.strip(), 
            file_path=file_path, 
            chunk_type="function_decl", 
            includes=includes, 
            current_class=None,
            defined=defined,
            used=used,
            fields=None
        ))


    # En dernier recours : chunk global du header
    # chunks.append(Document(
    #     page_content=code.strip(),
    #     metadata={"source": file_path, "type": "full_header", "chunk_id": "all"}
    # ))

    print(f"Chunks generated for {file_path}, chunks: {len(chunks)}")
    return chunks
