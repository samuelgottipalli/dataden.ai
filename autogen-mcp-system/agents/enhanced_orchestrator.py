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


if __name__ == "__main__":
    asyncio.run(test_orchestrator())
