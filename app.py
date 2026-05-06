import streamlit as st
import time
import re
import tempfile
from main import app, load_pdf

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="AI Blog Generator",
    layout="wide",
    page_icon="📝"
)

# ---------------- SESSION STATE ----------------
if "history" not in st.session_state:
    st.session_state.history = []

# ---------------- CUSTOM CSS ----------------
st.markdown("""
<style>
.main { background-color: #0e1117; }
h1, h2, h3 { color: #ffffff; }
.stTextInput input { background-color: #262730; color: white; }
.stSelectbox div { background-color: #262730; color: white; }
.block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------
st.markdown("<h1>📝 AI Blog Writing Agent</h1>", unsafe_allow_html=True)
st.caption("AI • RAG • Parallel • Streaming • History")

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown("## ⚙️ Controls")

    tone = st.selectbox("🎨 Tone", ["Simple", "Professional", "Creative"])
    length = st.selectbox("📏 Length", ["Short", "Medium", "Long"])

    # 🔥 NEW: Section count
    section_count = st.slider("📚 Sections", 3, 10, 5)

    # 🔥 NEW: Language
    language = st.selectbox("🌐 Language", ["English", "Hindi"])

    # PDF Upload
    st.markdown("---")
    st.markdown("## 📄 Upload Document")
    uploaded_file = st.file_uploader("Upload PDF (optional)", type=["pdf"])

    st.markdown("---")
    st.markdown("### 💡 Tips")
    st.write("• Upload PDF for better accuracy")
    st.write("• Increase sections for detailed blogs")

# ---------------- MAIN INPUT ----------------
st.markdown("### ✍️ Enter Blog Topic")

title = st.text_input("Topic", placeholder="e.g. AI in Healthcare")

generate = st.button("🚀 Generate Blog", use_container_width=True)

# ---------------- GENERATION ----------------
if generate:

    if title.strip() == "":
        st.warning("⚠️ Please enter a topic")

    else:
        # ---------------- PDF HANDLING ----------------
        pdf_text = ""
        if uploaded_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.read())
                pdf_text = load_pdf(tmp.name)

        # ---------------- LAYOUT ----------------
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### 📄 Generated Blog")
            placeholder = st.empty()

        with col2:
            st.markdown("### ⚡ Status")
            status_box = st.empty()
            progress = st.progress(0)

        final_text = ""
        current_step = ""

        with st.spinner("Generating blog..."):

            try:
                for chunk in app.stream(
                    {
                        "title": title,
                        "tone": tone,
                        "length": length,
                        "pdf_context": pdf_text,
                        "section_count": section_count,      # ✅ NEW
                        "language": language,                # ✅ NEW
                        "conversation_history": st.session_state.history  # ✅ NEW
                    },
                    stream_mode="values"
                ):

                    # ---------------- STATUS ----------------
                    if "sections" in chunk and current_step != "planner":
                        current_step = "planner"
                        status_box.info("📌 Planning structure...")
                        progress.progress(20)

                    elif "intro" in chunk and current_step != "intro":
                        current_step = "intro"
                        status_box.info("✍️ Writing intro...")
                        progress.progress(40)

                    elif "contents" in chunk and current_step != "writer":
                        current_step = "writer"
                        status_box.info("⚡ Generating sections...")
                        progress.progress(70)

                    elif "conclusion" in chunk and current_step != "conclusion":
                        current_step = "conclusion"
                        status_box.info("🧾 Finalizing...")
                        progress.progress(90)

                    # ---------------- FINAL OUTPUT ----------------
                    if "final_blog" in chunk:
                        blog = chunk["final_blog"]

                        # streaming effect
                        tokens = re.split(r'(\s+)', blog)
                        temp = ""

                        for token in tokens:
                            temp += token
                            placeholder.markdown(temp)
                            time.sleep(0.003)

                        final_text = temp
                        progress.progress(100)

                        # ✅ SAVE TO SESSION HISTORY
                        st.session_state.history.append({
                            "role": "user",
                            "content": title
                        })
                        st.session_state.history.append({
                            "role": "assistant",
                            "content": blog
                        })

                status_box.success("✅ Blog Ready!")

            except Exception as e:
                status_box.error("❌ Error occurred")
                st.error(str(e))

        # ---------------- DOWNLOAD ----------------
        if final_text:
            st.download_button(
                label="📥 Download Blog",
                data=final_text,
                file_name="blog.md",
                mime="text/markdown",
                use_container_width=True
            )

# ---------------- HISTORY VIEW ----------------
st.markdown("---")
st.markdown("### 🕘 Recent Conversations")

if st.session_state.history:
    for item in reversed(st.session_state.history[-6:]):
        st.write(f"**{item['role'].capitalize()}**: {item['content'][:100]}...")