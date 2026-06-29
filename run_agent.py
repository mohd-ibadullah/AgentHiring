import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure src is in python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "src"))

from src.agent import get_recruiting_agent

def main():
    parser = argparse.ArgumentParser(description="AgentHiring Recruiting Agent CLI")
    parser.add_argument("--prompt", type=str, help="Query for the recruiting agent")
    args = parser.parse_args()
    
    agent = get_recruiting_agent()
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("api_key")
    if not api_key:
        print("[!] Warning: GEMINI_API_KEY or api_key environment variables not found.")
        print("[!] The agent will run in local rule-based mock mode for demonstration.")
        print("[!] To run the live agent, please configure GEMINI_API_KEY in your .env file.")
        print("-" * 60)
        
    if args.prompt:
        print(f"User: {args.prompt}")
        print("Agent running...")
        try:
            response = agent.run(args.prompt)
            print(f"Agent:\n{response}")
        except Exception as e:
            print(f"Error executing agent: {e}")
    else:
        print(f"=== Welcome to the AgentHiring Recruiting Agent CLI ===")
        print("Type your request (e.g., 'rank candidates', 'check honeypot for CAND_0000002') or 'quit' to exit.")
        print("-" * 60)
        while True:
            try:
                prompt = input("\nYou: ")
                if prompt.strip().lower() in ["quit", "exit"]:
                    break
                if not prompt.strip():
                    continue
                print("Agent running...")
                response = agent.run(prompt)
                print(f"\nAgent:\n{response}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    main()
