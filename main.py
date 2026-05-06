# ---------------- IMPORTS ----------------
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from typing import TypedDict, List, Optional
from pydantic import BaseModel
import wikipedia
import json
import os
from datetime import datetime

# PDF loader
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# ---------------- LLM ----------------
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.3
)

# ================================================================
# HISTORY MANAGEMENT
# ================================================================
HISTORY_FILE = "blog_history.json"

def load_all_history() -> List[dict]:
    """Load all saved blog sessions from disk."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_session_to_history(title: str, tone: str, length: str, final_blog: str) -> str:
    """Save a completed blog session to history. Returns the session ID."""
    history = load_all_history()
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = {
        "id": session_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": title,
        "tone": tone,
        "length": length,
        "blog": final_blog,
        "word_count": len(final_blog.split()),
    }
    history.append(session)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    return session_id

def delete_session(session_id: str):
    """Delete a specific session by ID."""
    history = load_all_history()
    history = [s for s in history if s["id"] != session_id]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def clear_all_history():
    """Wipe all saved history."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

# ================================================================
# STATE
# ================================================================
class BlogState(TypedDict):
    title: str
    tone: str
    length: str
    context: str
    pdf_context: str
    sections: List[str]
    contents: List[dict]
    intro: str
    conclusion: str
    final_blog: str
    # ---- new fields ----
    section_count: int          # how many sections to generate
    language: str               # output language
    conversation_history: List[dict]   # [{role, content, timestamp}]

# ================================================================
# HELPERS
# ================================================================
def length_guidelines(length: str) -> str:
    if length == "Short":
        return "Keep it concise (3-5 lines per section)."
    elif length == "Medium":
        return "Moderate detail (6-10 lines per section)."
    else:
        return "Detailed explanation (10-15 lines per section)."

def build_history_context(history: List[dict], max_turns: int = 4) -> str:
    """Flatten the last N turns of conversation history for LLM context."""
    if not history:
        return ""
    recent = history[-max_turns:]
    lines = [
        f"{m.get('role','user').capitalize()}: {str(m.get('content',''))[:300]}"
        for m in recent
    ]
    return "\n".join(lines)

# ================================================================
# PDF LOADER  (chunked, not raw slice)
# ================================================================
def load_pdf(file_path: str) -> str:
    try:
        loader = PyPDFLoader(file_path)
        pages = loader.load()
        raw = "\n".join(p.page_content for p in pages[:10])
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_text(raw)
        result, budget = "", 2000
        for chunk in chunks:
            if len(result) + len(chunk) > budget:
                break
            result += chunk + "\n"
        return result.strip()
    except Exception:
        return ""

# ================================================================
# STRUCTURED OUTPUT
# ================================================================
class PlannerOutput(BaseModel):
    sections: List[str]

planner_llm = llm.with_structured_output(PlannerOutput)

# ================================================================
# NODES
# ================================================================

def retriever_node(state: BlogState) -> dict:
    topic = state["title"]
    pdf_context = state.get("pdf_context", "")
    history_ctx = build_history_context(state.get("conversation_history", []))

    wiki_context = ""
    try:
        wiki_context = wikipedia.summary(topic, sentences=5)
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            wiki_context = wikipedia.summary(e.options[0], sentences=5)
        except Exception:
            wiki_context = ""
    except wikipedia.exceptions.PageError:
        wiki_context = f"No Wikipedia page found for '{topic}'."
    except Exception:
        wiki_context = ""

    final_context = (
        f"Wikipedia Context:\n{wiki_context}\n\n"
        f"PDF Context:\n{pdf_context}\n\n"
        f"Previous Conversation:\n{history_ctx}"
    ).strip()

    return {"context": final_context}


def planner_node(state: BlogState) -> dict:
    n = state.get("section_count", 5)
    try:
        res = planner_llm.invoke(
            f"Generate exactly {n} UNIQUE, creative section headings for a blog post titled: \"{state['title']}\"\n"
            f"Tone: {state['tone']}\n"
            f"Make them specific, engaging, and progressive. Avoid 'Introduction' or 'Conclusion'."
        )
        return {"sections": res.sections[:n]}
    except Exception:
        return {"sections": ["Overview", "Core Concepts", "Real-World Applications", "Challenges & Solutions", "Future Outlook"][:n]}


def intro_node(state: BlogState) -> dict:
    lang = state.get("language", "English")
    history_ctx = build_history_context(state.get("conversation_history", []))
    try:
        res = llm.invoke(
            f"Write an engaging 2-3 paragraph introduction for a blog post titled: \"{state['title']}\"\n\n"
            f"Context:\n{state['context']}\n\n"
            f"{'Previous context:\n' + history_ctx if history_ctx else ''}\n"
            f"Tone: {state['tone']}. Language: {lang}.\n"
            f"Hook the reader immediately."
        )
        intro = res.content.strip()
    except Exception as e:
        intro = f"Introduction could not be generated. ({e})"

    updated_history = state.get("conversation_history", []) + [{
        "role": "assistant",
        "content": f"[Intro written for: {state['title']}]",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }]
    return {"intro": intro, "conversation_history": updated_history}


def write_single_section(title, sec, tone, length, context, language="English") -> dict:
    guideline = length_guidelines(length)
    try:
        res = llm.invoke(
            f"Write a blog section.\n\n"
            f"Blog Title: {title}\nSection: {sec}\n\n"
            f"Context:\n{context}\n\n"
            f"Tone: {tone}. Length: {guideline}. Language: {language}.\n\n"
            f"Structure:\n- Clear explanation\n- 2-3 key points\n- Concrete example\n"
            f"Do NOT repeat the heading."
        )
        return {"heading": sec, "content": res.content.strip()}
    except Exception as e:
        return {"heading": sec, "content": f"Section error: {e}"}


def writer_node(state: BlogState) -> dict:
    lang = state.get("language", "English")
    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(
            lambda sec: write_single_section(
                state["title"], sec, state["tone"], state["length"], state["context"], lang
            ),
            state["sections"]
        ))
    return {"contents": results}


def conclusion_node(state: BlogState) -> dict:
    lang = state.get("language", "English")
    try:
        res = llm.invoke(
            f"Write a compelling conclusion for: \"{state['title']}\"\n\n"
            f"Context:\n{state['context']}\n\n"
            f"Tone: {state['tone']}. Language: {lang}.\n"
            f"Include: key takeaways, a thought-provoking closing line, and a call to action."
        )
        return {"conclusion": res.content.strip()}
    except Exception as e:
        return {"conclusion": f"Conclusion error: {e}"}


def combiner_node(state: BlogState) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    blog = f"# {state['title']}\n\n"
    blog += f"*Tone: {state['tone']} · Length: {state['length']} · {now}*\n\n---\n\n"
    blog += f"{state['intro']}\n\n"
    for sec in state["contents"]:
        blog += f"## {sec['heading']}\n\n{sec['content']}\n\n"
    blog += f"## Conclusion\n\n{state['conclusion']}\n"

    # ---- persist to history ----
    save_session_to_history(
        title=state["title"],
        tone=state["tone"],
        length=state["length"],
        final_blog=blog,
    )

    updated_history = state.get("conversation_history", []) + [{
        "role": "assistant",
        "content": f"Blog '{state['title']}' generated ({len(blog.split())} words).",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }]
    return {"final_blog": blog, "conversation_history": updated_history}


# ================================================================
# GRAPH
# ================================================================
graph = StateGraph(BlogState)

graph.add_node("planner",    planner_node)
graph.add_node("retriever",  retriever_node)
graph.add_node("intro",      intro_node)
graph.add_node("writer",     writer_node)
graph.add_node("conclusion", conclusion_node)
graph.add_node("combiner",   combiner_node)

graph.add_edge(START,        "planner")
graph.add_edge("planner",    "retriever")
graph.add_edge("retriever",  "intro")
graph.add_edge("intro",      "writer")
graph.add_edge("writer",     "conclusion")
graph.add_edge("conclusion", "combiner")
graph.add_edge("combiner",   END)

app = graph.compile()