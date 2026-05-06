# ---------------- IMPORTS ----------------
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from typing import TypedDict, List
import wikipedia

from langchain_community.document_loaders import PyPDFLoader

load_dotenv()

# ---------------- LLM ----------------
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.4
)

# ---------------- STATE ----------------
class ChatState(TypedDict):
    query: str
    history: List[str]
    pdf_context: str
    context: str
    answer: str

# ---------------- PDF LOADER ----------------
def load_pdf(file_path):
    try:
        loader = PyPDFLoader(file_path)
        pages = loader.load()

        text = ""
        for page in pages[:5]:
            text += page.page_content

        return text[:2000]
    except:
        return ""

# ---------------- RETRIEVER ----------------
def retriever_node(state: ChatState) -> ChatState:
    query = state["query"]
    pdf_context = state.get("pdf_context", "")

    wiki_context = ""
    try:
        wiki_context = wikipedia.summary(query, sentences=3)
    except:
        pass

    context = f"""
[Wikipedia]
{wiki_context}

[PDF]
{pdf_context}
"""

    return {"context": context}

# ---------------- CHAT NODE ----------------
def chat_node(state: ChatState) -> ChatState:
    query = state["query"]
    history = "\n".join(state.get("history", []))
    context = state.get("context", "")

    prompt = f"""
You are an advanced AI assistant.

Rules:
- Answer clearly and correctly
- Use simple language
- Give step-by-step explanation when needed
- Use examples if helpful

Chat History:
{history}

External Context:
{context}

User Question:
{query}
"""

    try:
        res = llm.invoke(prompt)
        return {"answer": res.content.strip()}
    except:
        return {"answer": "Error generating response."}

# ---------------- GRAPH ----------------
graph = StateGraph(ChatState)

graph.add_node("retriever", retriever_node)
graph.add_node("chat", chat_node)

graph.add_edge(START, "retriever")
graph.add_edge("retriever", "chat")
graph.add_edge("chat", END)

app = graph.compile()