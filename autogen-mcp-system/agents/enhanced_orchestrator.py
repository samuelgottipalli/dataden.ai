# ============================================================
# COMPLETE WORKING VERSION - Enhanced Orchestrator
# All features from November 15 working session
# ============================================================

import asyncio
from typing import Optional, Dict, List
from loguru import logger
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.messages import TextMessage
from config.settings import settings
from mcp_server.tools import generate_and_execute_sql, analyze_data_pandas
from mcp_server.database import db
import re
import json
from datetime import datetime

class EnhancedAgentOrchestrator:
    """
    COMPLETE working orchestrator with all features:
    1. Message filtering (clean responses)
    2. Database-aware SQL agent
    3. Two-tier sophisticated routing
    4. Max turns = 10 (prevents loops)
    5. Proper streaming
    """

    def __init__(self):
        self.model_client = OllamaChatCompletionClient(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.7,  # Good balance for creativity and consistency
            max_tokens=2000,
            model_info=settings.ollama_model_info,
        )

        logger.info(f"✨ Enhanced Orchestrator initialized with model: {settings.ollama_model}")

    # ============================================================
    # MESSAGE FILTERING - Removes TextMessage junk
    # ============================================================

    def _extract_clean_content(self, result) -> str:
        """
        Extract clean, user-friendly content from raw agent messages
        
        This is the KEY to clean responses - filters out ALL internal junk
        """
        
        if isinstance(result, str):
            # Check if it has TextMessage wrappers
            if "TextMessage(" not in result:
                return result
            
            # Extract content from TextMessage format using regex
            pattern = r"content='([^']+(?:''[^']+)*?)'"
            matches = re.findall(pattern, result)
            
            if matches:
                # Get the LAST match (usually the final answer)
                last_content = matches[-1]
                # Clean up escaped quotes
                last_content = last_content.replace("''", "'")
                
                # If still too technical, try to extract just the answer
                if len(last_content) > 1000:
                    # Look for actual answer after planning
                    answer_patterns = [
                        r"(?:Final answer|Result|Answer):\s*(.+?)(?:TextMessage|$)",
                        r"(?:Here(?:'s| is) the (?:result|answer)):\s*(.+?)(?:TextMessage|$)",
                    ]
                    for pattern in answer_patterns:
                        answer_match = re.search(pattern, last_content, re.IGNORECASE | re.DOTALL)
                        if answer_match:
                            return answer_match.group(1).strip()
                
                return last_content
        
        # Handle object with messages attribute
        if hasattr(result, 'messages'):
            messages = result.messages
            if messages:
                # Get last message
                last_message = messages[-1]
                if hasattr(last_message, 'content'):
                    content = last_message.content
                    # Recursively clean if needed
                    if isinstance(content, str) and "TextMessage(" in content:
                        return self._extract_clean_content(content)
                    return str(content)
        
        # Fallback
        return str(result)

    def _should_show_message(self, source: str, content: str) -> bool:
        """
        Determine if a message should be shown to user
        
        Filters out internal orchestrator planning messages
        """
        
        # Skip internal orchestrator planning
        if source == "MagenticOneOrchestrator":
            # Only show if it's a final answer
            if any(phrase in content.lower() for phrase in ["final", "answer", "result", "here is"]):
                return True
            return False
        
        # Skip empty or very short messages
        if not content or len(content.strip()) < 5:
            return False
        
        # Skip technical metadata messages
        if any(keyword in content.lower() for keyword in ["textmessage(", "models_usage", "metadata={}"]):
            return False
        
        # Show everything else
        return True

    # ============================================================
    # SUPERVISOR AGENT - Simple routing
    # ============================================================

    async def create_supervisor_agent(self) -> AssistantAgent:
        """Supervisor Agent: Routes tasks to teams"""

        supervisor = AssistantAgent(
            name="SupervisorAgent",
            model_client=self.model_client,
            system_message="""You are a task router. Respond with ONLY the team name.

**Rules:**

1. **DATA_ANALYSIS_TEAM** - For database, SQL, data analysis
2. **GENERAL_ASSISTANT_TEAM** - For math, knowledge, conversions

Respond with ONE of:
- DATA_ANALYSIS_TEAM
- GENERAL_ASSISTANT_TEAM

No explanations.""",
        )

        return supervisor

    # ============================================================
    # GENERAL ASSISTANT TEAM
    # ============================================================

    async def create_general_assistant_team(self) -> MagenticOneGroupChat:
        """General Assistant for simple tasks"""

        general_agent = AssistantAgent(
            name="GeneralAssistant",
            model_client=self.model_client,
            system_message="""You are a helpful assistant.

Handle:
- Math calculations
- Unit conversions
- General knowledge
- Simple questions

Be concise and direct. Provide the answer clearly.""",
        )

        team = MagenticOneGroupChat(
            participants=[general_agent],
            model_client=self.model_client,
            max_turns=5,  # Simple tasks don't need many turns
        )

        return team

    # ============================================================
    # DATA ANALYSIS TEAM - Database-aware with max_turns=10
    # ============================================================

    async def create_data_analysis_team(self) -> MagenticOneGroupChat:
        """Data Analysis Team with DATABASE-AWARE SQL agent"""

        # Tool wrappers
        async def sql_tool_wrapper(query_description: str, sql_script: str) -> dict:
            logger.info(f"🔧 SQL Tool: {query_description}")
            return await generate_and_execute_sql(query_description, sql_script)

        async def data_analysis_tool_wrapper(data_json: str, analysis_type: str) -> dict:
            logger.info(f"📊 Analysis Tool: {analysis_type}")
            return await analyze_data_pandas(data_json, analysis_type)

        async def get_table_schema_wrapper(table_name: str) -> dict:
            logger.info(f"📋 Schema Tool: {table_name}")
            return db.get_table_schema(table_name)

        async def list_all_tables_wrapper() -> dict:
            logger.info("📚 List Tables Tool")
            result = db.execute_query("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """)
            return result

        # SQL Agent - DATABASE AWARE AND DIRECTIVE
        sql_agent = AssistantAgent(
            name="SQLAgent",
            model_client=self.model_client,
            tools=[sql_tool_wrapper, get_table_schema_wrapper, list_all_tables_wrapper],
            system_message="""You are a SQL expert CONNECTED to MS SQL Server (AdventureWorksDW).

🔴 CRITICAL: YOU ARE ALREADY CONNECTED - DON'T ASK FOR CREDENTIALS

**Your Tools (USE THEM IMMEDIATELY):**
1. list_all_tables_wrapper - See all tables NOW
2. get_table_schema_wrapper(table) - See columns NOW
3. sql_tool_wrapper(desc, sql) - Execute queries NOW

**WORKFLOW - NO QUESTIONS:**
When user asks for data:
1. ✅ Call list_all_tables_wrapper (see what exists)
2. ✅ Call get_table_schema_wrapper on relevant table
3. ✅ Generate SELECT query
4. ✅ Execute with sql_tool_wrapper
5. ✅ Return results

**DO NOT ASK FOR:**
- Connection details (you're connected!)
- What tables exist (use list_all_tables_wrapper!)
- Column names (use get_table_schema_wrapper!)

**Safety:**
- NEVER: DROP, DELETE, TRUNCATE, ALTER
- ALWAYS: Use SELECT TOP 100 for exploration

**BE DIRECTIVE:**
- Don't loop asking clarifying questions
- Use your tools to explore
- Make reasonable assumptions
- Execute queries directly

Example:
User: "Show sales data"
YOU: [Call list_all_tables_wrapper] → Find FactInternetSales
     [Call get_table_schema_wrapper('FactInternetSales')] → See columns
     [Execute] SELECT TOP 100 * FROM FactInternetSales ORDER BY OrderDate DESC
     [Return results]
""",
        )

        # Analysis Agent - Concise
        analysis_agent = AssistantAgent(
            name="AnalysisAgent",
            model_client=self.model_client,
            tools=[data_analysis_tool_wrapper],
            system_message="""You are a data analyst.

Analyze results from SQLAgent. Provide:
- Key statistics
- Trends
- Insights

Be brief and data-driven.""",
        )

        # Validation Agent - Quick
        validation_agent = AssistantAgent(
            name="ValidationAgent",
            model_client=self.model_client,
            system_message="""You are a QA specialist.

Check:
- Query safety (no DROP/DELETE)
- Logic correctness

Be decisive:
- "APPROVED" or "REJECTED: reason"

Keep it short.""",
        )

        # Create team with max_turns=10 (prevents loops)
        team = MagenticOneGroupChat(
            participants=[sql_agent, analysis_agent, validation_agent],
            model_client=self.model_client,
            max_turns=10,  # KEY: Prevents qwen3-vl from looping
        )

        return team

    # ============================================================
    # ROUTING - TWO-TIER SOPHISTICATED CLASSIFICATION
    # ============================================================

    def _classify_task(self, task: str) -> str:
        """
        Two-tier classification for better routing
        
        Tier 1: Check for STRONG database indicators
        Tier 2: Check for simple task indicators
        """
        
        task_lower = task.lower()
        
        # TIER 1: Strong database/data indicators (prioritize these)
        complex_indicators = [
            # Action verbs
            "show", "list", "display", "get", "fetch", "find", "retrieve",
            "analyze", "compare", "calculate from", "query",
            
            # Question starters
            "how many", "what are", "which", "who are",
            
            # Database terms
            "table", "database", "sql", "data",
            
            # Business entities
            "sales", "customer", "product", "order", "revenue",
            "employee", "supplier", "inventory", "transaction",
        ]
        
        if any(indicator in task_lower for indicator in complex_indicators):
            logger.info(f"🎯 Classified as DATA (found: {[i for i in complex_indicators if i in task_lower]})")
            return "DATA_ANALYSIS_TEAM"
        
        # TIER 2: Simple task indicators (only if no complex indicators found)
        simple_indicators = [
            "what is", "calculate", "compute", "convert",
            "how much", "percentage", "sum", "multiply", "divide"
        ]
        
        if any(indicator in task_lower for indicator in simple_indicators):
            # Double-check it's not actually a database query
            if not any(entity in task_lower for entity in ["sales", "customer", "data", "table", "from"]):
                logger.info(f"🎯 Classified as GENERAL (simple task)")
                return "GENERAL_ASSISTANT_TEAM"
        
        # Default to general for ambiguous cases
        logger.info(f"🎯 Classified as GENERAL (default)")
        return "GENERAL_ASSISTANT_TEAM"

    # ============================================================
    # MAIN EXECUTION
    # ============================================================

    async def execute_task_with_routing(self, task_description: str, username: str = "system") -> dict:
        """Execute task with routing"""

        logger.info(f"{'='*60}")
        logger.info(f"🚀 NEW TASK from {username}")
        logger.info(f"📝 Task: {task_description}")
        logger.info(f"{'='*60}")

        try:
            # Classify using two-tier system
            team_name = self._classify_task(task_description)
            
            # Create appropriate team
            if team_name == "DATA_ANALYSIS_TEAM":
                logger.info(f"📊 Creating Data Analysis Team")
                team = await self.create_data_analysis_team()
            else:
                logger.info(f"💬 Creating General Assistant Team")
                team = await self.create_general_assistant_team()

            # Execute
            logger.info(f"⚙️ Executing with {team_name}")
            result = await team.run(task=task_description)

            # Extract clean response
            response_text = self._extract_clean_content(result)

            logger.info(f"✅ Task completed successfully")
            logger.info(f"📤 Response: {response_text[:200]}...")

            return {
                "success": True,
                "response": response_text,
                "routed_to": team_name,
                "full_result": result
            }

        except Exception as e:
            logger.error(f"❌ Task execution failed: {e}")
            logger.exception("Full traceback:")
            
            return {
                "success": False,
                "error": str(e),
                "routed_to": team_name if 'team_name' in locals() else "Unknown"
            }

    # ============================================================
    # STREAMING SUPPORT
    # ============================================================

    async def execute_with_streaming(self, task_description: str, username: str = "system"):
        """Execute with streaming - FILTERED messages"""

        try:
            logger.info(f"{'='*60}")
            logger.info(f"🎬 STREAMING TASK from {username}")
            logger.info(f"📝 Task: {task_description}")
            logger.info(f"{'='*60}")

            # Classify and route
            team_name = self._classify_task(task_description)
            
            # Yield routing decision
            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": f"🎯 Routing to: **{team_name.replace('_', ' ').title()}**",
                "timestamp": datetime.now().isoformat()
            }

            # Create team
            if team_name == "DATA_ANALYSIS_TEAM":
                team = await self.create_data_analysis_team()
            else:
                team = await self.create_general_assistant_team()

            # Stream execution
            if hasattr(team, 'run_stream'):
                async for message in team.run_stream(task=task_description):
                    source = getattr(message, 'source', 'Unknown')
                    raw_content = getattr(message, 'content', '')
                    
                    # Convert to string if needed
                    if isinstance(raw_content, (list, dict)):
                        content = str(raw_content)
                    else:
                        content = raw_content
                    
                    # FILTER: Only show relevant messages
                    if not self._should_show_message(source, content):
                        logger.debug(f"⏭️ Skipping internal message from {source}")
                        continue
                    
                    # CLEAN: Extract user-friendly content
                    clean_content = self._extract_clean_content(content)
                    
                    # Classify message type
                    message_type = self._classify_message_type(source, clean_content)
                    
                    # Yield to user
                    yield {
                        "agent": source,
                        "type": message_type,
                        "content": clean_content,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    logger.debug(f"💬 [{source}] {clean_content[:100]}...")

            else:
                # Fallback: execute and return result
                result = await team.run(task=task_description)
                response = self._extract_clean_content(result)
                
                yield {
                    "agent": team_name,
                    "type": "final",
                    "content": response,
                    "timestamp": datetime.now().isoformat()
                }

            logger.info(f"✅ Streaming completed for {username}")

        except Exception as e:
            logger.error(f"❌ Streaming failed: {e}")
            logger.exception("Full traceback:")
            yield {
                "agent": "System",
                "type": "error",
                "content": f"❌ Error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    # ============================================================
    # HELPER: Message Type Classification
    # ============================================================

    def _classify_message_type(self, agent: str, content: str) -> str:
        """Classify message type for formatting"""
        
        if not isinstance(content, str):
            content = str(content)
        
        content_lower = content.lower()
        agent_lower = agent.lower()
        
        # SQL queries
        if "select" in content_lower and "from" in content_lower:
            return "action"
        
        # Tool calls
        if "calling" in content_lower or "executing" in content_lower:
            return "action"
        
        # Validation
        if "validation" in agent_lower or "approved" in content_lower:
            return "validation"
        
        # Analysis
        if "analysis" in agent_lower or "statistic" in content_lower:
            return "analysis"
        
        # Thinking
        if any(word in content_lower for word in ["i will", "let me", "first"]):
            return "thinking"
        
        # Errors
        if "error" in content_lower or "failed" in content_lower:
            return "error"
        
        # Default
        return "message"


# ============================================================
# TESTING
# ============================================================

async def test_complete_system():
    """Test the complete working system"""
    
    print("="*60)
    print("TESTING COMPLETE WORKING VERSION")
    print("="*60)
    
    orchestrator = EnhancedAgentOrchestrator()
    
    # Test 1: Database query
    print("\n[Test 1] Database Query")
    print("-"*60)
    
    async for event in orchestrator.execute_with_streaming(
        "Show me sales data",
        "test_user"
    ):
        agent = event.get("agent", "Unknown")
        msg_type = event.get("type", "message")
        content = event.get("content", "")
        
        print(f"[{agent}] ({msg_type}): {content[:150]}...")
    
    print("\n" + "="*60)
    
    # Test 2: Simple math
    print("\n[Test 2] Simple Math")
    print("-"*60)
    
    async for event in orchestrator.execute_with_streaming(
        "What is 25% of 400?",
        "test_user"
    ):
        agent = event.get("agent", "Unknown")
        msg_type = event.get("type", "message")
        content = event.get("content", "")
        
        print(f"[{agent}] ({msg_type}): {content[:150]}...")
    
    print("\n" + "="*60)
    print("✅ Tests complete!")


if __name__ == "__main__":
    asyncio.run(test_complete_system())
