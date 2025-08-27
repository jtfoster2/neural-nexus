# **🤖 Customer Support Agent (LangGraph + Mistral + Streamlit)**

This project is a **customer support chatbot** powered by:

- LangGraph → for conversation orchestration
- Mistral (via Ollama) → locally hosted LLM
- Streamlit → chat-style web UI

It can be extended with tools, APIs, or knowledge bases (RAG) to answer customer queries about orders, billing, or technical support.

## **🚀 Features**

- Local **Mistral model** (no external API costs).
- **Graph-based agent logic** with LangGraph.
- Clean **chat UI** built with Streamlit.
- Extensible: add FAQ docs, database lookup, or API calls.

## **📦 Installation**

### **1\. Clone Repo**

git clone https://github.com/jtfoster2/neural-nexus  

### **2\. Install Python Dependencies**

pip install -r requirements.txt  

If you don’t have a requirements.txt, use:

pip install langchain langgraph langchain-community streamlit  

### **3\. Install & Run Ollama**

Ollama makes running Mistral locally easy:

curl -fsSL <https://ollama.com/install.sh> | sh  
ollama pull mistral  
ollama run mistral  

Leave Ollama running in the background.

## **▶️ Usage**

### **Run the Streamlit App**

streamlit run app.py  

Open your browser at [http://localhost:8501](http://localhost:8501/).

## **📂 Project Structure**

.  
├── agent.py # LangGraph agent definition  
├── app.py # Streamlit UI  
├── README.md 
└── requirements.txt  

## **🛠️ How It Works**

1. **agent.py** defines a simple LangGraph workflow:
    1. Maintains conversation state (messages)
    2. Calls Mistral through ChatOllama
    3. Returns responses back to the UI
2. **app.py** renders the chat UI:
    1. Keeps history in st.session_state
    2. Uses LangGraph agent to generate replies

## **🔮 Next Steps / Enhancements**

- **Knowledge Base (RAG)** → Connect FAQs, product docs, or a vector DB (like FAISS, Weaviate, or Pinecone).
- **APIs / Tools** → Add CRM or order lookup via LangGraph tool nodes.
- **Conversation Memory** → Store chats in Redis or SQLite.
- **Multi-Agent Routing** → Direct questions to “Billing Bot” vs “Tech Support Bot”.

## **🧪 Example Interaction**

**User:**

Hi, I have an issue with my order.

**Assistant:**

I’m sorry to hear that! Could you share your order number so I can help look it up?

## **⚖️ License**

MIT License – feel free to modify and use.
