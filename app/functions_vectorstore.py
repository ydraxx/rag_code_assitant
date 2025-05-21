import chardet
import faiss
import hashlib
import json
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
import numpy as np
import os
from os import path
import re
from uuid import uuid4

from config import vector_cfg
from functions_embeddings import CustomEmbedding
from functions_parsing import parse_cpp_code


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


def extract_called_functions(code_chunk: str):
    """
    Extracts function/method names being called within a chunk of code.
    """
    pattern = r'\b([a-zA-Z_]\w*)\s*\('
    candidates = re.findall(pattern, code_chunk)
    keywords = {'if', 'for', 'while', 'switch', 'return', 'sizeof', 'catch', 'throw', 'new', 'delete'}
    return list(set(c for c in candidates if c not in keywords))


def extract_chunks_from_ast(root_node, code: str, file_path: str):
    chunks = []
    includes = extract_includes_from_ast(root_node, code)

    def recurse(node, current_class=None):
        if node.type in ['class_specifier', 'struct_specifier']:
            # Get class name
            class_name = None
            for child in node.children:
                if child.type == 'type_identifier':
                    class_name = code[child.start_byte:child.end_byte]
                    break

            # Extract class chunk
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": node.type,
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "includes": includes,
                    "parent_class": None,
                    "called_functions": extract_called_functions(chunk_code),
                    "ast": node.sexp(),
                }
            ))

            # Recurse into class body with class_name context
            for child in node.children:
                recurse(child, current_class=class_name)

        elif node.type == 'function_definition':
            chunk_code = code[node.start_byte:node.end_byte].strip()
            chunks.append(Document(
                page_content=chunk_code,
                metadata={
                    "file_path": file_path,
                    "type": node.type,
                    "hash": hashlib.sha256(chunk_code.encode()).hexdigest(),
                    "start_point": node.start_point,
                    "end_point": node.end_point,
                    "includes": includes,
                    "parent_class": current_class,
                    "called_functions": extract_called_functions(chunk_code),
                    "ast": node.sexp(),
                }
            ))

        else:
            for child in node.children:
                recurse(child, current_class)

    recurse(root_node)
    return includes, chunks


def load_splits_doc(folder_path: str):
    """
    Returns list of splitted documents (text content + metadata)
    """

    splits = []

    # Load texts
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_path = os.path.normpath(file_path)

            # Handle PDF documents
            if file_path.endswith('.pdf'):
                loader = PyMuPDFLoader(file_path)
                doc = loader.load()

            # Handle C, C++ documents
            elif file_path.endswith(('.cc', '.h', '.c', '.cpp', '.hpp')):
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                    result = chardet.detect(raw_data)
                    encoding = result['encoding']

                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    ast = parse_cpp_code(content)
                    includes, doc = extract_chunks_from_ast(ast, content, file_path)
                    splits.extend(doc)
    return splits


def document_hash(document):
    """
    Calculate unique hash for document
    """
    return hashlib.sha256(document.page_content.encode('utf-8')).hexdigest()


def load_existing_doc(json_file: str):
    """
    Load existing hashes doc from json file
    """
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            return set(json.load(f))
    return set()


def save_json(json_file: str, hashes):
    """
    Save hashes doc to json file
    """
    with open(json_file, 'w') as f:
        json.dump(list(hashes), f)


def build_vectorstore(folder_path: str, index_path: str, json_file: str):
    """
    Create or update vectorstore
    """

    splits = load_splits_doc(folder_path)
    embedding = CustomEmbedding()

    existing_hashes = load_existing_doc(json_file)

    new_embeddings = []
    new_splits =  []
    for split in splits:
        doc_hash = document_hash(split)
        if doc_hash not in existing_hashes:
            embedding_vector = embedding.embed_query(split.page_content)
            new_embeddings.append(embedding_vector)
            new_splits.append(split)
            existing_hashes.add(doc_hash)
            print('New document processed.')
        else:
            print('Document already exists.')

    if os.path.exists(index_path):
        vector_store = FAISS.load_local(index_path, embedding, allow_dangerous_deserialization=True)
        print('Vector store already exists.')
    
    else:
        dim = len(new_embeddings[0]) if new_embeddings else 1024
        index = faiss.IndexFlatIP(dim)
        vector_store = FAISS(index=index,
                             docstore=InMemoryDocstore({}),
                             embedding_function=embedding,
                             index_to_docstore_id={})
        print('New vector store created.')

    if new_embeddings:
        new_embeddings = np.array(new_embeddings).astype('float32')
        vector_store.index.add(new_embeddings)
        for split in new_splits:
            new_uuid = str(uuid4())
            vector_store.docstore.add({new_uuid: split})
            vector_store.index_to_docstore_id[vector_store.index.ntotal - len(new_splits) + new_splits.index(split)] = new_uuid

        vector_store.save_local(index_path)
        save_json(json_file, existing_hashes)
        print('New embeddings added and index saved.')
    else:
        print('No new documents to process.')


build_vectorstore(vector_cfg["DOCS_PATH"], vector_cfg["INDEX_PATH"], vector_cfg["JSON_PATH"])