from fastmcp import FastMCP
import os
import sys
import json
import logging

# Set up logging to stderr so it does not corrupt the stdio transport channel
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("AgentHiringMCP")

# Create a FastMCP instance
mcp = FastMCP("AgentHiring AI Recruiting MCP Server")

# Add the project root to path so we can import src modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

# Now import the core AgentHiring modules
from src.jd_parser import parse_job_description
from src.honeypot_detector import detect_trap
from src.data_loader import stream_candidates
from src.pipeline import run_ranking_pipeline

# Resolve the candidates data files
CANDIDATES_JSONL = os.path.join(project_root, "data", "candidates.jsonl")
SAMPLE_CANDIDATES_JSON = os.path.join(project_root, "data", "sample_candidates.json")

# Helper class to capture and redirect stdout during tool execution.
# This prevents functions that use print() (like the ranking pipeline) from writing to
# stdout, which would break the JSON-RPC communication of stdio transport.
class StdoutRedirector:
    def __enter__(self):
        self.old_stdout = sys.stdout
        sys.stdout = sys.stderr
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.old_stdout

@mcp.tool()
def parse_job_description_tool(jd_text: str) -> str:
    """
    Parses a raw job description string and returns structured metadata (title, skills, experience, etc.) as a JSON string.
    """
    logger.info("Running parse_job_description_tool")
    try:
        jd_input = {"title": "", "description": jd_text}
        parsed = parse_job_description(jd_input)
        return json.dumps(parsed, indent=2)
    except Exception as e:
        logger.error(f"Error parsing job description: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def rank_candidates_tool(jd_text: str, run_full_dataset: bool = False, top_n: int = 20) -> str:
    """
    Runs the candidate ranking pipeline for the given job description.
    Returns the top candidates as a JSON string containing their ID, rank, score, and reasoning.
    Args:
        jd_text: The job description text.
        run_full_dataset: If True, runs on the full 100K candidates (takes ~30s). If False, runs on the 50-candidate sample for testing.
        top_n: Number of candidates to return.
    """
    logger.info(f"Running rank_candidates_tool (full_dataset={run_full_dataset}, top_n={top_n})")
    try:
        candidates_path = CANDIDATES_JSONL if run_full_dataset else SAMPLE_CANDIDATES_JSON
        
        # Ensure outputs folder exists
        out_dir = os.path.join(project_root, "outputs")
        os.makedirs(out_dir, exist_ok=True)
        out_csv = os.path.join(out_dir, "mcp_ranking_result.csv")
        
        jd_input = {"title": "", "description": jd_text}
        
        with StdoutRedirector():
            results = run_ranking_pipeline(
                candidates_path=candidates_path,
                jd_input=jd_input,
                out_csv_path=out_csv,
                top_n=top_n,
                use_llm=False
            )
        
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
        logger.error(f"Error ranking candidates: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def get_candidate_profile_tool(candidate_id: str) -> str:
    """
    Retrieves the detailed profile information for a specific candidate ID.
    Includes their profile summary, current title, years of experience, skills list, and career history.
    """
    logger.info(f"Running get_candidate_profile_tool for {candidate_id}")
    try:
        from src.data_loader import load_sample_candidates
        # Check both full and sample paths
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
        logger.error(f"Error fetching candidate profile: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def detect_honeypot_trap_tool(candidate_id: str) -> str:
    """
    Runs the Honeypot Trap Detector on a candidate profile.
    Analyzes the profile for keyword stuffing, impossible employment timelines, and template boilerplate.
    """
    logger.info(f"Running detect_honeypot_trap_tool for {candidate_id}")
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
        logger.error(f"Error detecting trap: {e}")
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run(transport="stdio")
