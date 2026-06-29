import os
import sys
import json
import logging

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import the local modules
from src.jd_parser import parse_job_description
from src.honeypot_detector import detect_trap
from src.data_loader import stream_candidates
from src.pipeline import run_ranking_pipeline

# Resolve candidate paths
CANDIDATES_JSONL = os.path.join(project_root, "data", "candidates.jsonl")
SAMPLE_CANDIDATES_JSON = os.path.join(project_root, "data", "sample_candidates.json")

def parse_job_description_tool(jd_text: str) -> str:
    """
    Parses a raw job description string and returns structured metadata (title, skills, experience, etc.) as a JSON string.
    """
    try:
        jd_input = {"title": "", "description": jd_text}
        parsed = parse_job_description(jd_input)
        return json.dumps(parsed, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def rank_candidates_tool(jd_text: str, run_full_dataset: bool = False, top_n: int = 20) -> str:
    """
    Runs the candidate ranking pipeline for the given job description.
    Returns the top candidates as a JSON string containing candidate_id, rank, score, and reasoning.
    Args:
        jd_text: The job description text.
        run_full_dataset: If True, runs on the full 100K candidates (~30s). If False, runs on the 50-candidate sample for testing.
        top_n: Number of candidates to return.
    """
    try:
        candidates_path = CANDIDATES_JSONL if run_full_dataset else SAMPLE_CANDIDATES_JSON
        out_dir = os.path.join(project_root, "outputs")
        os.makedirs(out_dir, exist_ok=True)
        out_csv = os.path.join(out_dir, "agent_ranking_result.csv")
        
        jd_input = {"title": "", "description": jd_text}
        
        # Suppress prints to avoid cluttering agent execution stdout
        old_stdout = sys.stdout
        sys.stdout = sys.stderr
        try:
            results = run_ranking_pipeline(
                candidates_path=candidates_path,
                jd_input=jd_input,
                out_csv_path=out_csv,
                top_n=top_n,
                use_llm=False
            )
        finally:
            sys.stdout = old_stdout
            
        output = []
        for cand in results:
            output.append({
                "candidate_id": cand.get("candidate_id"),
                "rank": cand.get("_rank"),
                "score": round(cand.get("_final_score", 0.0) / 100.0, 4),
                "reasoning": cand.get("_reasoning"),
                "trap_score": cand.get("_trap_score", 0.0),
                "trap_reason": cand.get("_trap_reason", "")
            })
        return json.dumps(output, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_candidate_profile_tool(candidate_id: str) -> str:
    """
    Retrieves the detailed profile information for a specific candidate ID.
    """
    try:
        from src.data_loader import load_sample_candidates
        for path in [SAMPLE_CANDIDATES_JSON, CANDIDATES_JSONL]:
            if not os.path.exists(path):
                continue
            if path.endswith(".jsonl"):
                for cand in stream_candidates(path):
                    if cand.get("candidate_id") == candidate_id:
                        return json.dumps(cand, indent=2)
            else:
                candidates = load_sample_candidates(path)
                for cand in candidates:
                    if cand.get("candidate_id") == candidate_id:
                        return json.dumps(cand, indent=2)
        return json.dumps({"error": f"Candidate {candidate_id} not found."})
    except Exception as e:
        return json.dumps({"error": str(e)})

def detect_honeypot_trap_tool(candidate_id: str) -> str:
    """
    Runs the Honeypot Trap Detector on a candidate profile to check for keyword stuffing, impossible timelines, and boilerplate summaries.
    """
    try:
        profile_str = get_candidate_profile_tool(candidate_id)
        candidate = json.loads(profile_str)
        if "error" in candidate:
            return profile_str
        
        trap_score, trap_reason = detect_trap(candidate)
        return json.dumps({
            "candidate_id": candidate_id,
            "trap_score": trap_score,
            "trap_reason": trap_reason,
            "is_honeypot": trap_score >= 0.4
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# Mock Agent definition for safe offline execution / no API key fallbacks
class MockAgent:
    def __init__(self, name="talentlens_recruiting_concierge", model="gemini-2.5-flash", instruction="", tools=None):
        self.name = name
        self.model = model
        self.instruction = instruction
        self.tools = tools if tools is not None else [
            parse_job_description_tool,
            rank_candidates_tool,
            get_candidate_profile_tool,
            detect_honeypot_trap_tool
        ]

    def run(self, prompt, **kwargs):
        prompt_lower = prompt.lower()
        if "rank" in prompt_lower or "find" in prompt_lower:
            return "Here is the candidate ranking results:\n" + rank_candidates_tool("AI Engineer", run_full_dataset=False, top_n=3)
        elif "profile" in prompt_lower or "details" in prompt_lower:
            import re
            match = re.search(r'cand_\d+', prompt_lower)
            if match:
                cid = match.group(0).upper()
                return get_candidate_profile_tool(cid)
            return "Please specify a candidate ID (e.g., CAND_0000010) to inspect."
        elif "honeypot" in prompt_lower or "trap" in prompt_lower:
            import re
            match = re.search(r'cand_\d+', prompt_lower)
            if match:
                cid = match.group(0).upper()
                return detect_honeypot_trap_tool(cid)
            return "Please specify a candidate ID (e.g., CAND_0000002) to audit."
        return f"[Concierge Mock Agent] I parsed your query: '{prompt}'. (To use live LLM reasoning, please configure GEMINI_API_KEY in your .env file)."

def get_recruiting_agent():
    # Load env variables to ensure GEMINI_API_KEY is resolved
    from dotenv import load_dotenv
    load_dotenv()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    fallback_key = os.environ.get("api_key")
    
    # Verify if a genuine Gemini key is available (Gemini keys start with AIzaSy; Groq keys start with gsk_)
    is_gemini = (gemini_key and len(gemini_key) > 5 and not gemini_key.startswith("gsk_")) or (fallback_key and fallback_key.startswith("AIzaSy"))
    
    if not is_gemini:
        return MockAgent()
        
    # Propagate fallback key if it is Gemini-compliant
    if fallback_key and fallback_key.startswith("AIzaSy") and not gemini_key:
        os.environ["GEMINI_API_KEY"] = fallback_key

    # Try to import Google ADK classes
    try:
        from google.adk.agents import Agent
    except ImportError:
        try:
            from google.adk import Agent
        except ImportError:
            return MockAgent()

    try:
        agent = Agent(
            name="talentlens_recruiting_concierge",
            model="gemini-2.5-flash",
            instruction=(
                "You are a helpful and professional Recruiting Concierge Agent for AgentHiring.\n"
                "Your goal is to assist recruiters in finding, ranking, and auditing candidates for job positions.\n"
                "You have access to candidate ranking, detailed profile lookups, and honeypot detection tools.\n"
                "When asked to analyze or rank candidates, always call the appropriate tools.\n"
                "When analyzing a candidate's profile, always run the honeypot detection tool to verify the candidate's integrity.\n"
                "Present your analysis clearly and cite candidate data, skills, and experience where appropriate."
            ),
            tools=[
                parse_job_description_tool,
                rank_candidates_tool,
                get_candidate_profile_tool,
                detect_honeypot_trap_tool
            ]
        )
        return agent
    except Exception:
        return MockAgent()

def run_agent(prompt: str) -> str:
    agent = get_recruiting_agent()
    
    if isinstance(agent, MockAgent):
        return agent.run(prompt)
        
    # Real Google ADK Agent execution using InMemoryRunner
    import asyncio
    from google.adk.runners import InMemoryRunner
    
    runner = InMemoryRunner(agent=agent)
    
    async def _run():
        try:
            response = await runner.run_debug(prompt)
            return response
        except Exception as e:
            return f"Error executing ADK agent: {e}"
            
    return asyncio.run(_run())


