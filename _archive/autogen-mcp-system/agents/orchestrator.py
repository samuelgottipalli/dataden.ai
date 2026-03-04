import asyncio
from typing import Optional
from loguru import logger
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_ext.models.ollama import OllamaChatCompletionClient
from config.settings import settings
from mcp_server.tools import generate_and_execute_sql, analyze_data_pandas
from mcp_server.database import db


class AgentOrchestrator:
    """
    Orchestrates AutoGen 2 agents with Ollama LLM
    Manages SQL generation, data analysis, and validation

    SIMPLIFIED VERSION: Direct tool integration without MCP protocol
    """

    def __init__(self):
        self.model_client = OllamaChatCompletionClient(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.7,
            max_tokens=2000,
            model_info=settings.ollama_model_info,
        )
        logger.info(f"Initialized Ollama client with model: {settings.ollama_model}")

    async def setup_agents(self) -> MagenticOneGroupChat:
        """
        Create and configure the agent team with direct tool integration

        Returns:
            team: MagenticOneGroupChat instance
        """

        # Define tools as async functions
        async def sql_tool_wrapper(query_description: str, sql_script: str) -> dict:
            """Execute SQL query against data warehouse with retry logic"""
            return await generate_and_execute_sql(query_description, sql_script)

        async def data_analysis_tool_wrapper(
            data_json: str, analysis_type: str
        ) -> dict:
            """Analyze retrieved data using pandas"""
            return await analyze_data_pandas(data_json, analysis_type)

        async def get_table_schema_wrapper(table_name: str) -> dict:
            """Get schema information for a specific table"""
            logger.info(f"Schema tool called for table: {table_name}")
            return db.get_table_schema(table_name)

        # SQL Generation & Execution Agent
        sql_agent = AssistantAgent(
            name="SQLAgent",
            model_client=self.model_client,
            tools=[sql_tool_wrapper, get_table_schema_wrapper],
            system_message="""You are an expert SQL developer for Microsoft SQL Server.

Your responsibilities:
1. Understand natural language requests for data
2. Generate accurate, optimized SQL queries
3. Use the sql_tool_wrapper to execute queries against the data warehouse
4. Handle errors gracefully and provide clear feedback
5. Never execute DROP, DELETE, TRUNCATE, or ALTER commands
6. Always retrieve table schemas before writing queries using get_table_schema_wrapper
7. Explain your SQL logic to the team

When retrieving data:
- Use SELECT TOP for initial data exploration
- Request table schema via get_table_schema_wrapper tool if needed
- Report row counts and data types
- Pass results to AnalysisAgent for further processing""",
        )

        # Data Analysis Agent
        analysis_agent = AssistantAgent(
            name="AnalysisAgent",
            model_client=self.model_client,
            tools=[data_analysis_tool_wrapper],
            system_message="""You are a data analyst and data scientist.

Your responsibilities:
1. Receive data retrieved by SQLAgent
2. Perform statistical analysis using the data_analysis_tool_wrapper
3. Identify trends, patterns, and anomalies
4. Calculate key metrics and aggregations
5. Create meaningful insights from raw data
6. Provide clear, actionable recommendations
7. Highlight any data quality issues

Analysis types you can perform:
- Summary: Basic statistics, null values, duplicates
- Correlation: Correlation matrices for numeric data
- Trend: Time-series analysis if dates are present

Always validate your findings and explain methodology to ValidationAgent.""",
        )

        # Validation & Quality Assurance Agent
        validation_agent = AssistantAgent(
            name="ValidationAgent",
            model_client=self.model_client,
            system_message="""You are a quality assurance specialist and data validator.

Your responsibilities:
1. Review SQL queries for accuracy and safety
2. Validate data analysis results
3. Check for logical inconsistencies
4. Verify data meets business requirements
5. Ensure all steps were executed correctly
6. Approve or request corrections

Validation checklist:
□ SQL query syntax is correct for MS SQL Server
□ No dangerous operations (DROP, DELETE, etc)
□ Data retrieved matches the request
□ Analysis methodology is sound
□ Results are logically consistent
□ Findings support the conclusions
□ All assumptions are documented

Approval process:
- If everything checks out: Approve and summarize findings
- If issues found: Request specific corrections
- Escalate complex issues to human team lead""",
        )

        # Create Magentic Team for group chat
        team = MagenticOneGroupChat(
            participants=[sql_agent, analysis_agent, validation_agent],
            model_client=self.model_client,
            max_turns=15,  # Limit conversation turns to prevent infinite loops
        )

        logger.info("Agent team successfully configured")
        return team

    async def execute_task(
        self, task_description: str, username: str = "system"
    ) -> dict:
        """
        Execute a data analysis task using the agent team

        Args:
            task_description: Natural language description of the task
            username: User requesting the analysis (for audit logging)

        Returns:
            Dictionary with task results and agent communications
        """

        try:
            logger.info(f"Starting task execution for user: {username}")
            logger.info(f"Task: {task_description}")

            # Setup agents
            team = await self.setup_agents()

            # Execute the team
            result = await team.run(task=task_description)

            logger.info(f"Task completed successfully for user: {username}")

            return {
                "success": True,
                "user": username,
                "task": task_description,
                "result": result,
                "status": "completed",
            }

        except asyncio.TimeoutError:
            logger.error("Task execution timed out")
            return {
                "success": False,
                "user": username,
                "task": task_description,
                "error": "Task execution timed out",
                "status": "timeout",
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
                "status": "failed",
            }
