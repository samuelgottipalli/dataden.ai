# test_complete_system.py
# Comprehensive test to verify all components are working

import asyncio
from agents.enhanced_orchestrator import EnhancedAgentOrchestrator
from mcp_server.database import db
from config.settings import settings
from utils.logging_config import setup_logging
from loguru import logger

setup_logging()

async def test_all_components():
    """
    Test all components of the system
    """
    
    logger.info("="*80)
    logger.info("COMPLETE SYSTEM TEST")
    logger.info("="*80)
    
    results = {
        "database": False,
        "ollama": False,
        "supervisor": False,
        "user_proxy": False,
        "general_assistant": False,
        "data_analysis": False,
        "routing": False
    }
    
    # Test 1: Database Connection
    logger.info("\n[1/7] Testing Database Connection...")
    try:
        test_result = db.execute_query("SELECT 1 as test")
        if test_result["success"]:
            logger.info("✓ Database connection working")
            results["database"] = True
        else:
            logger.error(f"✗ Database error: {test_result['error']}")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
    
    # Test 2: Ollama
    logger.info("\n[2/7] Testing Ollama Connection...")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            has_cloud_model = any("120b-cloud" in m["name"] for m in models)
            if has_cloud_model:
                logger.info("✓ Ollama with gpt-oss:120b-cloud available")
                results["ollama"] = True
            else:
                logger.warning("⚠ gpt-oss:120b-cloud not found, but Ollama is running")
                results["ollama"] = True
        else:
            logger.error("✗ Ollama not responding correctly")
    except Exception as e:
        logger.error(f"✗ Ollama connection failed: {e}")
    
    # Initialize orchestrator for agent tests
    orchestrator = EnhancedAgentOrchestrator()
    
    # Test 3: Supervisor Agent
    logger.info("\n[3/7] Testing Supervisor Agent...")
    try:
        supervisor = await orchestrator.create_supervisor_agent()
        logger.info("✓ Supervisor Agent created successfully")
        results["supervisor"] = True
    except Exception as e:
        logger.error(f"✗ Supervisor Agent failed: {e}")
    
    # Test 4: User Proxy Agent
    logger.info("\n[4/7] Testing User Proxy Agent...")
    try:
        user_proxy = await orchestrator.create_user_proxy_agent()
        logger.info("✓ User Proxy Agent created successfully")
        results["user_proxy"] = True
    except Exception as e:
        logger.error(f"✗ User Proxy Agent failed: {e}")
    
    # Test 5: General Assistant Team
    logger.info("\n[5/7] Testing General Assistant Team...")
    try:
        general_team = await orchestrator.create_general_assistant_team()
        logger.info("✓ General Assistant Team created successfully")
        
        # Quick functionality test
        logger.info("  Testing with: 'What is 10 + 5?'")
        result = await general_team.run("What is 10 + 5?")
        logger.info(f"  Response received: {str(result)[:100]}")
        results["general_assistant"] = True
    except Exception as e:
        logger.error(f"✗ General Assistant Team failed: {e}")
    
    # Test 6: Data Analysis Team
    logger.info("\n[6/7] Testing Data Analysis Team...")
    try:
        data_team = await orchestrator.create_data_analysis_team()
        logger.info("✓ Data Analysis Team created successfully")
        
        # Quick functionality test
        logger.info("  Testing with: 'List database tables'")
        result = await data_team.run("Show me information about the database")
        logger.info(f"  Response received: {str(result)[:100]}")
        results["data_analysis"] = True
    except Exception as e:
        logger.error(f"✗ Data Analysis Team failed: {e}")
    
    # Test 7: Full Routing
    logger.info("\n[7/7] Testing Complete Routing System...")
    try:
        # Test simple math (should route to General Assistant)
        logger.info("  Test: Simple math question")
        result = await orchestrator.execute_task_with_routing(
            "What is 20% of 500?",
            "test_user"
        )
        
        if result["success"]:
            routed_to = result.get("routed_to", "Unknown")
            logger.info(f"  ✓ Routed to: {routed_to}")
            
            if routed_to == "GENERAL_ASSISTANT_TEAM":
                logger.info("  ✓ Correct routing!")
                results["routing"] = True
            else:
                logger.warning(f"  ⚠ Unexpected routing to {routed_to}")
        else:
            logger.error(f"  ✗ Routing failed: {result['error']}")
    except Exception as e:
        logger.error(f"✗ Routing test failed: {e}")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for component, status in results.items():
        icon = "✓" if status else "✗"
        logger.info(f"{icon} {component.replace('_', ' ').title()}: {'PASS' if status else 'FAIL'}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! System is ready to use.")
        return True
    else:
        logger.warning(f"⚠ {total - passed} component(s) failed. Please review errors above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_all_components())
    exit(0 if success else 1)
