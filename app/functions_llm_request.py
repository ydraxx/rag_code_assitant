from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from ollama import Client

from config import llm_cfg
from functions_embeddings import CustomEmbedding


class OllamaLLM:
    def __init__(self, model_name: str = llm_cfg['MODEL_NAME']):
        self.client = Client(host= llm_cfg['HOST'])
        self.model_name = model_name

    def generate_answer(self, context: str, query: str):
        prompt = f"""
            ## Context:

            You are an intelligent assistant tasked with explaining a code snippet from Summit, a financial software package.

            ## Objective:

            Provide a clear, high-level summary of the code. Explain its purpose, main functionalities,
            and interactions with other components.
            Focus on significant steps and skip trivial ones.

            ## Instructions:

            - Context: Explain the context in which this code is used within Summit.
            - Objective: Clearly state the main goal of the code.
            - Inputs and Outputs: Describe the inputs the code accepts and the outputs it produces.
            - Functionning: Outline the main steps or algorithms used in the code.
            - Interactions: Describe how the code interacts with other components or services.
            
            ## Code snippet to analyse:

            {query}

            ## Code Context:

            {context}
        """

        response = self.client.chat(model=self.model_name, messages=[
            {"role": "user", "content": prompt}
        ])
        return response['message']['content']
    

def similarity_search(query: str, index_path:str, embedding ,nb_results:int):
    """
    Search similar vector from user query
    """
    # Load FAISS vector store
    index = FAISS.load_local(index_path, embedding, allow_dangerous_deserialization=True)
    print('FAISS index loaded.')

    # Similarity search
    results = index.similarity_search(query, k=nb_results)
    print('Similarity search done.')

    for res in results:
        chunk = res

    return chunk


def get_all_chunks_from_vectorstore(index_path: str, embedding) -> list:
    """
    Returns list of all chunks from vectorstore
    """
    vector_store = FAISS.load_local(index_path, embedding, allow_dangerous_deserialization=True)
    return list(vector_store.docstore._dict.values())


def get_related_chunks(target_chunk: Document, all_chunks: list) -> list:
    """
    Return chunks that help explain the target_chunk, based on:
    - Definitions of functions used by the target
    - Same parent class (if applicable)
    - (Optional) Same file
    """

    related_chunks = []

    target_hash = target_chunk.metadata.get("hash")
    used_functions = target_chunk.metadata.get("used_functions", [])
    target_defined_functions = target_chunk.metadata.get("defined_functions", [])
    parent_class = target_chunk.metadata.get("parent_class")
    file_path = target_chunk.metadata.get("file_path")

    for chunk in all_chunks:
        # Skip self
        if chunk.metadata.get("hash") == target_hash:
            continue

        chunk_defined_functions = chunk.metadata.get("defined_functions", [])
        chunk_used_functions = chunk.metadata.get("used_functions", [])
        chunk_parent_class = chunk.metadata.get("parent_class")
        chunk_type = chunk.metadata.get("type")
        chunk_file_path = chunk.metadata.get("file_path")

        # The chunk defines a function used by the target
        defines_used_func = any(func in chunk_defined_functions for func in used_functions)

        # The chunk belongs to the same class (if method of a class)
        same_class = (
            parent_class and
            chunk_type == "function_definition" and
            chunk_parent_class == parent_class
        )

        # Exclude reverse dependency: chunk uses functions defined in the target
        uses_target_func = any(func in chunk_used_functions for func in target_defined_functions)
        if uses_target_func:
            continue

        # Same file context
        # same_file = chunk_file_path == file_path

        if defines_used_func or same_class:  # or same_file
            related_chunks.append(chunk)

    return related_chunks




def LLM_request(query: str, index_path: str) -> str:

    embedding = CustomEmbedding()

    all_chunks = get_all_chunks_from_vectorstore(index_path=index_path, embedding=embedding)
    chunk = similarity_search(query=query, index_path=index_path, embedding=embedding, nb_results=1)

    context = get_related_chunks(target_chunk=chunk, all_chunks=all_chunks)

    return all_chunks
    # llm = OllamaLLM()
    # response = llm.generate_answer(context=context, query=chunk)
    # print("LLM :\n", response)
    # return response
