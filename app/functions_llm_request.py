from langchain_community.vectorstores import FAISS
from ollama import Client

from functions_embeddings import CustomEmbedding


def similarity_search(chunk: str, index_path:str, nb_results:int):
    embedding = CustomEmbedding()

    # Load FAISS vector store
    index = FAISS.load_local(index_path, embedding, allow_dangerous_deserialization=True)
    print('FAISS index loaded.')

    # Similarity search
    results = index.similarity_search(chunk, k=nb_results)
    print('Similarity search done.')

    for res in results:
        print(res)


class OllamaLLM:
    def __init__(self, model_name: str = 'llama3'):
        self.client = Client(host="http://localhost:11434")
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
    

def LLM_request(query: str):
    llm = OllamaLLM()
    contexte = """
        int calculate_interest(double amount, double rate) {
            return amount * rate;
        }
        """
    query = "Que fait cette fonction et dans quel cas est-elle utile ?"

    reponse = llm.generate_answer(context=contexte, query=query)
    print("Réponse du LLM :\n", reponse)

LLM_request('')