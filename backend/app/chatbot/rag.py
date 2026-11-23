"""RAG store: Chroma vector DB + multilingual embeddings."""
from functools import lru_cache
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from . import config

MIN_RELEVANCE = 0.30


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    return Chroma(
        collection_name="kaavalal_kb",
        embedding_function=embeddings,
        persist_directory=config.VECTOR_DIR,
    )


def search(query: str, k: int = 4):
    """Return only reasonably relevant knowledge chunks; raise if the index cannot be read."""
    matches = get_vectorstore().similarity_search_with_relevance_scores(query, k=k)
    return [doc for doc, score in matches if score >= MIN_RELEVANCE]
