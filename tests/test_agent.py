import os
import sys
import unittest

# Ensure src is in python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "src"))

from src.agent import get_recruiting_agent, run_agent
from src.mcp_server import mcp

class TestRecruitingAgent(unittest.TestCase):
    def setUp(self):
        self.agent = get_recruiting_agent()

    def test_agent_initialization(self):
        """Verify that the ADK Agent instantiates with correct name, model and tools."""
        self.assertEqual(self.agent.name, "talentlens_recruiting_concierge")
        self.assertEqual(self.agent.model, "gemini-2.5-flash")
        self.assertTrue(len(self.agent.tools) >= 4)

    def test_mcp_server_initialization(self):
        """Verify that the FastMCP server is initialized and contains the registered tools."""
        import asyncio
        self.assertEqual(mcp.name, "AgentHiring AI Recruiting MCP Server")
        tools = asyncio.run(mcp.list_tools())
        tool_names = [t.name for t in tools]
        self.assertIn("parse_job_description_tool", tool_names)
        self.assertIn("rank_candidates_tool", tool_names)
        self.assertIn("get_candidate_profile_tool", tool_names)
        self.assertIn("detect_honeypot_trap_tool", tool_names)

    def test_agent_mock_execution(self):
        """Verify agent handles mock queries when GEMINI_API_KEY is not defined."""
        result = run_agent("Is CAND_0000002 a honeypot?")
        self.assertIsNotNone(result)
        self.assertIn("CAND_0000002", result)
        print("\nTest execution output:")
        print(result)

if __name__ == "__main__":
    unittest.main()
