"""RAG store: Chroma vector DB + multilingual embeddings."""
from functools import lru_cache
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from . import config


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    return Chroma(
        collection_name="kaavalal_kb",
        embedding_function=embeddings,
        persist_directory=config.VECTOR_DIR,
    )


def search(query: str, k: int = 4):
    return get_vectorstore().similarity_search(query, k=k)
