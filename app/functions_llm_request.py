from langchain_community.vectorstores import FAISS

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


chunk = """class Trade {
public:
    Trade(int id, double amount) : id(id), amount(amount) {}
    void print() const {
        std::cout << "Trade ID: " << id << ", Amount: " << amount << std::endl;
    }"""

similarity_search(chunk, '../test_vectorstore/vectorstore/', 1)