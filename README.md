# 🤖 Agentic Gemini App

This project is a **multi-tool AI agent** built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) for agent workflows
- [LangChain](https://www.langchain.com/) for LLM abstraction
- [Google Gemini](https://ai.google.dev/) as the LLM backend
- [Streamlit](https://streamlit.io/) for a simple chat UI

---

This project uses **SQLite** to store order and shipping data.
   ```bash
   sqlite agentic_ai.db
   sqlite> .tables
   sqlite> SELECT * FROM table_name;
   ```

## 🚀 Features
- Uses **Google Gemini** (`gemini-2.5-flash`) as the reasoning model.
- Multi-tool agent with:

  #### FOR FUTURE EXPANSION####

- Built with **LangGraph** → structured workflows with planner → tool executor → finalizer.
- **Streamlit chat app** with session memory.
- Environment variables managed via `.env`.

---

## 📦 Installation

Clone the repo and install dependencies:

```bash
git clone https://github.com/jtfoster2/neural-nexus
cd neural-nexus
pip install -r requirements.txt
```

---

## 🔑 Setup

1. Create a Gemini API key at https://aistudio.google.com/apikey
2. Create a SendGrid API key at https://sendgrid.com/en-us/solutions/email-api
3. Create a Vonage API key at https://www.vonage.com/log-in/
4. Create a `.env` file in the root of the project:
   ```env
   GOOGLE_API_KEY="your_api_key_here"
   SENDGRID_API_KEY="your_api_key_here"
   SENDGRID_VERIFIED_SENDER="your_api_key_here"
   SENDER_EMAI="email_send_from"
   VONAGE_API_KEY="your_api_key_here"
   VONAGE_API_SECRET="your_api_secret_key_here"
   VONAGE_SMS_FROM="phoneNumber_send_from"        #format e.g. (16785559999)
   ```

5. Make sure your Gemini API key is active in [Google AI Studio](https://makersuite.google.com/).

---

## 💬 Run the Streamlit Chat App

Launch the chat UI:

```bash
streamlit run app.py
```

Then open the link in your browser (default: [http://localhost:8501](http://localhost:8501)).

---

## 🧩 Project Structure

```
.
├── agent.py       # LangGraph workflow (planner, tools, finalizer)
├── app.py         # Streamlit UI
├── requirements.txt
├── db.py          # Database (SQLite)
└── .env           # Environment variables (Google API key)

```

---

## Documentation and Demo
**Mid-Demo** can be found at https://youtu.be/ygy_AnI0ntE





