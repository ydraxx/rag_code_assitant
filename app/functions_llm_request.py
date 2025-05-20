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
    

def similarity_search(query: str, index_path:str, nb_results:int):
    embedding = CustomEmbedding()

    # Load FAISS vector store
    index = FAISS.load_local(index_path, embedding, allow_dangerous_deserialization=True)
    print('FAISS index loaded.')

    # Similarity search
    results = index.similarity_search(query, k=nb_results)
    print('Similarity search done.')

    chunks = []

    for res in results:
        chunks.append(res)

    return chunks


def LLM_request(query: str, index_path: str) -> str:
    llm = OllamaLLM()
    context = similarity_search(query=query, index_path=index_path, nb_results=1)
    response = llm.generate_answer(context=context, query=query)
    print("Réponse du LLM :\n", response)
    return response
