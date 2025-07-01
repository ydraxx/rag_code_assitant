import hashlib
from langchain_core.documents import Document
import re


def create_chunk(node, code, file_path, includes, current_class, chunk_type, defined=None, used=None):
    chunk_code = code.encode("utf-8")[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    return Document(
        page_content=chunk_code,
        metadata={
            "file_path": file_path,
            "type": chunk_type,
            "includes": includes,
            "class": current_class,
            "defined_functions": defined or [],
            "used_functions": used or [],
            "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
            "start_point": node.start_point,
            "end_point": node.end_point,
            "ast": node.sexp(),
        }
    )


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
                        defined.append(code[decl_child.start_byte:decl_child.end_byte].strip())
    return defined


def collect_functions(node, code):
    defined = []
    used = []

    def walk(n):
        if n.type == 'function_definition':
            fn_names = extract_defined_functions(n, code)
            fn_code = code[n.start_byte:n.end_byte]
            fn_used = extract_used_functions(fn_code)
            defined.extend(fn_names)
            used.extend(fn_used)
        for child in n.children:
            walk(child)

    walk(node)
    used_clean = list(set(used) - set(defined))
    return defined, used_clean


def extract_chunks_from_ast(root_node, code: str, file_path: str):
    # code = code.encode("utf-8")
    chunks = []
    includes = extract_includes_from_ast(root_node, code)
    class_stack = []

    def recurse(node, current_class=None):
        node_type = node.type

        if node_type in ['class_specifier', 'struct_specifier']:
            class_name = None
            for child in node.children:
                if child.type == 'type_identifier':
                    class_name = code[child.start_byte:child.end_byte]
                    break

            class_stack.append(class_name)
            chunk_code = code[node.start_byte:node.end_byte].strip()
            if len(chunk_code.splitlines()) >= 5:
                defined, used = collect_functions(node, code)
                chunks.append(create_chunk(
                    node, code, file_path, includes,
                    current_class=class_name,
                    chunk_type=node_type,
                    defined=defined,
                    used=used
                ))

            for child in node.children:
                recurse(child, current_class=class_name)

            class_stack.pop()

        elif node_type == 'function_definition':
            if current_class is None:  # uniquement les fonctions libres
                defined = extract_defined_functions(node, code)
                chunk_code = code[node.start_byte:node.end_byte].strip()
                used = list(set(extract_used_functions(chunk_code)) - set(defined))

                if len(chunk_code.splitlines()) >= 5:
                    chunks.append(create_chunk(
                        node, code, file_path, includes, current_class,
                        chunk_type="function_definition",
                        defined=defined,
                        used=used
                    ))

        elif node_type == 'namespace_definition':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            if len(chunk_code.splitlines()) >= 3:
                current_class = class_stack[-1] if class_stack else None
                defined, used = collect_functions(node, code)
                chunks.append(create_chunk(
                    node, code, file_path, includes, current_class,
                    chunk_type=node_type,
                    defined=defined,
                    used=used
                ))


        elif node_type in ['enum_specifier', 'type_definition', 'namespace_definition']:
            chunk_code = code[node.start_byte:node.end_byte].strip()
            if len(chunk_code.splitlines()) >= 3:
                current_class = class_stack[-1] if class_stack else None
                chunks.append(create_chunk(
                    node, code, file_path, includes, current_class,
                    chunk_type=node_type,
                    used=extract_used_functions(chunk_code)
                ))

        for child in node.children:
            recurse(child, current_class)

    recurse(root_node)
    print(f"Chunks generated for {file_path}, chunks: {len(chunks)}")
    return chunks
