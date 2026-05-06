import streamlit as st
from ai_engine import app, load_pdf
import tempfile

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="AI Assistant",
    page_icon="🤖",
    layout="wide"
)

# ---------------- CUSTOM CSS ----------------
st.markdown("""
<style>
.main {
    background-color: #0e1117;
    color: white;
}

.chat-bubble-user {
    background-color: #2563eb;
    padding: 12px;
    border-radius: 12px;
    margin: 8px 0;
    text-align: right;
}

.chat-bubble-ai {
    background-color: #1f2937;
    padding: 12px;
    border-radius: 12px;
    margin: 8px 0;
}

.sidebar .sidebar-content {
    background-color: #111827;
}
</style>
""", unsafe_allow_html=True)

# ---------------- SESSION ----------------
if "history" not in st.session_state:
    st.session_state.history = []

if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

# ---------------- SIDEBAR ----------------
st.sidebar.title("⚙️ Controls")

uploaded_file = st.sidebar.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        pdf_text = load_pdf(tmp.name)
        st.session_state.pdf_text = pdf_text
        st.sidebar.success("PDF Loaded!")

if st.sidebar.button("🧹 Clear Chat"):
    st.session_state.history = []
    st.rerun()

# ---------------- TITLE ----------------
st.title("🤖 Advanced AI Assistant")

# ---------------- DISPLAY CHAT ----------------
for msg in st.session_state.history:
    if msg["role"] == "user":
        st.markdown(f"<div class='chat-bubble-user'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-bubble-ai'>{msg['content']}</div>", unsafe_allow_html=True)

# ---------------- INPUT ----------------
user_input = st.chat_input("Ask anything...")

if user_input:
    # Show user message
    st.session_state.history.append({"role": "user", "content": user_input})

    # Prepare history text
    history_text = [
        f"{msg['role']}: {msg['content']}"
        for msg in st.session_state.history[-6:]
    ]

    # Call AI
    response = app.invoke({
        "query": user_input,
        "history": history_text,
        "pdf_context": st.session_state.pdf_text
    })

    answer = response["answer"]

    # Add AI response
    st.session_state.history.append({"role": "assistant", "content": answer})

    st.rerun()