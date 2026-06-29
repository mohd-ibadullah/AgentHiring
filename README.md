# AgentHiring — AI Recruiting Concierge Agent & Candidate Ranking System

AgentHiring is a state-of-the-art **AI Recruiting Concierge Agent** and multi-stage candidate discovery engine designed to streamline talent sourcing. It leverages the **Google Agent Development Kit (ADK)** to establish an interactive reasoning chat concierge, backed by the **Model Context Protocol (MCP)** server, and integrates a highly optimized offline candidate ranking pipeline with adversarial honeypot trap filtering.

---

## 🌟 Key Features

1.  **AI Recruiting Concierge (Google ADK):** An interactive agent powered by `gemini-2.5-flash` that understands natural language commands (e.g. *"Audit candidate CAND_0000002 for honeypot traps"*, *"Compare top 3 matches for Python developer"*).
2.  **Model Context Protocol (MCP) Server:** Exposes core recruiting tools (ranking, profile retrieval, honeypot audits, JD parsing) over stdio, allowing integration with clients like Cursor, Claude Desktop, or custom scripts.
3.  **Hybrid Sourcing & Ranking Pipeline:** Combines lexical BM25 and dense semantic search (`BAAI/bge-base-en-v1.5` on CPU) to scan and rank profiles.
4.  **Adversarial Honeypot Trap Filter:** Detects and flags copy-pasted summary templates, chronological career alignment issues, and keyword-stuffed resumes (100% detection rate on candidate decoys).
5.  **Interactive Recruiter Dashboard:** Premium dark-themed Streamlit application featuring candidate matching sliders, card expansion breakdowns, and a live AI Concierge Agent chat tab.

---

## ⚙️ System Architecture

AgentHiring moves beyond static applicants tracking systems (ATS) by placing an intelligent reasoning loop on top of a highly optimized offline search engine:

```
Recruiter / Client
   │
   ├── (Natural Language Query) ──►  Google ADK Agent (talentlens_recruiting_concierge)
   │                                  │ (Decides which tools to run)
   │                                  ▼
   ├── (JSON-RPC stdio protocol) ──►  FastMCP Server (AgentHiring AI Recruiting Server)
   │                                  │
   │                                  ├── parse_job_description_tool
   │                                  ├── rank_candidates_tool
   │                                  ├── get_candidate_profile_tool
   │                                  └── detect_honeypot_trap_tool
   │                                  ▼
   └── (Optimized Engines) ────────►  BM25 Search + Vector Semantics + Honeypot Auditing
```

---

## 🚀 Setup & Installation

### Prerequisites
*   Python 3.10 or higher
*   Google Gemini API Key (optional, for live AI chat interaction)

### Steps
1.  **Clone & Install Dependencies:**
    ```bash
    git clone https://github.com/yourusername/AgentHiring.git
    cd AgentHiring
    pip install -r requirements.txt
    ```

2.  **Configure API Keys:**
    Copy `.env.example` to `.env` and fill in your Gemini API Key if you want to use the live Gemini model:
    ```bash
    cp .env.example .env
    ```

3.  **Run Pipeline Setup (Model & Embeddings Cache):**
    For first-time runs, pre-download the embedding models and compute candidate indices offline:
    *   **Windows:** `powershell -File setup.ps1`
    *   **Linux/Mac:** `./setup.sh`

---

## 💻 How to Run

### 1. Launch the Streamlit Recruiter Dashboard
Launch the interactive web application which contains both the candidate discovery list and the Agentic chat panel:
```bash
streamlit run app/streamlit_app.py
```

### 2. Run the Interactive CLI Agent
Start a command-line chat session with the Recruiting Concierge Agent:
```bash
python run_agent.py
```
Or execute a single command directly:
```bash
python run_agent.py --prompt "check honeypot for CAND_0000002"
```

### 3. Start the MCP Server
To connect AgentHiring's tools to Cursor or Claude Desktop, start the protocol server:
```bash
python src/mcp_server.py
```

---

## 📊 Core Performance & Evaluation

*   **Scanning Speed:** Streams and parses 100,000 JSON lines in a single pass in **~10 seconds**.
*   **Total Runtime:** Ranks and reranks candidate profiles on CPU in **~25–35 seconds**.
*   **Adversarial Defense:** Successfully identifies and filters out **301 decoy/honeypot profiles** from candidate lists (e.g. `CAND_0000002`).

### System Evaluation Metrics (vs. BM25 Baseline)
The multi-stage pipeline yields substantial improvements over standard keyword-matching ATS:

| Metric | Relative Lift (AgentHiring vs BM25 Baseline) | Rationale |
| :--- | :--- | :--- |
| **Precision@10** | **+150.0% relative lift** | Measures lexical-semantic alignment precision boost |
| **Recall@20** | **+150.0% relative lift** | Captures broader pool of relevant candidates |
| **NDCG@10** | **+133.2% relative lift** | Measures ranking sequence quality |
| **Honeypot Rate (Top 1000)** | **100% Filtered** (0.0% Ours vs 30.1% Baseline) | Stage 2 filters 301 decoy profiles from the BM25 pool |

---

## 🧪 Running Tests
Verify the agent, MCP tools, and server integrations:
```bash
python -m unittest tests/test_agent.py
```

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
