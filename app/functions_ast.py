import hashlib
from langchain_core.documents import Document


def split_large_chunk(code_str: str, max_lines: int = 20) -> list:
    """
    Split chunks that are larger than X lines.
    """

    lines = code_str.strip().split('\n')
    if len(lines) <= max_lines:
        return [code_str.strip()]
    return [
        '\n'.join(lines[i:i + max_lines]).strip()
        for i in range(0, len(lines), max_lines)
    ]


def create_chunk(node, code_bytes, file_path: str, includes, current_class: str, namespace, chunk_type: str, defined=None, used=None):
    """
    Create chunks and set metadata.
    """
    
    chunk_code = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    split_chunks = split_large_chunk(chunk_code)
    total = len(split_chunks)
    documents = []

    for i, split_code in enumerate(split_chunks):
        documents.append(Document(
            page_content=split_code,
            metadata={
                "file_path": file_path,
                "type": chunk_type,
                "includes": includes,
                "class": current_class,
                "namespace": namespace,
                "defined_functions": defined or [],
                "used_functions": used or [],
                "hash": hashlib.sha256(split_code.encode()).hexdigest(),
                "start_point": node.start_point,
                "end_point": node.end_point,
                # "ast": node.sexp(),
                "chunk_index": i,
                "split_total": total
            }
        ))
    return documents


def extract_includes(root_node, code_bytes: bytes):
    """
    Search includes and extract only the dependency name.
    """

    includes = []

    def recurse(node):
        if node.type == 'preproc_include':
            # Find the child node that contains the include name
            found_include = False
            for child in node.children:
                if child.type == 'string' or child.type == 'system_lib_string':  # Check for both <...> and "..."
                    include_name = code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace").strip()
                    includes.append(include_name)
                    found_include = True
                    break 
            if not found_include:
                include_text = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()
                parts = include_text.split(maxsplit=1)
                if len(parts) > 1:  
                    includes.append(parts[1].strip()) 
                else :
                    includes.append(include_text)

        for child in node.children:
            recurse(child)

    recurse(root_node)
    return includes


def extract_defined_functions(node, code_bytes):
    """
    Search functions that are defined in the current chunk.
    """

    defined = []
    if node.type == 'function_definition':
        declarator = next((c for c in node.children if c.type == 'function_declarator'), None)
        if declarator:
            identifier = next(
                (c for c in declarator.children if c.type in ('identifier', 'field_identifier', 'destructor_name')),
                None
            )
            if identifier:
                name = code_bytes[identifier.start_byte:identifier.end_byte].decode("utf-8", errors="replace").strip()
                defined.append(name)
    return defined


def extract_used_functions(node, code_bytes):
    """
    Search which functions are called in the current chunk.
    """

    used = []

    def walk(n):
        if n.type == 'call_expression':
            fn_node = n.child_by_field_name('function')
            if fn_node and fn_node.type == 'identifier':
                fn_name = code_bytes[fn_node.start_byte:fn_node.end_byte].decode("utf-8", errors="replace").strip()
                used.append(fn_name)
        for child in n.children:
            walk(child)

    walk(node)
    return used


def collect_functions(node, code_bytes):
    defined = []
    used = []

    def walk(n):
        if n.type == 'function_definition':
            defined.extend(extract_defined_functions(n, code_bytes))
            used.extend(extract_used_functions(n, code_bytes))
        else:
            used.extend(extract_used_functions(n, code_bytes))
        for child in n.children:
            walk(child)

    walk(node)
    used_clean = list(set(used) - set(defined))
    return defined, used_clean


def extract_chunks(root_node, code: str, file_path: str):
    """
    By browsing the AST, search each chunk to create.
    """

    code_bytes = code.encode("utf-8")
    chunks = []
    includes = extract_includes(root_node, code_bytes)
    class_stack = []
    namespace_stack = []

    def recurse(node, current_class=None):
        node_type = node.type

        if node_type == 'namespace_definition':
            ns_name = None
            for child in node.children:
                if child.type == 'namespace_identifier':
                    ns_name = code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace").strip()
                    break
            namespace_stack.append(ns_name)
            for child in node.children:
                recurse(child, current_class)
            namespace_stack.pop()

        elif node_type in ['class_specifier', 'struct_specifier']:
            class_name = None
            for child in node.children:
                if child.type == 'type_identifier':
                    class_name = code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace").strip()
                    break
            class_stack.append(class_name)
            chunk_code = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()
            if len(chunk_code.splitlines()) >= 5:
                defined, used = collect_functions(node, code_bytes)
                docs = create_chunk(
                    node, code_bytes, file_path, includes,
                    current_class=class_name,
                    namespace="::".join(namespace_stack) if namespace_stack else None,
                    chunk_type=node_type,
                    defined=defined,
                    used=used
                )
                chunks.extend(docs)
            for child in node.children:
                recurse(child, current_class=class_name)
            class_stack.pop()

        elif node_type == 'function_definition':
            if current_class is None:
                defined = extract_defined_functions(node, code_bytes)
                used = extract_used_functions(node, code_bytes)
                used = list(set(used) - set(defined))
                chunk_code = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()
                if len(chunk_code.splitlines()) >= 3:
                    docs = create_chunk(
                        node, code_bytes, file_path, includes,
                        current_class=None,
                        namespace="::".join(namespace_stack) if namespace_stack else None,
                        chunk_type="function_definition",
                        defined=defined,
                        used=used
                    )
                    chunks.extend(docs)

        elif node_type in ['enum_specifier', 'type_definition']:
            chunk_code = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()
            if len(chunk_code.splitlines()) >= 3:
                current_class = class_stack[-1] if class_stack else None
                docs = create_chunk(
                    node, code_bytes, file_path, includes,
                    current_class=current_class,
                    namespace="::".join(namespace_stack) if namespace_stack else None,
                    chunk_type=node_type,
                    used=extract_used_functions(node, code_bytes)
                )
                chunks.extend(docs)

        for child in node.children:
            recurse(child, current_class)

    recurse(root_node)
    print(f"Chunks generated for {file_path}, chunks: {len(chunks)}")
    # print(chunks)
    return chunks
