# ============================================================
# COMPLETE WORKING SYSTEM - FINAL INTEGRATION
# All features working together with database, tools, and safety
# ============================================================

# run_complete_system.py
# Main entry point for the complete system

import asyncio
from agents.enhanced_orchestrator import EnhancedAgentOrchestrator
from utils.logging_config import setup_logging
from loguru import logger
import sys

setup_logging()

async def interactive_mode():
    """
    Interactive mode - user can type questions and get responses
    """
    
    logger.info("="*80)
    logger.info("MULTI-AGENT DATA ANALYSIS SYSTEM")
    logger.info("="*80)
    logger.info("Features:")
    logger.info("  ✓ Automatic task routing (Supervisor Agent)")
    logger.info("  ✓ Safety checks (User Proxy Agent)")
    logger.info("  ✓ Data analysis (SQL + Analysis + Validation)")
    logger.info("  ✓ Simple tasks (Math, conversions, general knowledge)")
    logger.info("="*80)
    logger.info("\nType your questions below (or 'exit' to quit)")
    logger.info("Examples:")
    logger.info("  - 'What's 15% of 850?'")
    logger.info("  - 'Show me the first 5 tables in the database'")
    logger.info("  - 'Analyze sales by region for Q4 2024'")
    logger.info("  - 'Convert 100 Fahrenheit to Celsius'")
    logger.info("="*80)
    print()
    
    orchestrator = EnhancedAgentOrchestrator()
    
    while True:
        try:
            # Get user input
            user_input = input("\n🤔 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                logger.info("Goodbye! 👋")
                break
            
            # Process the request
            print("\n⏳ Processing...\n")
            
            result = await orchestrator.execute_task_with_routing(
                task_description=user_input,
                username="interactive_user"
            )
            
            # Display results
            if result["success"]:
                print("\n" + "="*80)
                print("🤖 Response:")
                print("="*80)
                
                # Show classification
                if "classification" in result:
                    print(f"\n📋 Routed to: {result.get('routed_to', 'Unknown')}")
                
                # Show result
                print(f"\n{result['result']}")
                
                print("\n" + "="*80)
            else:
                print("\n" + "="*80)
                print("❌ Error:")
                print("="*80)
                print(f"{result['error']}")
                print("="*80)
        
        except KeyboardInterrupt:
            logger.info("\n\nGoodbye! 👋")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\n❌ Error: {e}\n")

async def demo_mode():
    """
    Demo mode - runs predefined scenarios to showcase all features
    """
    
    logger.info("="*80)
    logger.info("DEMO MODE - SHOWCASING ALL FEATURES")
    logger.info("="*80)
    
    orchestrator = EnhancedAgentOrchestrator()
    
    demo_scenarios = [
        {
            "name": "Simple Math (General Assistant)",
            "task": "What is 25% of 400?",
            "expected": "General Assistant calculates: 100"
        },
        {
            "name": "Unit Conversion (General Assistant)",
            "task": "Convert 100 Fahrenheit to Celsius",
            "expected": "General Assistant converts: 37.78°C"
        },
        {
            "name": "General Knowledge (General Assistant)",
            "task": "What is the capital of France?",
            "expected": "General Assistant answers: Paris"
        },
        {
            "name": "Database Tables (Data Analysis Team)",
            "task": "Show me the first 5 tables in the database",
            "expected": "SQL Agent queries system tables, returns list"
        },
        {
            "name": "Sales Analysis (Data Analysis Team)",
            "task": "Show total sales from the FactInternetSales table",
            "expected": "SQL Agent queries sales, Analysis Agent provides insights"
        }
    ]
    
    for i, scenario in enumerate(demo_scenarios, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"DEMO {i}/{len(demo_scenarios)}: {scenario['name']}")
        logger.info(f"{'='*80}")
        logger.info(f"Task: {scenario['task']}")
        logger.info(f"Expected: {scenario['expected']}")
        logger.info(f"{'-'*80}\n")
        
        result = await orchestrator.execute_task_with_routing(
            task_description=scenario['task'],
            username="demo_user"
        )
        
        if result["success"]:
            logger.info(f"✓ SUCCESS")
            logger.info(f"Routed to: {result.get('routed_to', 'Unknown')}")
            print(f"\nResult:\n{result['result']}\n")
        else:
            logger.error(f"✗ FAILED: {result['error']}")
        
        # Pause between demos
        await asyncio.sleep(3)
    
    logger.info(f"\n{'='*80}")
    logger.info("DEMO COMPLETE")
    logger.info(f"{'='*80}")

async def single_query_mode(query: str):
    """
    Single query mode - execute one query and exit
    Useful for API integration or testing
    """
    
    logger.info(f"Executing query: {query}")
    
    orchestrator = EnhancedAgentOrchestrator()
    
    result = await orchestrator.execute_task_with_routing(
        task_description=query,
        username="api_user"
    )
    
    if result["success"]:
        print(result['result'])
        return 0
    else:
        print(f"Error: {result['error']}")
        return 1

def main():
    """Main entry point with mode selection"""
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == "demo":
            # Demo mode
            asyncio.run(demo_mode())
        
        elif mode == "query":
            # Single query mode
            if len(sys.argv) < 3:
                print("Usage: python run_complete_system.py query 'Your question here'")
                sys.exit(1)
            query = " ".join(sys.argv[2:])
            exit_code = asyncio.run(single_query_mode(query))
            sys.exit(exit_code)
        
        elif mode == "help":
            print("Multi-Agent Data Analysis System")
            print("\nUsage:")
            print("  python run_complete_system.py              # Interactive mode (default)")
            print("  python run_complete_system.py demo         # Demo mode (showcases features)")
            print("  python run_complete_system.py query 'Q'    # Single query mode")
            print("  python run_complete_system.py help         # Show this help")
            sys.exit(0)
        
        else:
            print(f"Unknown mode: {mode}")
            print("Run 'python run_complete_system.py help' for usage")
            sys.exit(1)
    
    else:
        # Default: Interactive mode
        asyncio.run(interactive_mode())

if __name__ == "__main__":
    main()
