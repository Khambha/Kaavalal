"""Load knowledge/*.md into the vector store.

Run from the backend folder:  python -m app.chatbot.ingest
Re-run whenever you add or edit knowledge files.
"""
from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from . import config
from .rag import get_vectorstore


def main():
    kb = Path(config.KB_DIR)
    files = sorted(kb.glob("*.md"))
    if not files:
        raise SystemExit(f"No .md files found in {kb.resolve()}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    docs = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for chunk in splitter.split_text(text):
            docs.append(Document(page_content=chunk, metadata={"source": f.name}))

    store = get_vectorstore()
    try:
        store.delete_collection()  # rebuild cleanly
        get_vectorstore.cache_clear()
        store = get_vectorstore()
    except Exception:
        pass
    store.add_documents(docs)
    print(f"Ingested {len(docs)} chunks from {len(files)} files.")


if __name__ == "__main__":
    main()
