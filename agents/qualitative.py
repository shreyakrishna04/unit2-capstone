# filename: agents/qualitative.py

import os
import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# Gemini via the OpenAI-compatible endpoint (same pattern as your smoke test & reference)
client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
model = SentenceTransformer("all-MiniLM-L6-v2")


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    chroma = chromadb.PersistentClient(path="./data/chroma")
    collection = chroma.get_collection("enterprise-docs")
    embedding = model.encode([query]).tolist()
    results = collection.query(query_embeddings=embedding, n_results=top_k)
    return [
        {
            "content": doc,
            "source": meta["source"],
            "chunk": meta["chunk"]
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]


def build_prompt(query: str, chunks: list[dict], history_context: str = "") -> str:
    context = ""
    for i, chunk in enumerate(chunks):
        context += f"[Source {i+1}: {chunk['source']}]\n{chunk['content']}\n\n"

    # history_context sits after CONTEXT so retrieved docs stay the primary
    # grounding source and citations aren't displaced by prior conversation.
    return f"""You are a helpful enterprise documentation assistant.
Answer the question using ONLY the context provided below.
If the answer is not in the context, say "I cannot find this information in the provided documents."
Always cite the source number(s) you used.

CONTEXT:
{context}

{history_context}QUESTION: {query}

ANSWER:"""


def run(query: str, history_context: str = "") -> dict:
    chunks = retrieve(query)
    prompt = build_prompt(query, chunks, history_context)
    response = client.chat.completions.create(
        model="gemini-3.5-flash-lite",
        max_tokens=1024,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert assistant. Answer questions accurately "
                    "using ONLY the provided context. If the context does not "
                    "contain the answer, say so and do not use outside knowledge."
                )
            },
            {"role": "user", "content": prompt}
        ]
    )
    return {
        "answer": response.choices[0].message.content,
        "chunks": chunks,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens
    }
