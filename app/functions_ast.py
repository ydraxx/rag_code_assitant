import hashlib
from langchain_core.documents import Document
import re


def extract_includes_from_ast(root_node, code: str):

    includes = []

    def recurse(node):
        if node.type == 'preproc_include':
            include_text = code[node.start_byte:node.end_byte].strip()
            includes.append(include_text)
        for child in node.children:
            recurse(child)

    recurse(root_node)
    return includes


def extract_used_functions(code_chunk: str):
    """
    Extracts function/method names being used (called) within a chunk of code.
    """
    pattern = r'\b([a-zA-Z_]\w*)\s*\('
    candidates = re.findall(pattern, code_chunk)
    keywords = {'if', 'for', 'while', 'switch', 'return', 'sizeof', 'catch', 'throw', 'new', 'delete'}
    return list(set(c for c in candidates if c not in keywords))


def extract_defined_functions(node, code: str):
    """
    Extract function names defined by this node.
    Only applies to function_definition nodes.
    """
    defined = []
    if node.type == 'function_definition':
        for child in node.children:
            if child.type == 'function_declarator':
                for decl_child in child.children:
                    if decl_child.type == 'identifier':
                        defined.append(code[decl_child.start_byte:decl_child.end_byte])
    return defined


def extract_defined_fields(node, code: str):
    """
    Extracts field (member variable) names defined in a class/struct.
    """
    fields = []
    if node.type == 'field_declaration':
        for child in node.children:
            if child.type in ['init_declarator', 'identifier']:
                fields.append(code[child.start_byte:child.end_byte])
    return fields


def extract_chunks_from_ast(root_node, code: str, file_path: str):
    chunks = []
    includes = extract_includes_from_ast(root_node, code)

    def recurse(node, current_class=None):

        if node.type in ['class_specifier', 'struct_specifier']:
            class_name = None
            defined_fields = []

            for child in node.children:
                if child.type == 'type_identifier':
                    class_name = code[child.start_byte:child.end_byte]
                defined_fields.extend(extract_defined_fields(child, code))

            chunk_code = code[node.start_byte:node.end_byte].strip()

            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": node.type,
                    "includes": includes,
                    "parent_class": None,
                    "defined_functions": [],
                    "defined_fields": defined_fields,
                    "used_functions": extract_used_functions(chunk_code),
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

            for child in node.children:
                recurse(child, current_class=class_name)

        elif node.type == 'function_definition':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            defined = extract_defined_functions(node, code)
            used = extract_used_functions(chunk_code)

            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": node.type,
                    "includes": includes,
                    "parent_class": current_class,
                    "defined_functions": defined,
                    "used_functions": used,
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'declaration':
            has_func_decl = any(child.type == 'function_declarator' for child in node.children)
            if has_func_decl:
                chunk_code = code[node.start_byte:node.end_byte].strip()
                used = extract_used_functions(chunk_code)
                defined = []

                for child in node.children:
                    if child.type == 'function_declarator':
                        for decl_child in child.children:
                            if decl_child.type == 'identifier':
                                defined.append(code[decl_child.start_byte:decl_child.end_byte])

                chunks.append(Document(
                    page_content=chunk_code,
                    metadata={
                        "file_path": file_path,
                        "type": "function_declaration",
                        "includes": includes,
                        "parent_class": current_class,
                        "defined_functions": defined,
                        "used_functions": used,
                        "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                        "start_point": node.start_point,
                        "end_point": node.end_point,
                        "ast": node.sexp(),
                    }
            ))
                
        elif node.type == 'enum_specifier':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "enum",
                    "includes": includes,
                    "parent_class": current_class,
                    "defined_functions": [],
                    "used_functions": [],
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'type_definition':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "typedef",
                    "includes": includes,
                    "parent_class": current_class,
                    "defined_functions": [],
                    "used_functions": [],
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'using_declaration':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "using",
                    "includes": includes,
                    "parent_class": current_class,
                    "defined_functions": [],
                    "used_functions": [],
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'alias_declaration':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "using_alias",
                    "includes": includes,
                    "parent_class": current_class,
                    "defined_functions": [],
                    "used_functions": [],
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'namespace_definition':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "namespace",
                    "includes": includes,
                    "parent_class": current_class,
                    "defined_functions": [],
                    "used_functions": [],
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'template_declaration':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "template_declaration",
                    "includes": includes,
                    "parent_class": current_class,
                    "defined_functions": [],
                    "used_functions": extract_used_functions(chunk_code),
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'template_declaration':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "template_declaration",
                    "includes": includes,
                    "parent_class": current_class,
                    "defined_functions": [],
                    "used_functions": extract_used_functions(chunk_code),
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'preproc_def':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "macro_define",
                    "includes": includes,
                    "parent_class": None,
                    "defined_functions": [],
                    "used_functions": [],
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'preproc_function_def':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "macro_function_define",
                    "includes": includes,
                    "parent_class": None,
                    "defined_functions": [],
                    "used_functions": [],
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        elif node.type == 'preproc_undef':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": "macro_undef",
                    "includes": includes,
                    "parent_class": None,
                    "defined_functions": [],
                    "used_functions": [],
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "ast": node.sexp(),
                }
            ))

        else:
            for child in node.children:
                recurse(child, current_class)

    recurse(root_node)
    return includes, chunks
