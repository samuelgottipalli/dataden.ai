# ============================================================
# FIXED ENHANCED MULTI-TEAM ORCHESTRATION
# Consistent MagenticOne implementation with proper error handling
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

class EnhancedAgentOrchestrator:
    """
    Enhanced orchestrator with proper MagenticOne implementation
    
    Teams:
    1. Supervisor Agent (routes tasks)
    2. User Proxy Agent (confirms risky operations) 
    3. General Assistant Team (simple tasks)
    4. Data Analysis Team (SQL + analysis)
    """

    def __init__(self):
        # Configure model client with better settings for MagenticOne
        self.model_client = OllamaChatCompletionClient(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.3,  # Lower temperature for more consistent formatting
            max_tokens=4000,  # Higher token limit for complex responses
            model_info=settings.ollama_model_info,
        )

        logger.info(f"Initialized Enhanced Orchestrator with model: {settings.ollama_model}")

    # ============================================================
    # SUPERVISOR AGENT (Task Router)
    # ============================================================

    async def create_supervisor_agent(self) -> AssistantAgent:
        """
        Supervisor Agent: Routes tasks to appropriate teams
        Uses simple classification without complex team coordination
        """

        supervisor = AssistantAgent(
            name="SupervisorAgent",
            model_client=self.model_client,
            system_message="""You are a task classification assistant. Analyze requests and respond with ONLY the team name.

**Classification Rules:**

1. **DATA_ANALYSIS_TEAM** - For:
   - SQL queries, database operations
   - Data analysis, reports, statistics
   - Table information, schema queries
   Examples: "Show sales data", "Analyze revenue", "List tables"

2. **GENERAL_ASSISTANT_TEAM** - For:
   - Math calculations
   - General knowledge questions
   - Unit conversions
   - Date/time questions
   Examples: "What is 15% of 850?", "Convert USD to EUR", "What day is it?"

**Response Format:**
Respond with ONLY ONE of these exact strings:
- DATA_ANALYSIS_TEAM
- GENERAL_ASSISTANT_TEAM

Do not add explanations or additional text.""",
        )

        return supervisor

    # ============================================================
    # USER PROXY AGENT (Safety Checks)
    # ============================================================

    async def create_user_proxy_agent(self) -> AssistantAgent:
        """
        User Proxy: Validates queries for safety
        Blocks dangerous operations
        """

        user_proxy = AssistantAgent(
            name="UserProxyAgent",
            model_client=self.model_client,
            system_message="""You are a safety validation assistant. Check if SQL operations are safe.

**Dangerous Operations to BLOCK:**
- DROP (tables, databases)
- DELETE (without specific WHERE clause)
- TRUNCATE
- ALTER
- UPDATE (affecting > 100 rows)

**Response Format:**
Respond with JSON only:
{
    "safe": true/false,
    "reason": "brief explanation"
}

Example safe query: {"safe": true, "reason": "Read-only SELECT query"}
Example unsafe query: {"safe": false, "reason": "DELETE without WHERE clause"}""",
        )

        return user_proxy

    # ============================================================
    # GENERAL ASSISTANT TEAM (Simple Tasks)
    # ============================================================

    async def create_general_assistant_team(self) -> MagenticOneGroupChat:
        """
        General Assistant Team: Handles simple, everyday tasks
        Uses MagenticOne for consistency across all teams
        """

        # Define utility tools
        async def calculate_math(expression: str) -> dict:
            """
            Perform mathematical calculations
            
            Args:
                expression: Math expression (e.g., "15% of 850", "sqrt(144)")
            
            Returns:
                Calculation result
            """
            try:
                import math

                # Handle percentage calculations
                if "%" in expression and "of" in expression:
                    match = re.search(r'(\d+\.?\d*)%\s+of\s+(\d+\.?\d*)', expression)
                    if match:
                        percent = float(match.group(1))
                        number = float(match.group(2))
                        result = (percent / 100) * number
                        return {
                            "success": True,
                            "result": result,
                            "explanation": f"{percent}% of {number} is {result}"
                        }

                # Handle basic math expressions
                # Safely evaluate using limited namespace
                safe_dict = {
                    'sqrt': math.sqrt,
                    'pow': math.pow,
                    'abs': abs,
                    'round': round,
                    'min': min,
                    'max': max,
                    'sum': sum,
                    'pi': math.pi,
                    'e': math.e
                }

                # Clean expression
                expression = expression.replace('^', '**')
                result = eval(expression, {"__builtins__": {}}, safe_dict)

                return {
                    "success": True,
                    "result": result,
                    "explanation": f"{expression} = {result}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Calculation error: {str(e)}"
                }

        async def get_current_datetime() -> dict:
            """
            Get current date and time
            
            Returns:
                Current datetime information
            """
            from datetime import datetime
            now = datetime.now()
            return {
                "success": True,
                "datetime": now.isoformat(),
                "formatted": now.strftime("%A, %B %d, %Y at %I:%M %p"),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S")
            }

        # Create assistant agent with tools
        general_agent = AssistantAgent(
            name="GeneralAssistant",
            model_client=self.model_client,
            tools=[calculate_math, get_current_datetime],
            system_message="""You are a helpful general assistant for simple tasks.

**Your Capabilities:**
1. Math calculations - use calculate_math tool
2. Current date/time - use get_current_datetime tool
3. General knowledge questions - answer directly
4. Unit conversions - calculate manually

**Response Style:**
- Be concise and direct
- Use tools when appropriate
- For general knowledge, answer from your knowledge base
- Always provide the final answer clearly

**Examples:**

User: "What is 15% of 850?"
You: [Use calculate_math("15% of 850")] → Return the result

User: "What time is it?"
You: [Use get_current_datetime] → Return formatted time

User: "What's the capital of France?"
You: "The capital of France is Paris."

Keep responses brief and helpful.""",
        )

        # Create team with single agent - MagenticOne for consistency
        team = MagenticOneGroupChat(
            participants=[general_agent],
            model_client=self.model_client,
            max_turns=5,  # Simple tasks shouldn't need many turns
        )

        return team

    # ============================================================
    # DATA ANALYSIS TEAM (SQL + Analysis)
    # ============================================================

    async def create_data_analysis_team(self) -> MagenticOneGroupChat:
        """
        Create the Data Analysis Team with proper MagenticOne configuration
        """

        # Tool wrappers
        async def sql_tool_wrapper(query_description: str, sql_script: str) -> dict:
            """Execute SQL query against data warehouse with retry logic"""
            logger.info(f"SQL Tool called with: {query_description}")
            return await generate_and_execute_sql(query_description, sql_script)

        async def data_analysis_tool_wrapper(data_json: str, analysis_type: str) -> dict:
            """Analyze retrieved data using pandas"""
            logger.info(f"Analysis Tool called for: {analysis_type}")
            return await analyze_data_pandas(data_json, analysis_type)

        async def get_table_schema_wrapper(table_name: str) -> dict:
            """Get schema information for a specific table"""
            logger.info(f"Schema tool called for table: {table_name}")
            return db.get_table_schema(table_name)

        async def list_all_tables_wrapper() -> dict:
            """List all available tables in the database"""
            logger.info("List tables tool called")
            result = db.execute_query("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """)
            return result

        # SQL Agent with enhanced system message
        sql_agent = AssistantAgent(
            name="SQLAgent",
            model_client=self.model_client,
            tools=[sql_tool_wrapper, get_table_schema_wrapper, list_all_tables_wrapper],
            system_message="""You are an expert SQL developer for Microsoft SQL Server.

**Core Responsibilities:**
1. Generate accurate T-SQL queries
2. Execute queries using sql_tool_wrapper
3. Handle errors and retry as needed
4. Present results clearly

**Safety Rules:**
- NEVER use: DROP, DELETE, TRUNCATE, ALTER
- Always use SELECT TOP for exploration
- Get schema before complex queries
- Use proper table qualifiers [schema].[table]

**Query Process:**
1. If table name provided → use get_table_schema_wrapper first
2. If unsure about tables → use list_all_tables_wrapper
3. Generate appropriate SELECT query
4. Execute using sql_tool_wrapper
5. Report results clearly

**Response Format:**
When you have results, provide:
- Brief summary of what was found
- Key data points
- Total row count if relevant

Example: "Found 150 sales records. Top revenue: $45,230 from Store #5."

Be direct and factual.""",
        )

        # Analysis Agent
        analysis_agent = AssistantAgent(
            name="AnalysisAgent",
            model_client=self.model_client,
            tools=[data_analysis_tool_wrapper],
            system_message="""You are a data analyst specializing in statistical analysis.

**Capabilities:**
- Calculate statistics (mean, median, mode, std dev)
- Identify trends and patterns
- Perform aggregations
- Generate insights

**When to Act:**
- After SQLAgent retrieves data
- When statistical analysis is requested
- For trend identification

**Response Style:**
- Clear numerical findings
- Brief interpretation
- Actionable insights

Be concise and data-driven.""",
        )

        # Validation Agent
        validation_agent = AssistantAgent(
            name="ValidationAgent",
            model_client=self.model_client,
            system_message="""You are a quality assurance specialist.

**Responsibilities:**
- Review SQL queries for correctness
- Check for dangerous operations (DROP, DELETE, etc.)
- Validate analysis logic
- Ensure safe execution

**Validation Checklist:**
1. Query uses READ-ONLY operations
2. No dangerous commands
3. Proper table references
4. Reasonable row limits

**Response Format:**
If safe: "APPROVED: Query is safe to execute"
If unsafe: "REJECTED: [specific reason]"

Be decisive and clear.""",
        )

        # Create team with MagenticOne orchestration
        team = MagenticOneGroupChat(
            participants=[sql_agent, analysis_agent, validation_agent],
            model_client=self.model_client,
            max_turns=20,  # Allow more turns for complex analysis
        )

        return team

    # ============================================================
    # MAIN EXECUTION WITH ROUTING
    # ============================================================

    async def execute_task_with_routing(self, task_description: str, username: str = "system") -> dict:
        """
        Execute task with full orchestration and proper error handling
        
        Flow:
        1. Supervisor classifies task
        2. Route to appropriate team
        3. Execute with team
        4. Return structured results
        """

        try:
            logger.info(f"{'='*60}")
            logger.info(f"NEW TASK from {username}")
            logger.info(f"Task: {task_description}")
            logger.info(f"{'='*60}")

            # Step 1: Get classification from supervisor
            supervisor = await self.create_supervisor_agent()

            # Simple direct call for classification
            classification_msg = TextMessage(
                content=f"Classify: {task_description}",
                source="user"
            )

            classification_response = await supervisor.on_messages(
                [classification_msg],
                cancellation_token=None
            )

            classification = classification_response.chat_message.content.strip()
            logger.info(f"Classification: {classification}")

            # Step 2: Route to appropriate team
            team_name = None
            team = None

            if "DATA_ANALYSIS_TEAM" in classification:
                team_name = "DATA_ANALYSIS_TEAM"
                logger.info("Routing to: DATA ANALYSIS TEAM")
                team = await self.create_data_analysis_team()
            elif "GENERAL_ASSISTANT_TEAM" in classification:
                team_name = "GENERAL_ASSISTANT_TEAM"
                logger.info("Routing to: GENERAL ASSISTANT TEAM")
                team = await self.create_general_assistant_team()
            else:
                # Default to general assistant if unclear
                team_name = "GENERAL_ASSISTANT_TEAM"
                logger.warning(f"Unclear classification, defaulting to GENERAL_ASSISTANT_TEAM")
                team = await self.create_general_assistant_team()

            # Step 3: Execute with selected team
            logger.info(f"Executing task with {team_name}")

            # Run the team with proper error handling
            try:
                result = await team.run(task=task_description)

                # Extract final response
                final_message = None
                if hasattr(result, 'messages') and result.messages:
                    final_message = result.messages[-1].content
                elif isinstance(result, str):
                    final_message = result
                else:
                    final_message = str(result)

                logger.info(f"Task completed successfully")
                logger.info(f"Response: {final_message[:200]}...")

                return {
                    "success": True,
                    "routed_to": team_name,
                    "response": final_message,
                    "username": username
                }

            except ValueError as ve:
                # Handle MagenticOne parsing errors specifically
                if "Failed to parse ledger information" in str(ve):
                    logger.error(f"MagenticOne ledger parsing error. This usually means the model response format is unexpected.")
                    logger.error(f"Try using a different model or adjusting temperature/max_tokens")
                    return {
                        "success": False,
                        "error": "Model response format incompatible with MagenticOne orchestration",
                        "details": str(ve),
                        "routed_to": team_name
                    }
                else:
                    raise  # Re-raise if it's a different ValueError

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            logger.exception("Full traceback:")
            return {
                "success": False,
                "error": str(e),
                "routed_to": team_name if 'team_name' in locals() else "UNKNOWN"
            }

    # ============================================================
    # SIMPLIFIED DIRECT EXECUTION (For Testing)
    # ============================================================

    async def execute_direct(self, task_description: str, team_type: str = "data") -> dict:
        """
        Direct execution without routing - useful for testing
        
        Args:
            task_description: The task to execute
            team_type: "data" or "general"
        """

        try:
            logger.info(f"Direct execution: {team_type} team")

            if team_type == "data":
                team = await self.create_data_analysis_team()
            else:
                team = await self.create_general_assistant_team()

            result = await team.run(task=task_description)

            # Extract response
            final_message = None
            if hasattr(result, 'messages') and result.messages:
                final_message = result.messages[-1].content
            else:
                final_message = str(result)

            return {
                "success": True,
                "response": final_message
            }

        except Exception as e:
            logger.error(f"Direct execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def execute_with_streaming(self, task_description: str, username: str = "system"):
        """
        Execute task with full orchestration and stream each agent message
        
        This method yields events in real-time as agents communicate,
        allowing OpenWebUI to display the full thought process.
        
        Yields:
            dict: Event with format:
                {
                    "agent": "AgentName",
                    "type": "routing|thinking|action|tool_result|validation|analysis|final|error",
                    "content": "Message content",
                    "timestamp": "ISO timestamp"
                }
        
        Example usage:
            async for event in orchestrator.execute_with_streaming("Show sales", "user123"):
                print(f"{event['agent']}: {event['content']}")
        """

        from datetime import datetime

        try:
            logger.info(f"{'='*60}")
            logger.info(f"STREAMING TASK from {username}")
            logger.info(f"Task: {task_description}")
            logger.info(f"{'='*60}")

            # Step 1: Supervisor classification
            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": "Analyzing your request...",
                "timestamp": datetime.now().isoformat()
            }

            supervisor = await self.create_supervisor_agent()

            # Get classification
            from autogen_agentchat.messages import TextMessage
            classification_msg = TextMessage(
                content=f"Classify: {task_description}",
                source="user"
            )

            classification_response = await supervisor.on_messages(
                [classification_msg],
                cancellation_token=None
            )

            classification = classification_response.chat_message.content.strip()
            logger.info(f"Classification: {classification}")

            # Step 2: Determine routing
            team_name = None
            team = None

            if "DATA_ANALYSIS_TEAM" in classification:
                team_name = "DATA_ANALYSIS_TEAM"
                yield {
                    "agent": "SupervisorAgent",
                    "type": "routing",
                    "content": f"📊 Routing to: **Data Analysis Team**\nThis requires SQL queries and data analysis.",
                    "timestamp": datetime.now().isoformat()
                }
                team = await self.create_data_analysis_team()

            elif "GENERAL_ASSISTANT_TEAM" in classification:
                team_name = "GENERAL_ASSISTANT_TEAM"
                yield {
                    "agent": "SupervisorAgent",
                    "type": "routing",
                    "content": f"🤖 Routing to: **General Assistant Team**\nThis is a simple task that doesn't require database access.",
                    "timestamp": datetime.now().isoformat()
                }
                team = await self.create_general_assistant_team()

            else:
                # Default to general assistant
                team_name = "GENERAL_ASSISTANT_TEAM"
                yield {
                    "agent": "SupervisorAgent",
                    "type": "routing",
                    "content": f"🤖 Routing to: **General Assistant Team** (default)\nUnclear classification, using general assistant.",
                    "timestamp": datetime.now().isoformat()
                }
                team = await self.create_general_assistant_team()

            logger.info(f"Streaming with {team_name}")

            # Step 3: Execute with team and stream messages
            try:
                # Run the team with streaming
                async for message in team.run_stream(task=task_description):
                    # Extract message details with better error handling
                    source = getattr(message, 'source', 'Unknown')
                    
                    # Handle content more carefully - it might be a list, dict, or string
                    raw_content = getattr(message, 'content', None)
                    
                    if raw_content is None:
                        content = str(message)
                    elif isinstance(raw_content, (list, dict)):
                        content = str(raw_content)
                    else:
                        content = raw_content

                    # Determine message type based on content
                    message_type = self._classify_message_type(source, content)

                    # Yield formatted event
                    yield {
                        "agent": source,
                        "type": message_type,
                        "content": content,
                        "timestamp": datetime.now().isoformat()
                    }

                    logger.debug(f"[{source}] {content[:100]}...")

                # Final success message
                yield {
                    "agent": "System",
                    "type": "final",
                    "content": "✅ Task completed successfully",
                    "timestamp": datetime.now().isoformat()
                }

                logger.info(f"Streaming completed successfully for {username}")

            except ValueError as ve:
                # Handle MagenticOne parsing errors
                if "Failed to parse ledger information" in str(ve):
                    logger.error("MagenticOne ledger parsing error during streaming")
                    yield {
                        "agent": "System",
                        "type": "error",
                        "content": "⚠️ Model response format issue detected. Falling back to direct execution...",
                        "timestamp": datetime.now().isoformat()
                    }

                    # Fallback to direct execution without streaming
                    result = await self.execute_direct(task_description, "data" if team_name == "DATA_ANALYSIS_TEAM" else "general")

                    if result["success"]:
                        yield {
                            "agent": "System",
                            "type": "final",
                            "content": result.get("response", "Task completed"),
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        yield {
                            "agent": "System",
                            "type": "error",
                            "content": f"❌ Error: {result.get('error', 'Unknown error')}",
                            "timestamp": datetime.now().isoformat()
                        }
                else:
                    raise

        except Exception as e:
            logger.error(f"Streaming execution failed: {e}")
            logger.exception("Full traceback:")

            yield {
                "agent": "System",
                "type": "error",
                "content": f"❌ Error during execution: {str(e)}\n\nPlease try again or contact support if the issue persists.",
                "timestamp": datetime.now().isoformat()
            }

    def _classify_message_type(self, agent: str, content: str) -> str:
        """
        Classify message type based on agent and content

        This helps format messages appropriately in OpenWebUI

        Handles content as either string or list (handles both cases)
        """

        # Handle content that might be a list or other types
        if isinstance(content, list):
            # If it's a list, convert to string
            content_str = " ".join(str(item) for item in content)
        elif isinstance(content, dict):
            # If it's a dict, convert to string
            content_str = str(content)
        elif content is None:
            # If None, use empty string
            content_str = ""
        else:
            # If string or other, convert to string
            content_str = str(content)

        content_lower = content_str.lower()
        agent_lower = str(agent).lower()

        # Tool-related messages
        if "tool" in content_lower or "function" in content_lower:
            if "call" in content_lower or "calling" in content_lower:
                return "action"
            elif "result" in content_lower or "returned" in content_lower:
                return "tool_result"

        # SQL-related messages
        if "select" in content_lower or "from" in content_lower or "where" in content_lower:
            return "action"

        # Validation messages
        if agent_lower == "validationagent" or "validat" in content_lower:
            return "validation"

        # Analysis messages
        if (
            agent_lower == "analysisagent"
            or "analyz" in content_lower
            or "analys" in content_lower
        ):
            return "analysis"

        # Thinking/planning messages
        if any(
            word in content_lower
            for word in ["i will", "i'll", "let me", "i need to", "first", "then"]
        ):
            return "thinking"

        # Error messages
        if "error" in content_lower or "failed" in content_lower:
            return "error"

        # Default to regular message
        return "message"

    # ============================================================
    # ALTERNATIVE: If run_stream doesn't work, use this version
    # ============================================================

    async def execute_with_streaming_fallback(self, task_description: str, username: str = "system"):
        """
        Fallback streaming implementation if team.run_stream() doesn't exist
        
        This version executes the task and simulates streaming by breaking
        down the response into logical chunks.
        
        Use this if you get: AttributeError: 'MagenticOneGroupChat' object has no attribute 'run_stream'
        """

        from datetime import datetime

        try:
            logger.info(f"{'='*60}")
            logger.info(f"STREAMING TASK (FALLBACK) from {username}")
            logger.info(f"Task: {task_description}")
            logger.info(f"{'='*60}")

            # Step 1: Show routing
            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": "Analyzing your request...",
                "timestamp": datetime.now().isoformat()
            }

            # Execute task normally
            result = await self.execute_task_with_routing(
                task_description=task_description,
                username=username
            )

            # Step 2: Show team assignment
            team_name = result.get("routed_to", "Unknown")
            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": f"Routing to: **{team_name}**",
                "timestamp": datetime.now().isoformat()
            }

            # Step 3: Show processing
            yield {
                "agent": team_name,
                "type": "thinking",
                "content": "Processing your request...",
                "timestamp": datetime.now().isoformat()
            }

            # Step 4: Show result
            if result["success"]:
                response = result.get("response", "Task completed")

                # Break response into chunks for streaming effect
                chunks = self._break_into_chunks(response)

                for i, chunk in enumerate(chunks):
                    yield {
                        "agent": team_name,
                        "type": "message" if i < len(chunks) - 1 else "final",
                        "content": chunk,
                        "timestamp": datetime.now().isoformat()
                    }

                    # Small delay between chunks
                    await asyncio.sleep(0.1)
            else:
                yield {
                    "agent": "System",
                    "type": "error",
                    "content": f"❌ Error: {result.get('error', 'Unknown error')}",
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Fallback streaming failed: {e}")
            yield {
                "agent": "System",
                "type": "error",
                "content": f"❌ Error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _break_into_chunks(self, text: str, chunk_size: int = 200) -> list:
        """
        Break text into logical chunks for streaming
        
        Breaks at sentence boundaries when possible
        """

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by sentences
        sentences = text.replace(". ", ".|").replace("? ", "?|").replace("! ", "!|").split("|")

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

# ============================================================
# TESTING FUNCTION
# ============================================================

async def test_orchestrator():
    """Simple test of the orchestrator"""

    orchestrator = EnhancedAgentOrchestrator()

    # Test 1: Simple math (general assistant)
    print("\n" + "="*60)
    print("TEST 1: General Assistant - Math")
    print("="*60)
    result1 = await orchestrator.execute_task_with_routing(
        "What is 15% of 850?",
        "test_user"
    )
    print(f"Result: {result1}")

    # Test 2: Database query (data analysis)
    print("\n" + "="*60)
    print("TEST 2: Data Analysis - Database")
    print("="*60)
    result2 = await orchestrator.execute_task_with_routing(
        "List the first 5 tables in the database",
        "test_user"
    )
    print(f"Result: {result2}")

# ============================================================
# TESTING FUNCTION
# ============================================================

async def test_streaming():
    """
    Test the streaming functionality

    Run this to verify streaming works before connecting OpenWebUI
    """

    print("=" * 60)
    print("TESTING STREAMING FUNCTIONALITY")
    print("=" * 60)

    orchestrator = EnhancedAgentOrchestrator()

    # Test 1: Simple math
    print("\n[Test 1] Simple math (General Assistant)")
    print("-" * 60)

    async for event in orchestrator.execute_with_streaming(
        "What is 25% of 400?", "test_user"
    ):
        agent = event.get("agent", "Unknown")
        msg_type = event.get("type", "message")
        content = event.get("content", "")

        print(f"[{agent}] ({msg_type}): {content[:100]}...")

    print("\n" + "=" * 60)
    print("Test 1 complete!")

    # Test 2: Database query (if you want to test)
    print("\n[Test 2] Database query (Data Analysis)")
    print("-" * 60)
    
    async for event in orchestrator.execute_with_streaming(
        "List the first 3 tables in the database",
        "test_user"
    ):
        agent = event.get("agent", "Unknown")
        msg_type = event.get("type", "message")
        content = event.get("content", "")
    
        print(f"[{agent}] ({msg_type}): {content[:100]}...")
    
    print("\n" + "=" * 60)
    print("Test 2 complete!")


if __name__ == "__main__":
    # asyncio.run(test_orchestrator())
    asyncio.run(test_streaming())
