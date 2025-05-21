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


def get_related_chunks(target_chunk: list, all_chunks: list) -> list:
    """
    Return related chunks based on:
    - parent class
    - called functions
    - same file
    """

    related_chunks = []

    parent_class = target_chunk.metadata.get("parent_class")
    called_functions = target_chunk.metadata.get("called_functions", [])
    file_path = target_chunk.metadata.get("file_path")

    for chunk in all_chunks:
        # Exclude the target chunk
        if chunk.metadata.get('hash') == target_chunk.metadata.get('hash'):
            continue

        same_file = chunk.metadata.get('file_path') == file_path
        same_class = parent_class and chunk.metadata.get('type') in ['function_definition'] and chunk.metadata.get("parent_class") == parent_class
        contains_called_func = any(func in chunk.page_content for func in called_functions)

        if same_class or contains_called_func or same_file:
            related_chunks.append(chunk)

    return related_chunks


def LLM_request(query: str, index_path: str) -> str:

    embedding = CustomEmbedding()

    all_chunks = get_all_chunks_from_vectorstore(index_path=index_path, embedding=embedding)
    chunk = similarity_search(query=query, index_path=index_path, embedding=embedding, nb_results=1)

    context = get_related_chunks(target_chunk=chunk, all_chunks=all_chunks)

    return context
    # llm = OllamaLLM()
    # response = llm.generate_answer(context=context, query=chunk)
    # print("LLM :\n", response)
    # return response
