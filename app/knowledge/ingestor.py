from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from app.config import settings


def _split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """Simple recursive character text splitter (avoids langchain_text_splitters dependency)."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks


def ingest_corpus(texts: list[str], sources: list[str], namespace: str) -> int:
    """
    Embed and upsert documents into Pinecone under the given namespace.
    Returns number of chunks ingested.

    Args:
        texts: list of regulatory document texts
        sources: list of source labels (e.g. "GDPR Art. 28", "EDPB-2021-05")
        namespace: Pinecone namespace (e.g. "gdpr", "soc2")
    """
    assert len(texts) == len(sources), "texts and sources must have equal length"

    docs = []
    for text, source in zip(texts, sources):
        for chunk in _split_text(text):
            docs.append(Document(
                page_content=chunk,
                metadata={"source": source, "namespace": namespace},
            ))

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.openai_api_key)
    PineconeVectorStore.from_documents(
        docs,
        embeddings,
        index_name=settings.pinecone_index_name,
        namespace=namespace,
        pinecone_api_key=settings.pinecone_api_key,
    )
    return len(docs)
