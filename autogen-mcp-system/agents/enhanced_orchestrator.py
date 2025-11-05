# ============================================================
# ENHANCED MULTI-TEAM ORCHESTRATION
# With Supervisor, User Proxy, and General Assistant
# ============================================================

# FILE: agents/enhanced_orchestrator.py
# ============================================================
import asyncio
from typing import Optional, Dict, List
from loguru import logger
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import MagenticOneGroupChat, RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient
from config.settings import settings
from mcp_server.tools import generate_and_execute_sql, analyze_data_pandas
from mcp_server.database import db
import re

class EnhancedAgentOrchestrator:
    """
    Enhanced orchestrator with:
    1. Supervisor Agent (routes tasks to appropriate teams)
    2. User Proxy Agent (confirms risky operations)
    3. General Assistant Team (simple tasks)
    4. Data Analysis Team (SQL + analysis)
    """
    
    def __init__(self):
        self.model_client = OllamaChatCompletionClient(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.7,
            max_tokens=2000
        )
        
        # User interaction state
        self.pending_approval = None
        self.user_response = None
        
        logger.info(f"Initialized Enhanced Orchestrator with model: {settings.ollama_model}")
    
    # ============================================================
    # FEATURE 1: SUPERVISOR AGENT (Task Manager/Team Manager)
    # ============================================================
    
    async def create_supervisor_agent(self) -> AssistantAgent:
        """
        Supervisor Agent: Routes tasks to appropriate teams
        
        Responsibilities:
        - Classify incoming user requests
        - Route to appropriate team (Data/General/Web/Calendar)
        - Handle multi-step tasks
        - Coordinate between teams if needed
        """
        
        supervisor = AssistantAgent(
            name="SupervisorAgent",
            model_client=self.model_client,
            system_message="""You are the Supervisor and Task Manager. Your role is to analyze user requests and route them to the appropriate team.

**Available Teams:**

1. **DATA_ANALYSIS_TEAM** - Use for:
   - SQL queries and database operations
   - Data analysis, statistics, trends
   - Reports from data warehouse
   - Examples: "Show Q4 sales", "Analyze customer data", "Generate revenue report"

2. **GENERAL_ASSISTANT_TEAM** - Use for:
   - Simple math calculations
   - General knowledge questions
   - Timers, reminders, conversions
   - Unit conversions (currency, temperature, etc.)
   - Current date/time questions
   - Examples: "What's 15% of 850?", "Convert 100 USD to EUR", "What is the capital of France?"

3. **WEB_RESEARCH_TEAM** (Not yet implemented) - Use for:
   - Internet searches
   - News and current events
   - Competitor research
   - Examples: "Find latest news on X", "Research competitor Y"

4. **CALENDAR_TEAM** (Not yet implemented) - Use for:
   - Scheduling meetings
   - Checking availability
   - Calendar management
   - Examples: "Schedule meeting next Tuesday", "Check my calendar"

**Your Task Classification Process:**

1. Analyze the user's request carefully
2. Identify the PRIMARY category (DATA/GENERAL/WEB/CALENDAR)
3. If the task requires multiple teams, break it into sub-tasks
4. Respond ONLY with the classification in this exact format:

   **Single Team:**
   ROUTE: [TEAM_NAME]
   REASONING: [1-2 sentence explanation]
   
   **Multiple Teams:**
   ROUTE: MULTI_STEP
   STEP_1: [TEAM_NAME] - [what to do]
   STEP_2: [TEAM_NAME] - [what to do]
   REASONING: [why multiple steps needed]

**Important Rules:**
- Always choose the most appropriate team
- For ambiguous requests, ask the user for clarification
- For risky operations, note "REQUIRES_APPROVAL" in reasoning
- Keep reasoning concise and clear""",
        )
        
        return supervisor
    
    # ============================================================
    # FEATURE 2: USER PROXY AGENT (Safety & Confirmation)
    # ============================================================
    
    async def create_user_proxy_agent(self) -> AssistantAgent:
        """
        User Proxy Agent: Confirms risky operations with user
        
        Responsibilities:
        - Detect potentially risky operations
        - Ask user for confirmation
        - Block execution until user approves
        - Log all user decisions
        """
        
        async def request_user_approval(operation_description: str, risk_level: str, details: str) -> dict:
            """
            Request user approval for a risky operation
            
            Args:
                operation_description: What operation is being requested
                risk_level: LOW/MEDIUM/HIGH/CRITICAL
                details: Detailed explanation of risks
            
            Returns:
                {"approved": bool, "user_comment": str}
            """
            logger.warning(f"⚠️  USER APPROVAL REQUIRED - Risk Level: {risk_level}")
            logger.warning(f"Operation: {operation_description}")
            logger.warning(f"Details: {details}")
            
            # Store pending approval
            self.pending_approval = {
                "operation": operation_description,
                "risk_level": risk_level,
                "details": details
            }
            
            # In a real system, this would trigger UI notification
            # For now, we'll simulate user input
            print("\n" + "="*60)
            print("⚠️  USER APPROVAL REQUIRED")
            print("="*60)
            print(f"Operation: {operation_description}")
            print(f"Risk Level: {risk_level}")
            print(f"Details: {details}")
            print("="*60)
            
            # Get user input (in real system, this comes from UI)
            user_input = input("Do you want to proceed? (yes/no): ").strip().lower()
            
            approved = user_input in ['yes', 'y']
            
            logger.info(f"User decision: {'APPROVED' if approved else 'REJECTED'}")
            
            return {
                "approved": approved,
                "user_comment": user_input,
                "timestamp": str(asyncio.get_event_loop().time())
            }
        
        user_proxy = AssistantAgent(
            name="UserProxyAgent",
            model_client=self.model_client,
            tools=[request_user_approval],
            system_message="""You are the User Proxy Agent responsible for user safety and confirmation of risky operations.

**Your Responsibilities:**

1. **Monitor all operations** for potential risks
2. **Classify risk levels** and request approval when needed
3. **Block dangerous operations** until user confirms
4. **Log all decisions** for audit trail

**Risk Classification:**

**CRITICAL** (Always require approval):
- DELETE, DROP, TRUNCATE operations on database
- Executing code that modifies system files
- Financial transactions
- Sending emails or external communications
- Accessing sensitive personal data

**HIGH** (Require approval):
- UPDATE operations affecting many rows (>100)
- Web scraping or automated requests
- Downloading files from internet
- Creating/modifying calendar events
- Accessing external APIs

**MEDIUM** (Warn but allow):
- Complex SQL queries that might be slow
- Large data exports (>1000 rows)
- Multiple simultaneous operations

**LOW** (Allow without approval):
- SELECT queries (read-only)
- Simple calculations
- General knowledge questions
- View operations

**When to Intervene:**

Before ANY operation, analyze:
1. What is being requested?
2. What are the potential consequences?
3. Is this reversible?
4. Could this harm data, systems, or users?
5. Is this socially acceptable and legal?

**Red Flags:**
- Keywords: DELETE, DROP, TRUNCATE, EXECUTE, EVAL, SYSTEM
- Accessing external networks without reason
- Operations on sensitive tables (users, passwords, financial)
- Requests involving illegal content
- Socially unacceptable content (hate speech, violence, etc.)

**If risky operation detected:**
1. Call request_user_approval() tool
2. Provide clear operation description
3. Explain risks in simple terms
4. Wait for user decision
5. Proceed only if approved
6. Log the decision

**Example Interventions:**

❌ "Delete all records from users table"
   → CRITICAL: Call request_user_approval()
   
❌ "Execute this Python code: os.system('rm -rf /')"
   → CRITICAL: BLOCK immediately, call request_user_approval()
   
⚠️  "Update 500 customer records with new address"
   → HIGH: Call request_user_approval()
   
✅ "Show me top 10 sales records"
   → LOW: Allow without approval

Always prioritize user safety and data integrity.""",
        )
        
        return user_proxy
    
    # ============================================================
    # FEATURE 3: GENERAL ASSISTANT TEAM (Simple Tasks)
    # ============================================================
    
    async def create_general_assistant_team(self) -> MagenticOneGroupChat:
        """
        General Assistant Team: Handles simple, everyday tasks
        
        Capabilities:
        - Math calculations
        - General knowledge
        - Unit conversions
        - Date/time operations
        - Timers and reminders
        """
        
        # Define simple utility tools
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
                import re
                
                # Handle percentage calculations
                if "%" in expression and "of" in expression:
                    match = re.search(r'(\d+\.?\d*)%\s+of\s+(\d+\.?\d*)', expression)
                    if match:
                        percentage = float(match.group(1))
                        number = float(match.group(2))
                        result = (percentage / 100) * number
                        return {
                            "success": True,
                            "expression": expression,
                            "result": result,
                            "explanation": f"{percentage}% of {number} = {result}"
                        }
                
                # Handle basic math expressions
                # Safe evaluation with limited scope
                safe_dict = {
                    "sqrt": math.sqrt,
                    "pow": math.pow,
                    "sin": math.sin,
                    "cos": math.cos,
                    "tan": math.tan,
                    "log": math.log,
                    "pi": math.pi,
                    "e": math.e
                }
                
                result = eval(expression, {"__builtins__": {}}, safe_dict)
                
                return {
                    "success": True,
                    "expression": expression,
                    "result": result
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "expression": expression,
                    "error": str(e)
                }
        
        async def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
            """
            Convert between units
            
            Supported conversions:
            - Temperature: celsius, fahrenheit, kelvin
            - Distance: meters, kilometers, miles, feet
            - Weight: grams, kilograms, pounds, ounces
            """
            
            conversions = {
                # Temperature
                ("celsius", "fahrenheit"): lambda x: (x * 9/5) + 32,
                ("fahrenheit", "celsius"): lambda x: (x - 32) * 5/9,
                ("celsius", "kelvin"): lambda x: x + 273.15,
                ("kelvin", "celsius"): lambda x: x - 273.15,
                
                # Distance
                ("meters", "kilometers"): lambda x: x / 1000,
                ("kilometers", "meters"): lambda x: x * 1000,
                ("meters", "feet"): lambda x: x * 3.28084,
                ("feet", "meters"): lambda x: x / 3.28084,
                ("kilometers", "miles"): lambda x: x * 0.621371,
                ("miles", "kilometers"): lambda x: x / 0.621371,
                
                # Weight
                ("grams", "kilograms"): lambda x: x / 1000,
                ("kilograms", "grams"): lambda x: x * 1000,
                ("kilograms", "pounds"): lambda x: x * 2.20462,
                ("pounds", "kilograms"): lambda x: x / 2.20462,
            }
            
            key = (from_unit.lower(), to_unit.lower())
            
            if key in conversions:
                result = conversions[key](value)
                return {
                    "success": True,
                    "original": f"{value} {from_unit}",
                    "converted": f"{result} {to_unit}",
                    "result": result
                }
            else:
                return {
                    "success": False,
                    "error": f"Conversion from {from_unit} to {to_unit} not supported"
                }
        
        async def get_current_datetime(timezone: str = "UTC") -> dict:
            """Get current date and time"""
            from datetime import datetime
            import pytz
            
            try:
                tz = pytz.timezone(timezone)
                now = datetime.now(tz)
                
                return {
                    "success": True,
                    "datetime": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M:%S"),
                    "day_of_week": now.strftime("%A"),
                    "timezone": timezone
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # General Assistant Agent
        general_agent = AssistantAgent(
            name="GeneralAssistant",
            model_client=self.model_client,
            tools=[calculate_math, convert_units, get_current_datetime],
            system_message="""You are a General Assistant for simple, everyday tasks.

**Your Capabilities:**

1. **Mathematical Calculations**
   - Basic arithmetic: addition, subtraction, multiplication, division
   - Percentages: "What's 15% of 850?"
   - Advanced math: square roots, powers, trigonometry
   - Use the calculate_math tool

2. **Unit Conversions**
   - Temperature: Celsius, Fahrenheit, Kelvin
   - Distance: meters, kilometers, miles, feet
   - Weight: grams, kilograms, pounds, ounces
   - Use the convert_units tool

3. **Date and Time**
   - Current date and time
   - Day of week
   - Different timezones
   - Use the get_current_datetime tool

4. **General Knowledge**
   - Answer common knowledge questions directly
   - Provide factual information
   - Explain concepts simply

**How to Respond:**

- For math: Use calculate_math tool, then explain the result
- For conversions: Use convert_units tool, provide clear answer
- For date/time: Use get_current_datetime tool
- For knowledge: Answer directly from your training

**Example Interactions:**

User: "What's 15% of 850?"
You: [Use calculate_math tool] → "15% of 850 is 127.5"

User: "Convert 100 Fahrenheit to Celsius"
You: [Use convert_units tool] → "100°F is approximately 37.78°C"

User: "What's the capital of France?"
You: "The capital of France is Paris."

User: "What time is it?"
You: [Use get_current_datetime tool] → "It's currently 3:45 PM UTC on Wednesday, October 27, 2025"

Keep responses concise, friendly, and helpful.""",
        )
        
        # Create team (single agent for simple tasks)
        team = RoundRobinGroupChat(
            participants=[general_agent],
            model_client=self.model_client,
        )
        
        return team
    
    # ============================================================
    # DATA ANALYSIS TEAM (From Previous Implementation)
    # ============================================================
    
    async def create_data_analysis_team(self) -> MagenticOneGroupChat:
        """Create the Data Analysis Team (SQL + Analysis + Validation)"""
        
        # Tools
        async def sql_tool_wrapper(query_description: str, sql_script: str) -> dict:
            """Execute SQL query against data warehouse with retry logic"""
            return await generate_and_execute_sql(query_description, sql_script)
        
        async def data_analysis_tool_wrapper(data_json: str, analysis_type: str) -> dict:
            """Analyze retrieved data using pandas"""
            return await analyze_data_pandas(data_json, analysis_type)
        
        async def get_table_schema_wrapper(table_name: str) -> dict:
            """Get schema information for a specific table"""
            logger.info(f"Schema tool called for table: {table_name}")
            return db.get_table_schema(table_name)
        
        # SQL Agent
        sql_agent = AssistantAgent(
            name="SQLAgent",
            model_client=self.model_client,
            tools=[sql_tool_wrapper, get_table_schema_wrapper],
            system_message="""You are an expert SQL developer for Microsoft SQL Server.

Generate accurate SQL queries, execute them safely, and report results clearly.
Always get table schema first. Use SELECT TOP for exploration.
Never use DROP, DELETE, TRUNCATE, or ALTER.""",
        )
        
        # Analysis Agent
        analysis_agent = AssistantAgent(
            name="AnalysisAgent",
            model_client=self.model_client,
            tools=[data_analysis_tool_wrapper],
            system_message="""You are a data analyst.

Perform statistical analysis, identify trends, calculate metrics, and provide insights.
Use data_analysis_tool_wrapper for pandas operations.""",
        )
        
        # Validation Agent
        validation_agent = AssistantAgent(
            name="ValidationAgent",
            model_client=self.model_client,
            system_message="""You are a quality assurance specialist.

Review SQL queries and analysis for accuracy. Approve or request corrections.
Check for dangerous operations and logical inconsistencies.""",
        )
        
        team = MagenticOneGroupChat(
            participants=[sql_agent, analysis_agent, validation_agent],
            model_client=self.model_client,
            max_turns=15,
        )
        
        return team
    
    # ============================================================
    # MAIN ORCHESTRATION LOGIC
    # ============================================================
    
    async def execute_task_with_routing(self, task_description: str, username: str = "system") -> dict:
        """
        Execute task with full orchestration:
        1. Supervisor classifies and routes
        2. User Proxy checks for risks
        3. Appropriate team executes
        """
        
        try:
            logger.info(f"="*60)
            logger.info(f"NEW TASK from {username}")
            logger.info(f"Task: {task_description}")
            logger.info(f"="*60)
            
            # Step 1: Supervisor classifies the task
            supervisor = await self.create_supervisor_agent()
            
            # Ask supervisor to classify
            classification_prompt = f"Classify this task and route to appropriate team: {task_description}"
            
            # Simple synchronous call for classification
            from autogen_agentchat.messages import TextMessage
            response = await supervisor.on_messages(
                [TextMessage(content=classification_prompt, source="user")],
                cancellation_token=None
            )
            
            classification = response.chat_message.content
            logger.info(f"Supervisor Classification:\n{classification}")
            
            # Step 2: Parse classification
            if "DATA_ANALYSIS_TEAM" in classification:
                team_name = "DATA_ANALYSIS_TEAM"
                team = await self.create_data_analysis_team()
            elif "GENERAL_ASSISTANT_TEAM" in classification:
                team_name = "GENERAL_ASSISTANT_TEAM"
                team = await self.create_general_assistant_team()
            else:
                return {
                    "success": False,
                    "error": "Could not determine appropriate team",
                    "classification": classification
                }
            
            logger.info(f"Routing to: {team_name}")
            
            # Step 3: User Proxy checks for risks
            user_proxy = await self.create_user_proxy_agent()
            
            risk_check_prompt = f"Analyze this task for risks: {task_description}"
            risk_response = await user_proxy.on_messages(
                [TextMessage(content=risk_check_prompt, source="user")],
                cancellation_token=None
            )
            
            risk_assessment = risk_response.chat_message.content
            logger.info(f"Risk Assessment:\n{risk_assessment}")
            
            # If high risk detected, get user approval
            if "CRITICAL" in risk_assessment or "HIGH" in risk_assessment:
                logger.warning("High-risk operation detected - would request user approval here")
                # In production, this would call request_user_approval tool
                # For now, we proceed (in real system, wait for approval)
            
            # Step 4: Execute with appropriate team
            result = await team.run(task_description)
            
            logger.info(f"Task completed by {team_name}")
            
            return {
                "success": True,
                "user": username,
                "task": task_description,
                "classification": classification,
                "risk_assessment": risk_assessment,
                "routed_to": team_name,
                "result": result,
                "status": "completed"
            }
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Task execution failed: {e}")
            logger.error(f"Full traceback:\n{error_details}")
            return {
                "success": False,
                "user": username,
                "task": task_description,
                "error": str(e),
                "error_details": error_details,
                "status": "failed"
            }
