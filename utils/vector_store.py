# utils/vector_store.py
"""
Vector Store Utilities – Optimised for Speed & Streamlit Caching
"""

import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import streamlit as st
import traceback
import torch

from config import VECTOR_DB_DIR, VECTOR_SETTINGS

_device = "cuda" if torch.cuda.is_available() else "cpu"

# ==========================================================
# CACHED RESOURCES (Prevents "Client Closed" errors)
# ==========================================================

@st.cache_resource
def get_embedding_model():
    """Loads and caches the SentenceTransformer model so it doesn't reload."""
    print(f"Loading embedding model on {_device}...")
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name, device=_device)
    print("Model loaded.")
    return model


@st.cache_resource
def get_chroma_collection():
    """Initializes and caches the ChromaDB client and collection."""
    try:
        print("Initializing ChromaDB client...")
        client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
        collection = client.get_or_create_collection(name="lecture_transcripts")
        print("ChromaDB ready.")
        return collection
    except Exception as e:
        print(f"ERROR initializing ChromaDB: {e}")
        traceback.print_exc()
        raise RuntimeError(
            f"Failed to initialize vector database at {VECTOR_DB_DIR}: {e}\n"
            f"Try deleting the '{VECTOR_DB_DIR}' folder and restarting."
        )


def chunk_text(text):
    print("Chunking transcript...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=VECTOR_SETTINGS["chunk_size"],
        chunk_overlap=VECTOR_SETTINGS["chunk_overlap"],
    )
    chunks = splitter.split_text(text)
    print(f"Created {len(chunks)} chunks.")
    return chunks


def create_vector_store(transcript, document_id="current_video"):
    if not transcript or not transcript.strip():
        print("Transcript is empty, nothing to store.")
        return 0

    collection = get_chroma_collection()
    delete_document(document_id)

    try:
        chunks = chunk_text(transcript)
        print(f"Chunks: {len(chunks)}")

        model = get_embedding_model()
        print("Generating embeddings (batch size = 64)...")
        embeddings = model.encode(
            chunks,
            convert_to_numpy=True,
            batch_size=64,
            show_progress_bar=True,
        ).tolist()
        print(f"Embeddings shape: {len(embeddings)}")

        ids = [f"{document_id}_{i}" for i in range(len(chunks))]
        metadatas = [{"document": document_id, "chunk": i} for i in range(len(chunks))]

        print("Adding to ChromaDB...")
        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        print(f"Successfully stored {len(chunks)} chunks.")
        return len(chunks)

    except Exception as e:
        print("ERROR in create_vector_store:")
        traceback.print_exc()
        raise


def search_vector_store(query, document_id="current_video"):
    collection = get_chroma_collection()
    model = get_embedding_model()

    query_embedding = model.encode(query, convert_to_numpy=True).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=VECTOR_SETTINGS["top_k"],
        where={"document": document_id},
    )
    return results.get("documents", [[]])[0]


def delete_document(document_id="current_video"):
    try:
        collection = get_chroma_collection()
        collection.delete(where={"document": document_id})
    except Exception:
        pass


def clear_database():
    try:
        collection = get_chroma_collection()
        data = collection.get()
        if data["ids"]:
            collection.delete(ids=data["ids"])
    except Exception:
        pass
