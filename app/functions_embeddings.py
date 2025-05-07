from typing import List
from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import HuggingFaceEmbeddings


class CustomEmbedding(Embeddings):

    def __init__(self, model_name: str = "intfloat/e5-large-v2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = HuggingFaceEmbeddings(
            model_name=self.model_name,
            model_kwargs={"device": self.device}
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self.model.embed_query(text)
