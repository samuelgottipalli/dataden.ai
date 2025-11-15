# ============================================================
# ENHANCED MULTI-TEAM ORCHESTRATION
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

    def __init__(self, model_name: Optional[str] = None, task_description: str = None):
        """Initialize orchestrator with smart model selection"""

        # Determine which model to use based on task complexity
        if task_description:
            from utils.model_selector import select_model_for_task
            selected_model, selected_model_info, self.show_local_notice = select_model_for_task(task_description, model_name)
        else:
            selected_model = model_name or settings.ollama_model
            selected_model_info = (
                {
                    "vision": True,
                    "function_calling": True,
                    "json_output": True,
                    "family": selected_model.split(":")[0],
                    "structured_output": True,
                }
                if "vision" in selected_model or "vl" in selected_model
                else {
                    "vision": False,
                    "function_calling": True,
                    "json_output": True,
                    "family": selected_model.split(":")[0],
                    "structured_output": True,
                } if selected_model == model_name else settings.ollama_model_info
            )
            self.show_local_notice = False

        # # Import correct Ollama client
        # from autogen_ext.models.ollama import OllamaChatCompletionClient

        # Create model client
        self.model_client = OllamaChatCompletionClient(
            model=selected_model,
            host=settings.ollama_host,
            # Add model_info for qwen3-vl
            model_info=selected_model_info,
            options={
                "streaming": True,
                "temperature": settings.temperature,
                "max_tokens": settings.max_tokens,
            },
        )

        self.current_model = selected_model

        logger.info(f"Initialized Enhanced Orchestrator")
        logger.info(f"Model: {self.current_model}")
        logger.info(f"Max tokens: {settings.max_tokens}")
        logger.info(f"Temperature: {settings.temperature}")

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
            system_message="""You are the Supervisor and Task Router. Analyze user requests and route them to the appropriate team.

                **CRITICAL ROUTING RULES:**

                Route to **DATA_ANALYSIS_TEAM** if the request involves ANY of these:
                - Numbers, metrics, statistics, or data points (revenue, sales, counts, amounts)
                - Business entities (customers, orders, products, employees, transactions)
                - Comparisons, rankings, lists, or "top N" queries
                - Time periods (Q1, Q2, quarterly, monthly, yearly, dates)
                - Business questions (performance, growth, trends, forecasts)
                - ANY question that would require looking at stored business data
                - Questions like: "show me", "list", "find", "how many", "what is the total"
                - Department or location-based queries
                - Any mention of: revenue, profit, cost, price, quantity, inventory

                **Examples for DATA_ANALYSIS_TEAM:**
                - "Show me top 5 customers" → DATA (needs customer data from database)
                - "What is our Q4 revenue?" → DATA (needs revenue data)
                - "How many orders did we have?" → DATA (needs order count)
                - "List products by price" → DATA (needs product data)
                - "Which region has most sales?" → DATA (needs sales data)
                - "Find customers from California" → DATA (needs customer data)
                - "Show revenue trend" → DATA (needs historical data)
                - "What products are low on inventory?" → DATA (needs inventory data)

                Route to **GENERAL_ASSISTANT_TEAM** ONLY for:
                - Simple calculations without business context (15% of 850)
                - Unit conversions (100 USD to EUR, Fahrenheit to Celsius)
                - General knowledge (capitals, definitions, facts)
                - Current date/time
                - Simple math (2+2, square root of 16)

                **When in doubt, choose DATA_ANALYSIS_TEAM** - it's better to query the database unnecessarily than to miss a data question.

                Respond with ONLY:
                - "DATA_ANALYSIS_TEAM" for data/database questions
                - "GENERAL_ASSISTANT_TEAM" for simple calculations/knowledge

                No explanation needed.""",
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
        

        def _force_data_team_if_needed(self, task: str, classification: str) -> str:
            """
            Override classification for obvious data queries
            
            Sometimes the supervisor misclassifies. This catches common patterns.
            """
            task_lower = task.lower()
            
            # Strong indicators of data queries
            data_indicators = [
                "show", "list", "find", "get", "fetch", "retrieve",
                "how many", "count", "total", "sum", "average",
                "top", "bottom", "best", "worst", "highest", "lowest",
                "customer", "order", "product", "sale", "revenue",
                "employee", "transaction", "inventory", "user",
                "q1", "q2", "q3", "q4", "quarter", "month", "year",
                "compare", "rank", "sort", "filter", "where",
                "region", "department", "location", "category"
            ]
            
            # Check if task has data indicators
            indicator_count = sum(1 for indicator in data_indicators if indicator in task_lower)
            
            if indicator_count >= 2 and "GENERAL" in classification:
                logger.warning(f"Overriding classification to DATA_ANALYSIS_TEAM")
                logger.warning(f"Task has {indicator_count} data indicators: {task}")
                return "DATA_ANALYSIS_TEAM"
            
            return classification
        

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

    async def _execute_with_retry(self, team, task_description: str, team_name: str) -> dict:
        """Execute task with retry logic and fallback support"""
        from utils.usage_tracker import get_usage_tracker
        from utils.model_manager import get_model_manager
        import asyncio

        tracker = get_usage_tracker()
        model_manager = get_model_manager()

        max_retries = settings.max_retries_per_query
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            logger.info(f"Attempt {attempt}/{max_retries}")

            try:
                # Check quota
                quota_status = tracker.check_quota()
                if quota_status["exceeded"]:
                    return {
                        "success": False,
                        "error": "Daily API quota exceeded. Please try again tomorrow."
                    }

                # Execute
                result = await team.run(task=task_description)

                # Extract response
                final_message = None
                if hasattr(result, 'messages') and result.messages:
                    final_message = result.messages[-1].content
                else:
                    final_message = str(result)

                # Record success
                tracker.record_request(tokens_used=len(final_message.split()))
                model_manager.record_success()

                return {
                    "success": True,
                    "response": final_message,
                    "routed_to": team_name
                }

            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                model_manager.record_failure()

                if attempt >= max_retries:
                    return {
                        "success": False,
                        "error": f"Failed after {max_retries} attempts: {str(e)}"
                    }

                # If switched to fallback, recreate team
                if model_manager.using_fallback:
                    self.model_client, self.current_model = model_manager.get_model_client()
                    if "DATA" in team_name:
                        team = await self.create_data_analysis_team()
                    else:
                        team = await self.create_general_assistant_team()

                # Wait before retry
                await asyncio.sleep(settings.retry_delay_seconds * attempt)

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

            # Override if obviously a data query
            classification = self._force_data_team_if_needed(task_description, classification)
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
                # result = await team.run(task=task_description)
                result = await self._execute_with_retry(team, task_description, team_name)

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

    def _extract_clean_content(self, raw_content: any) -> str:
        """
        Extract clean, user-friendly content from raw agent messages
        
        IMPROVED: Better handling of formatted text and tables
        """
        import re

        # If it's already a clean string without TextMessage, return it
        if isinstance(raw_content, str):
            # Check if it contains TextMessage wrappings
            if "TextMessage(" not in raw_content and "models_usage" not in raw_content:
                # It's already clean - just return it
                return raw_content

            # Has TextMessage wrapping - extract content
            # Pattern to find content='...' in TextMessage objects
            pattern = r"content='([^']+(?:''[^']+)*?)'"
            matches = re.findall(pattern, raw_content)

            if matches:
                # Get the LAST match (final answer)
                last_content = matches[-1]

                # Clean up escaped quotes
                last_content = last_content.replace("''", "'")

                # Unescape newlines and formatting
                last_content = last_content.replace('\\n', '\n')
                last_content = last_content.replace('\\t', '\t')

                # If still has orchestrator planning messages, extract final message
                if len(last_content) > 2000 and "MagenticOneOrchestrator" in raw_content:
                    # Try to find the last orchestrator message
                    orch_pattern = r"TextMessage\(source='MagenticOneOrchestrator'[^}]+content='([^']+(?:''[^']+)*?)'"
                    orch_matches = re.findall(orch_pattern, raw_content)

                    if len(orch_matches) >= 2:
                        # Last orchestrator message is usually the formatted answer
                        last_content = orch_matches[-1].replace("''", "'")
                        last_content = last_content.replace('\\n', '\n')

                return last_content

            # If no content= found, try to strip Python objects but keep text
            cleaned = re.sub(r'TextMessage\([^)]+\)', '', raw_content)
            cleaned = re.sub(r'models_usage=[^,\]]+', '', cleaned)
            cleaned = re.sub(r'metadata=\{[^}]*\}', '', cleaned)

            # Keep newlines and formatting
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()

            return cleaned if cleaned else raw_content

        elif isinstance(raw_content, list):
            # Extract from list
            contents = []
            for item in raw_content:
                extracted = self._extract_clean_content(item)
                if extracted and len(extracted) > 10:
                    contents.append(extracted)
            return contents[-1] if contents else str(raw_content)

        elif isinstance(raw_content, dict):
            if 'content' in raw_content:
                return self._extract_clean_content(raw_content['content'])
            return str(raw_content)

        else:
            return str(raw_content)

    def _should_show_message(self, source: str, content: str, message_type: str) -> bool:
        """
        Determine if a message should be shown to the user
        
        Returns:
            True if message should be displayed
            False if message is internal/verbose
        """
        # Always show these types
        if message_type in ["final", "error"]:
            return True

        # Hide internal orchestrator planning
        if source == "MagenticOneOrchestrator" and message_type not in ["final", "routing"]:
            # Orchestrator planning is internal
            if "We are working to address" in content or "Here is the plan" in content:
                return False

        # Hide raw TextMessage dumps
        if "TextMessage(" in content and "models_usage" in content:
            return False

        # Hide very long internal messages
        if len(content) > 1500 and message_type not in ["final", "analysis"]:
            return False

        # Show everything else
        return True

    # ============================================================
    # STREAMING EXECUTION (Real-Time Responses)
    # ============================================================

    async def execute_with_streaming(self, task_description: str, username: str = "system"):
        """
        Execute task with TRUE real-time streaming
        
        This yields agent messages AS THEY HAPPEN, not after completion
        Uses the EXISTING supervisor classification approach
        """
        from datetime import datetime
        import asyncio
        from autogen_agentchat.messages import TextMessage

        try:
            logger.info(f"{'='*60}")
            logger.info(f"STREAMING TASK from {username}")
            logger.info(f"Task: {task_description}")
            logger.info(f"{'='*60}")

            # Step 1: Show initial routing message
            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": "🎯 Analyzing your request...",
                "timestamp": datetime.now().isoformat()
            }

            # Step 2: Supervisor classification (using YOUR existing approach)
            supervisor = await self.create_supervisor_agent()

            classification_prompt = f"Classify this task and route to appropriate team: {task_description}"

            # Use the SAME classification approach as execute_task_with_routing
            response = await supervisor.on_messages(
                [TextMessage(content=classification_prompt, source="user")],
                cancellation_token=None
            )

            classification = response.chat_message.content
            logger.info(f"Supervisor Classification: {classification}")

            # Step 3: Parse classification and create team
            team_name = None
            team = None

            if "DATA_ANALYSIS_TEAM" in classification:
                team_name = "DATA_ANALYSIS_TEAM"
                yield {
                    "agent": "SupervisorAgent",
                    "type": "routing",
                    "content": f"🎯 **Routing Decision**\n**Team:** Data Analysis Team\n**Reason:** Database query detected",
                    "timestamp": datetime.now().isoformat()
                }
                team = await self.create_data_analysis_team()

            elif "GENERAL_ASSISTANT_TEAM" in classification:
                team_name = "GENERAL_ASSISTANT_TEAM"
                yield {
                    "agent": "SupervisorAgent",
                    "type": "routing",
                    "content": f"🎯 **Routing Decision**\n**Team:** General Assistant Team\n**Reason:** General task",
                    "timestamp": datetime.now().isoformat()
                }
                team = await self.create_general_assistant_team()

            else:
                # Default to general assistant
                team_name = "GENERAL_ASSISTANT_TEAM"
                yield {
                    "agent": "SupervisorAgent",
                    "type": "routing",
                    "content": f"🎯 **Routing Decision**\n**Team:** General Assistant Team (default)\n**Reason:** Unclear classification",
                    "timestamp": datetime.now().isoformat()
                }
                team = await self.create_general_assistant_team()

            logger.info(f"Selected team: {team_name}")

            # Step 4: Stream team execution
            try:
                # Try to use run_stream if available
                if hasattr(team, 'run_stream'):
                    logger.info("✓ Using team.run_stream() for real-time streaming")

                    async for message in team.run_stream(task=task_description):
                        # Extract message details safely
                        source = getattr(message, 'source', 'Unknown')
                        raw_content = getattr(message, 'content', None)

                        # Handle content - might be string, list, or dict
                        if raw_content is None:
                            content = str(message)
                        elif isinstance(raw_content, str):
                            content = raw_content
                        elif isinstance(raw_content, (list, dict)):
                            content = str(raw_content)
                        else:
                            content = str(raw_content)

                        # ✨ CLEAN THE CONTENT - Extract only user-relevant parts
                        clean_content = self._extract_clean_content(content)

                        # Classify message type based on CLEAN content
                        msg_type = self._classify_message_type(source, clean_content)

                        # ✨ Check if we should show this message
                        if not self._should_show_message(source, clean_content, msg_type):
                            # Skip internal/verbose messages
                            logger.debug(f"Skipping internal message from {source}")
                            continue

                        # Yield formatted event with CLEAN content
                        yield {
                            "agent": source,
                            "type": msg_type,
                            "content": clean_content,  # ✨ Using clean_content here
                            "timestamp": datetime.now().isoformat()
                        }

                        # Small delay to prevent overwhelming client
                        await asyncio.sleep(0.05)

                    # Success message
                    yield {
                        "agent": "System",
                        "type": "final",
                        "content": "✅ Task completed successfully",
                        "timestamp": datetime.now().isoformat()
                    }

                else:
                    # Fallback: run_stream not available
                    logger.warning("⚠ run_stream not available, using word-by-word streaming fallback")

                    # Show processing message
                    yield {
                        "agent": team_name,
                        "type": "thinking",
                        "content": "🤔 Processing your request...",
                        "timestamp": datetime.now().isoformat()
                    }

                    # Execute task using existing method
                    result = await self.execute_task_with_routing(
                        task_description=task_description,
                        username=username
                    )

                    # Stream the result word-by-word for better UX
                    if result["success"]:
                        response = result.get("response", "Task completed")

                        # Send in word chunks
                        words = response.split()
                        chunk_size = 15  # words per chunk

                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])

                            yield {
                                "agent": team_name,
                                "type": "message",
                                "content": chunk + " ",
                                "timestamp": datetime.now().isoformat()
                            }

                            await asyncio.sleep(0.08)

                        # Final message
                        yield {
                            "agent": "System",
                            "type": "final",
                            "content": "✅ Task completed",
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        # Error message
                        yield {
                            "agent": "System",
                            "type": "error",
                            "content": f"❌ Error: {result.get('error', 'Unknown error')}",
                            "timestamp": datetime.now().isoformat()
                        }

            except AttributeError as ae:
                # run_stream doesn't exist - use fallback
                logger.warning(f"⚠ AttributeError with run_stream: {ae}, using word-streaming fallback")

                # Show processing
                yield {
                    "agent": team_name,
                    "type": "thinking",
                    "content": "🤔 Processing...",
                    "timestamp": datetime.now().isoformat()
                }

                # Execute normally and stream result
                result = await self.execute_task_with_routing(
                    task_description=task_description,
                    username=username
                )

                if result["success"]:
                    response = result.get("response", "Task completed")

                    # Stream response word by word
                    words = response.split()
                    chunk_size = 15

                    for i in range(0, len(words), chunk_size):
                        chunk = " ".join(words[i:i+chunk_size])

                        yield {
                            "agent": team_name,
                            "type": "message",
                            "content": chunk + " ",
                            "timestamp": datetime.now().isoformat()
                        }

                        await asyncio.sleep(0.08)
                else:
                    yield {
                        "agent": "System",
                        "type": "error",
                        "content": f"❌ Error: {result.get('error', 'Unknown error')}",
                        "timestamp": datetime.now().isoformat()
                    }

                # Final
                yield {
                    "agent": "System",
                    "type": "final",
                    "content": "✅ Complete",
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Streaming execution failed: {e}")
            logger.exception("Full traceback:")

            yield {
                "agent": "System",
                "type": "error",
                "content": f"❌ Error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _classify_message_type(self, source: str, content: str) -> str:
        """
        Classify message type based on source and content
        
        Returns: 'routing', 'thinking', 'action', 'tool_result', 'validation', 'analysis', 'final', or 'message'
        """
        content_lower = content.lower() if isinstance(content, str) else ""
        source_lower = source.lower()

        # Routing messages
        if "supervisor" in source_lower or "routing" in content_lower:
            return "routing"

        # Thinking/planning
        if any(word in content_lower for word in ["thinking", "analyzing", "planning", "considering", "let me", "i need to", "i'll"]):
            return "thinking"

        # Actions/tool calls
        if any(word in content_lower for word in ["executing", "calling", "running", "query:", "select ", "function call"]):
            return "action"

        # Tool results
        if any(word in content_lower for word in ["result:", "output:", "returned", "rows returned"]):
            return "tool_result"

        # Validation
        if "validation" in source_lower or any(word in content_lower for word in ["validating", "checking", "approved", "blocked", "safe"]):
            return "validation"

        # Analysis
        if "analysis" in source_lower or any(word in content_lower for word in ["analyzing", "shows that", "indicates", "trend"]):
            return "analysis"

        # Final answer indicators
        if any(word in content_lower for word in ["final answer", "in conclusion", "to summarize", "✅"]):
            return "final"

        # Default
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
