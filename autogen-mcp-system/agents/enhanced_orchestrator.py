# ============================================================
# COMPLETE WORKING VERSION - Enhanced Orchestrator
# All features from November 15 working session
# ============================================================

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient
from config.settings import settings
from loguru import logger
from mcp_server.database import db
from mcp_server.tools import analyze_data_pandas, generate_and_execute_sql

from utils.model_manager import model_manager

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
        # Use model manager for automatic fallback
        self.model_manager = model_manager
        self.model_client = self.model_manager.get_model_client()

        logger.info(f"✨ Enhanced Orchestrator initialized")
        logger.info(f"   Current model: {self.model_manager.current_model}")

    # ============================================================
    # MESSAGE FILTERING - Removes TextMessage junk
    # ============================================================

    # def _extract_clean_content(self, result) -> str:
    #     """
    #     Extract clean, user-friendly content from raw agent messages

    #     This is the KEY to clean responses - filters out ALL internal junk
    #     """

    #     if isinstance(result, str):
    #         # Check if it has TextMessage wrappers
    #         if "TextMessage(" not in result:
    #             return result

    #         # Extract content from TextMessage format using regex
    #         pattern = r"content='([^']+(?:''[^']+)*?)'"
    #         matches = re.findall(pattern, result)

    #         if matches:
    #             # Get the LAST match (usually the final answer)
    #             last_content = matches[-1]
    #             # Clean up escaped quotes
    #             last_content = last_content.replace("''", "'")

    #             # If still too technical, try to extract just the answer
    #             if len(last_content) > 1000:
    #                 # Look for actual answer after planning
    #                 answer_patterns = [
    #                     r"(?:Final answer|Result|Answer):\s*(.+?)(?:TextMessage|$)",
    #                     r"(?:Here(?:'s| is) the (?:result|answer)):\s*(.+?)(?:TextMessage|$)",
    #                 ]
    #                 for pattern in answer_patterns:
    #                     answer_match = re.search(pattern, last_content, re.IGNORECASE | re.DOTALL)
    #                     if answer_match:
    #                         return answer_match.group(1).strip()

    #             return last_content

    #     # Handle object with messages attribute
    #     if hasattr(result, 'messages'):
    #         messages = result.messages
    #         if messages:
    #             # Get last message
    #             last_message = messages[-1]
    #             if hasattr(last_message, 'content'):
    #                 content = last_message.content
    #                 # Recursively clean if needed
    #                 if isinstance(content, str) and "TextMessage(" in content:
    #                     return self._extract_clean_content(content)
    #                 return str(content)

    #     # Fallback
    #     return str(result)

    # def _should_show_message(self, source: str, content: str) -> bool:
    #     """
    #     Determine if a message should be shown to user

    #     Filters out internal orchestrator planning messages
    #     """

    #     # Skip internal orchestrator planning
    #     if source == "MagenticOneOrchestrator":
    #         # Only show if it's a final answer
    #         if any(phrase in content.lower() for phrase in ["final", "answer", "result", "here is"]):
    #             return True
    #         return False

    #     # Skip empty or very short messages
    #     if not content or len(content.strip()) < 5:
    #         return False

    #     # Skip technical metadata messages
    #     if any(keyword in content.lower() for keyword in ["textmessage(", "models_usage", "metadata={}"]):
    #         return False

    #     # Show everything else
    #     return True

    def _extract_clean_content(self, raw_content: Any) -> str:
        """
        Extract clean, user-friendly content from raw agent messages
        
        IMPROVED VERSION - Removes ALL TextMessage wrappers
        
        Handles:
        - TextMessage(source='...', content='...')
        - [TextMessage(...), TextMessage(...)]
        - models_usage=None, metadata={}
        - Nested TextMessages
        - Multiple messages in lists
        """

        # Convert to string if needed
        if not isinstance(raw_content, str):
            content_str = str(raw_content)
        else:
            content_str = raw_content

        # Quick check: if no TextMessage wrapper, return as-is
        if "TextMessage(" not in content_str and "models_usage" not in content_str:
            return content_str

        # Step 1: Extract all content='...' values
        # This handles nested quotes and escaped quotes
        content_pattern = r"content=['\"]([^'\"]+(?:['\"]['\"][^'\"]+)*?)['\"]"
        content_matches = re.findall(content_pattern, content_str)

        if content_matches:
            # Get the last meaningful content (usually the final answer)
            for match in reversed(content_matches):
                # Skip if it's just metadata or empty
                if match and len(match.strip()) > 5:
                    # Clean up escaped quotes
                    cleaned = match.replace("''", "'").replace('""', '"')
                    return cleaned.strip()

        # Step 2: If no content= found, try removing wrappers directly
        # Remove TextMessage(...) wrappers completely
        cleaned = re.sub(r'TextMessage\([^)]+\)', '', content_str)

        # Remove list brackets
        cleaned = re.sub(r'^\[|\]$', '', cleaned)

        # Remove metadata fields
        cleaned = re.sub(r'models_usage\s*=\s*\w+', '', cleaned)
        cleaned = re.sub(r'metadata\s*=\s*\{[^}]*\}', '', cleaned)
        cleaned = re.sub(r'source\s*=\s*["\'][^"\']+["\']', '', cleaned)

        # Remove extra commas and spaces
        cleaned = re.sub(r'\s*,\s*', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Remove common prefixes that might remain
        cleaned = re.sub(r'^messages\s*=\s*', '', cleaned)

        cleaned = cleaned.strip()

        # Step 3: If we got nothing or something too short, return original
        if not cleaned or len(cleaned) < 5:
            return content_str

        return cleaned

    def _should_show_message(self, source: str, content: str) -> bool:
        """
        Determine if a message should be shown to user
        
        IMPROVED VERSION - Better filtering of internal messages
        
        Filters out:
        - Empty or very short messages
        - Pure technical metadata
        - Internal orchestrator planning (unless it's final answer)
        - Messages that are just TextMessage wrappers
        """

        # Skip empty or very short
        if not content or len(content.strip()) < 5:
            logger.debug(f"⏭️ Skipping empty message from {source}")
            return False

        content_lower = content.lower()

        # Skip if it's still wrapped in TextMessage (filtering failed)
        if "textmessage(" in content_lower and "content=" in content_lower:
            logger.debug(f"⏭️ Skipping unfiltered TextMessage from {source}")
            return False

        # Skip if it's just metadata
        if all(keyword in content_lower for keyword in ["models_usage", "metadata"]):
            logger.debug(f"⏭️ Skipping metadata from {source}")
            return False

        # Handle MagenticOneOrchestrator messages
        if source == "MagenticOneOrchestrator":
            # Only show if it contains final answer indicators
            final_indicators = [
                "final", "answer", "result", "here is", "here are",
                "completed", "summary", "conclusion"
            ]
            if any(indicator in content_lower for indicator in final_indicators):
                return True
            # Skip internal planning messages
            planning_indicators = [
                "we are working", "to answer this", "here is an initial",
                "fact sheet", "assembled the following", "team:"
            ]
            if any(indicator in content_lower for indicator in planning_indicators):
                logger.debug(f"⏭️ Skipping orchestrator planning from {source}")
                return False

        # Skip very long messages that look like dumps
        if len(content) > 3000 and ("textmessage" in content_lower or "models_usage" in content_lower):
            logger.debug(f"⏭️ Skipping long technical dump from {source}")
            return False

        # Show everything else
        return True

    # ============================================================
    # ADDITIONAL HELPER: Clean streaming messages in real-time
    # ============================================================

    def _clean_streaming_message(self, raw_message: Any) -> str:
        """
        Clean a streaming message before yielding to user
        
        This is called BEFORE _extract_clean_content for extra safety
        """

        # Get the content
        if hasattr(raw_message, 'content'):
            content = raw_message.content
        else:
            content = str(raw_message)

        # Quick pre-cleaning
        if isinstance(content, str):
            # Remove obvious TextMessage patterns
            if content.startswith("TextMessage("):
                # Extract just the content part
                match = re.search(r"content=['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)

            # Remove list markers
            content = content.strip("[]")

        return content

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

    def _build_context_prompt(self, current_message: str, conversation_history: List[Dict]) -> str:
        """
        Build enriched prompt with conversation context
        
        Args:
            current_message: The latest user message
            conversation_history: List of previous messages [{"role": "user/assistant", "content": "..."}]
        
        Returns:
            Enhanced prompt with context
        """

        if not conversation_history or len(conversation_history) <= 1:
            # No previous context, return as-is
            return current_message

        # Build context summary from previous messages
        context_lines = []
        context_lines.append("**Previous conversation context:**")

        # Get last 3-5 exchanges (6-10 messages)
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history

        for msg in recent_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user":
                context_lines.append(f"User: {content[:200]}")  # Truncate long messages
            elif role == "assistant":
                context_lines.append(f"Assistant: {content[:200]}")

        # Add current message
        context_lines.append("")
        context_lines.append("**Current question:**")
        context_lines.append(current_message)

        enhanced_prompt = "\n".join(context_lines)

        logger.info(f"📚 Added conversation context ({len(recent_history)} previous messages)")
        logger.debug(f"Context: {enhanced_prompt[:500]}...")

        return enhanced_prompt

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

    async def execute_task_with_routing(
        self,
        task_description: str,
        username: str = "system",
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Execute task with routing and conversation context

        Args:
            task_description: Current user message
            username: User identifier
            conversation_history: Previous messages for context
        """

        logger.info(f"{'='*60}")
        logger.info(f"🚀 NEW TASK from {username}")
        logger.info(f"📝 Task: {task_description}")

        # Add context if available
        if conversation_history:
            logger.info(f"📚 With {len(conversation_history)} previous messages")
            # Build enhanced prompt with context
            enriched_task = self._build_context_prompt(
                task_description, conversation_history
            )
        else:
            enriched_task = task_description

        logger.info(f"{'='*60}")

        try:
            # Classify using two-tier system
            team_name = self._classify_task(enriched_task)

            # Create appropriate team
            if team_name == "DATA_ANALYSIS_TEAM":
                logger.info(f"📊 Creating Data Analysis Team")
                team = await self.create_data_analysis_team()
            else:
                logger.info(f"💬 Creating General Assistant Team")
                team = await self.create_general_assistant_team()

            # Execute with enriched task (includes context)
            # Execute with fallback support
            logger.info(f"⚙️ Executing with {team_name}")

            try:
                result = await team.run(task=enriched_task)

                # Report success to model manager
                self.model_manager.report_success()

            except Exception as exec_error:
                # Check if it's a rate limit error
                if self.model_manager.handle_model_error(exec_error):
                    logger.info("♻️ Retrying with fallback model...")

                    # Get new client with fallback model
                    self.model_client = self.model_manager.get_model_client()

                    # Recreate team with fallback model
                    if team_name == "DATA_ANALYSIS_TEAM":
                        team = await self.create_data_analysis_team()
                    else:
                        team = await self.create_general_assistant_team()

                    # Retry once
                    try:
                        result = await team.run(task=enriched_task)
                        self.model_manager.report_success()
                        logger.info("✅ Fallback succeeded!")
                    except Exception as retry_error:
                        logger.error(f"❌ Fallback also failed: {retry_error}")
                        raise
                else:
                    # Not a rate limit error, propagate
                    raise exec_error

            # Extract clean response (continues as before)
            response_text = self._extract_clean_content(result)

            logger.info(f"✅ Task completed successfully")
            logger.info(f"📤 Response: {response_text[:200]}...")

            return {
                "success": True,
                "response": response_text,
                "routed_to": team_name,
                "model_used": self.model_manager.current_model,  # NEW: Track which model was used
                "full_result": result
            }

        except Exception as e:
            logger.error(f"❌ Task execution failed: {e}")
            logger.exception("Full traceback:")

            return {
                "success": False,
                "error": str(e),
                "routed_to": team_name if 'team_name' in locals() else "Unknown",
                "model_used": self.model_manager.current_model  # NEW: Track model even on failure
            }

    # ============================================================
    # STREAMING SUPPORT
    # ============================================================

    async def execute_with_streaming(
        self, 
        task_description: str, 
        username: str = "system",
        conversation_history: Optional[List[Dict]] = None
    ):
        """
        Execute with streaming and conversation context
        
        Args:
            task_description: Current user message
            username: User identifier  
            conversation_history: Previous messages for context
        """

        try:
            logger.info(f"{'='*60}")
            logger.info(f"🎬 STREAMING TASK from {username}")
            logger.info(f"📝 Task: {task_description}")

            # Add context if available
            if conversation_history:
                logger.info(f"📚 With {len(conversation_history)} previous messages")
                enriched_task = self._build_context_prompt(task_description, conversation_history)
            else:
                enriched_task = task_description

            logger.info(f"{'='*60}")

            # Classify and route
            team_name = self._classify_task(enriched_task)

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

            # Stream execution with enriched task
            if hasattr(team, 'run_stream'):
                try:
                    async for message in team.run_stream(task=enriched_task):
                        source = getattr(message, 'source', 'Unknown')
                        raw_content = getattr(message, 'content', '')

                        # Pre-clean the message
                        pre_cleaned = self._clean_streaming_message(message)

                        # Convert to string if needed
                        if isinstance(pre_cleaned, (list, dict)):
                            content = str(pre_cleaned)
                        else:
                            content = pre_cleaned

                        # FILTER: Only show relevant messages
                        if not self._should_show_message(source, content):
                            logger.debug(f"⏭️ Skipping internal message from {source}")
                            continue

                        # CLEAN: Extract user-friendly content
                        clean_content = self._extract_clean_content(content)

                        # Classify message type
                        message_type = self._classify_message_type(source, clean_content)

                        # FINAL CHECK: Make sure we didn't leave any wrappers
                        if "TextMessage(" in clean_content:
                            logger.warning(f"⚠️ TextMessage wrapper still present, doing deep clean")
                            # Try one more aggressive clean
                            clean_content = re.sub(r'.*content=["\']([^"\']+)["\'].*', r'\1', clean_content)

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
                    # Report success after streaming completes
                    self.model_manager.report_success()

                except Exception as stream_error:
                    # Check if it's a rate limit error
                    if self.model_manager.handle_model_error(stream_error):
                        yield {
                            "agent": "System",
                            "type": "routing",
                            "content": f"♻️ Rate limit hit, switching to fallback model ({self.model_manager.fallback_model})...",
                            "timestamp": datetime.now().isoformat()
                        }

                        # Get new client with fallback
                        self.model_client = self.model_manager.get_model_client()

                        # Recreate team
                        if team_name == "DATA_ANALYSIS_TEAM":
                            team = await self.create_data_analysis_team()
                        else:
                            team = await self.create_general_assistant_team()

                        # Retry streaming with fallback
                        async for message in team.run_stream(task=enriched_task):
                            # ... same message processing ...
                            source = getattr(message, 'source', 'Unknown')
                            raw_content = getattr(message, 'content', '')

                            if isinstance(raw_content, (list, dict)):
                                content = str(raw_content)
                            else:
                                content = raw_content

                            if not self._should_show_message(source, content):
                                continue

                            clean_content = self._extract_clean_content(content)
                            message_type = self._classify_message_type(source, clean_content)

                            yield {
                                "agent": source,
                                "type": message_type,
                                "content": clean_content,
                                "timestamp": datetime.now().isoformat()
                            }

                        self.model_manager.report_success()
                    else:
                        # Not a rate limit error
                        raise stream_error

            else:
                # Fallback: execute and return result
                result = await team.run(task=enriched_task)
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
