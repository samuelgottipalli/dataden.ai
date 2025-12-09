# ============================================================
# PHASE 1: INTERACTIVE AGENT RESPONSES
# Enhanced Orchestrator with User Question/Answer Capability
# ============================================================

import asyncio
import uuid
import re
from typing import Optional, Dict, AsyncIterator, Any
from datetime import datetime
from loguru import logger

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import MagenticOneGroupChat, RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient

from config.settings import settings
from mcp_server.tools import generate_and_execute_sql, analyze_data_pandas
from mcp_server.database import db

from utils.model_manager import model_manager


class EnhancedAgentOrchestrator:
    """
    Phase 1: Interactive Agent Orchestrator

    New Features:
    - Agents can ask users clarifying questions
    - Conversation pause/resume capability
    - Question detection and parsing
    - State preservation between turns
    """

    def __init__(self):
        # Use model manager for automatic fallback
        self.model_client = model_manager.get_model_client()

        # Phase 1: User interaction state
        self.pending_questions: Dict[str, Dict] = {}  # conversation_id -> question data
        self.conversation_states: Dict[str, Dict] = {}  # conversation_id -> agent state

        logger.info(
            f"✨ Phase 1 Interactive Orchestrator initialized with model: {settings.ollama_model}"
        )

    # ============================================================
    # PHASE 1: QUESTION DETECTION & PARSING
    # ============================================================

    def _detect_user_question(self, message_content: str) -> Dict[str, Any]:
        """
        Detect if agent message contains a user question

        Agents use this format:
        [NEED_USER_INPUT]
        Question: What do you need clarification on?
        Options:
        1. Option one
        2. Option two
        3. Option three
        Context: Why I need this information
        [/NEED_USER_INPUT]

        Returns:
            dict with keys: is_question, question, options, context
        """

        if "[NEED_USER_INPUT]" not in str(message_content):
            return {"is_question": False}

        try:
            content_str = str(message_content)
            start = content_str.find("[NEED_USER_INPUT]") + len("[NEED_USER_INPUT]")
            end = content_str.find("[/NEED_USER_INPUT]")

            if end == -1:
                return {"is_question": False}

            question_block = content_str[start:end].strip()

            # Parse the structured question
            lines = question_block.split("\n")
            question = ""
            options = []
            context = ""
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("Question:"):
                    question = line.replace("Question:", "").strip()
                elif line.startswith("Options:"):
                    current_section = "options"
                elif line.startswith("Context:"):
                    current_section = "context"
                elif current_section == "options":
                    # Remove numbering if present (1. 2. etc)
                    option = re.sub(r"^\d+\.\s*", "", line).strip()
                    if option:
                        options.append(option)
                elif current_section == "context":
                    context += line + " "

            return {
                "is_question": True,
                "question": question,
                "options": options,
                "context": context.strip(),
            }

        except Exception as e:
            logger.error(f"Failed to parse user question: {e}")
            return {"is_question": False}

    def _format_question_for_user(self, question_data: Dict) -> str:
        """
        Format question for display to user

        Makes it look nice in OpenWebUI
        """

        question = question_data.get("question", "I need more information")
        options = question_data.get("options", [])
        context = question_data.get("context", "")

        formatted = f"🤔 **I need clarification:**\n\n{question}\n\n"

        if options:
            formatted += "**Please choose:**\n"
            for i, opt in enumerate(options, 1):
                formatted += f"{i}. {opt}\n"
            formatted += "\n*You can respond with the number or describe your choice*"

        if context:
            formatted += f"\n\n💡 *{context}*"

        return formatted

    # ============================================================
    # PHASE 1: CONVERSATION STATE MANAGEMENT
    # ============================================================

    def _save_conversation_state(
        self,
        conversation_id: str,
        original_task: str,
        current_context: Dict,
        agent_state: Optional[Dict] = None,
    ):
        """
        Save conversation state when pausing for user input
        """

        self.conversation_states[conversation_id] = {
            "original_task": original_task,
            "context": current_context,
            "agent_state": agent_state or {},
            "timestamp": datetime.now().isoformat(),
            "status": "waiting_for_user",
        }

        logger.info(f"💾 Saved conversation state for {conversation_id}")

    def _get_conversation_state(self, conversation_id: str) -> Optional[Dict]:
        """
        Retrieve saved conversation state
        """

        return self.conversation_states.get(conversation_id)

    def _clear_conversation_state(self, conversation_id: str):
        """
        Clear conversation state after completion
        """

        if conversation_id in self.conversation_states:
            del self.conversation_states[conversation_id]
        if conversation_id in self.pending_questions:
            del self.pending_questions[conversation_id]

        logger.info(f"🧹 Cleared conversation state for {conversation_id}")

    # ============================================================
    # PHASE 1: SUPERVISOR AGENT (with question support)
    # ============================================================

    async def create_supervisor_agent(self) -> AssistantAgent:
        """
        Supervisor Agent with clarification capabilities
        """

        supervisor = AssistantAgent(
            name="SupervisorAgent",
            model_client=self.model_client,
            system_message="""You are the Supervisor and Task Router.

**Your role:**
1. Analyze user requests
2. Route to appropriate team
3. Ask for clarification if request is ambiguous

**Available Teams:**

1. **DATA_ANALYSIS_TEAM** - For database queries and analysis
   Examples: "Show sales", "Analyze revenue", "Query customers"
   
2. **GENERAL_ASSISTANT_TEAM** - For simple tasks
   Examples: "What's 15% of 850?", "Convert units", "Explain concept"

**When to ask for clarification:**
- Request is too vague ("show me data" - which data?)
- Multiple valid interpretations
- Missing critical parameters

**How to ask (use this exact format):**
```
[NEED_USER_INPUT]
Question: What specifically do you need?
Options:
1. Sales data
2. Customer data
3. Product data
Context: Your request matches multiple data types
[/NEED_USER_INPUT]
```

**Otherwise:** Route directly with clear reasoning.

Format: [ROUTE:TEAM_NAME] Brief explanation
""",
        )

        return supervisor

    # ============================================================
    # PHASE 1: DATA ANALYSIS TEAM (with question support)
    # ============================================================

    async def create_data_analysis_team(self) -> MagenticOneGroupChat:
        """
        Data Analysis Team with interactive questioning
        """

        # Create tool wrappers from actual functions
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

        async def list_all_tables_wrapper() -> dict:
            """List all tables in the database"""
            logger.info("List tables tool called")
            # Query information schema for all tables
            result = await generate_and_execute_sql(
                "List all tables",
                """
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_SCHEMA, TABLE_NAME
                """,
            )
            return result

        # SQL Agent - NOW with clarification capability
        sql_agent = AssistantAgent(
            name="SQLAgent",
            model_client=self.model_client,
            tools=[sql_tool_wrapper, get_table_schema_wrapper, list_all_tables_wrapper],
            system_message="""You are a SQL expert with DIRECT ACCESS to a connected MS SQL Server database.

🔴 YOU ARE ALREADY CONNECTED - DO NOT ASK FOR CONNECTION INFO!

**Your Connected Database:**
✅ MS SQL Server (AdventureWorksDW) - ACTIVE CONNECTION
✅ Three tools ready to use RIGHT NOW:
  1. list_all_tables_wrapper - See all available tables
  2. get_table_schema_wrapper(table) - View table structure  
  3. sql_tool_wrapper(desc, sql) - Execute queries

**CORRECT Workflow:**
User: "Show me sales data"
YOU:
  Step 1: Call list_all_tables_wrapper (discover tables)
  Step 2: Call get_table_schema_wrapper on relevant table
  Step 3: Execute SELECT query
  Step 4: Return results

**❌ NEVER Ask For:**
- Database connection information
- What tables exist (use list_all_tables_wrapper!)
- Column names (use get_table_schema_wrapper!)
- Credentials or access

**✅ You MAY Ask About:**
- Which specific table if multiple match (e.g., "sales.monthly vs sales.transactions?")
- What time period to query
- What filters to apply
- What specific analysis needed

**Interactive Questions Format:**
When you need clarification about WHICH data to query:
```
[NEED_USER_INPUT]
Question: I found 3 sales tables. Which one?
Options:
1. FactInternetSales (online sales)
2. FactResellerSales (B2B sales)
3. FactSalesQuota (sales targets)
Context: Need to know which dataset to analyze
[/NEED_USER_INPUT]
```

**Safety:**
- NEVER use: DROP, DELETE, TRUNCATE, ALTER
- Always use SELECT TOP 100 for exploration
- Use [schema].[table] format

**Example CORRECT behavior:**
User: "Show sales"
YOU: [Calls list_all_tables_wrapper] → Sees FactInternetSales
YOU: [Calls get_table_schema_wrapper('FactInternetSales')] → Sees columns
YOU: [Executes] SELECT TOP 100 * FROM [dbo].[FactInternetSales]
YOU: Returns results with summary

**Example WRONG behavior:**
User: "Show sales"  
YOU: 🚫 "Please provide database connection details..." ← NEVER DO THIS!

Remember: Database is CONNECTED. Use your tools to explore and query!
""",
        )

        # Analysis Agent
        analysis_agent = AssistantAgent(
            name="AnalysisAgent",
            model_client=self.model_client,
            tools=[data_analysis_tool_wrapper],
            system_message="""You are a data analyst.

Analyze results from SQLAgent and provide insights.

If data is unclear or incomplete, you can also ask questions using:
[NEED_USER_INPUT]
Question: [question]
Options: [options if applicable]
Context: [context]
[/NEED_USER_INPUT]

Focus on: trends, patterns, anomalies, key metrics.
""",
        )

        # Validation Agent
        validation_agent = AssistantAgent(
            name="ValidationAgent",
            model_client=self.model_client,
            system_message="""You are a validation specialist.

Review SQL queries for safety and correctness.

If you find issues that need user clarification, ask questions using:
[NEED_USER_INPUT]
Question: [question]
Options: [options if applicable]
Context: [context]
[/NEED_USER_INPUT]

Approve only safe queries. Reject dangerous operations.
""",
        )

        team = MagenticOneGroupChat(
            participants=[sql_agent, analysis_agent, validation_agent],
            model_client=self.model_client,
            max_turns=20,
        )

        return team

    # ============================================================
    # PHASE 1: GENERAL ASSISTANT TEAM
    # ============================================================

    async def create_general_assistant_team(self) -> RoundRobinGroupChat:
        """
        General Assistant Team for simple tasks
        """

        assistant = AssistantAgent(
            name="GeneralAssistant",
            model_client=self.model_client,
            system_message="""You are a helpful general assistant.

Handle: math, conversions, explanations, general knowledge.

If you need clarification, ask using:
[NEED_USER_INPUT]
Question: [question]
Options: [options if applicable]
Context: [context]
[/NEED_USER_INPUT]

Be concise and accurate.
""",
        )

        team = RoundRobinGroupChat(
            participants=[assistant],
            max_turns=3,
        )

        return team

    # ============================================================
    # PHASE 1: INTERACTIVE EXECUTION WITH STREAMING
    # ============================================================

    async def execute_with_interactive_streaming(
        self,
        task_description: str,
        username: str = "system",
        conversation_id: Optional[str] = None,
        user_response: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute task with interactive question/answer capability

        Args:
            task_description: User's request
            username: User identifier
            conversation_id: Unique conversation ID (generated if None)
            user_response: User's answer to previous question (if resuming)

        Yields:
            Events including regular messages and user_question events
        """

        # Generate conversation ID if new conversation
        if conversation_id is None:
            conversation_id = f"conv-{uuid.uuid4()}"

        logger.info(f"🎬 Interactive execution started: {conversation_id}")
        logger.info(f"Task: {task_description[:100]}...")

        try:
            # Check if resuming from previous question
            if user_response:
                state = self._get_conversation_state(conversation_id)
                if state:
                    logger.info(
                        f"▶️ Resuming conversation with user response: {user_response}"
                    )

                    # Yield acknowledgment
                    yield {
                        "agent": "System",
                        "type": "user_response",
                        "content": f"✅ Got it: {user_response}",
                        "timestamp": datetime.now().isoformat(),
                        "conversation_id": conversation_id,
                    }

                    # Continue with original task + user response context
                    task_with_context = f"{state['original_task']}\n\nUser clarification: {user_response}"

                    # Clear the pending question
                    if conversation_id in self.pending_questions:
                        del self.pending_questions[conversation_id]

                    # Re-execute with context
                    async for event in self._execute_task_stream(
                        task_with_context, username, conversation_id
                    ):
                        yield event

                    # Clear state on completion
                    self._clear_conversation_state(conversation_id)
                    return

            # New execution
            async for event in self._execute_task_stream(
                task_description, username, conversation_id
            ):
                yield event

        except Exception as e:
            logger.error(f"Execution error: {e}")

            # Try to handle as rate limit
            if self._handle_model_error(e):
                # Notify user
                yield {
                    "agent": "System",
                    "type": "warning",
                    "content": "⚠️ Primary model rate limit reached. Switching to local model. Response may be slower.",
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id,
                }

                # Retry with fallback
                async for event in self._execute_task_stream(task_description, username, conversation_id):
                    yield event
            else:
                # Not rate limit - raise original error
                yield {
                    "agent": "System",
                    "type": "error",
                    "content": f"❌ Error: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id,
                }


    def _handle_model_error(self, error: Exception) -> bool:
        """
        Check for rate limit and switch models if needed
        
        Returns True if handled, False if unknown error
        """
        from utils.model_manager import model_manager

        error_str = str(error)

        # Check if rate limit
        if model_manager.handle_model_failure(error_str):
            logger.warning(f"⚠️ Switching to fallback model due to rate limit")
            # Update our client to use fallback
            self.model_client = model_manager.get_model_client()
            return True

        return False

    async def _execute_task_stream(
        self, task_description: str, username: str, conversation_id: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Internal streaming execution with question detection
        """

        try:
            # Step 1: Routing
            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": "🎯 Analyzing your request...",
                "timestamp": datetime.now().isoformat(),
                "conversation_id": conversation_id,
            }

            # Determine team
            supervisor = await self.create_supervisor_agent()

            # Simple classification for Phase 1
            task_lower = task_description.lower()
            if any(
                kw in task_lower
                for kw in [
                    "database",
                    "sql",
                    "query",
                    "table",
                    "show",
                    "list",
                    "analyze data",
                    "sales",
                    "customer",
                    "revenue",
                ]
            ):
                team_name = "DATA_ANALYSIS_TEAM"
                team = await self.create_data_analysis_team()
            else:
                team_name = "GENERAL_ASSISTANT_TEAM"
                team = await self.create_general_assistant_team()

            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": f"📍 Routing to: **{team_name}**",
                "timestamp": datetime.now().isoformat(),
                "conversation_id": conversation_id,
            }

            # Step 2: Execute with team and monitor for questions
            messages_buffer = []

            # Check if team has run_stream
            if hasattr(team, "run_stream"):
                async for message in team.run_stream(task=task_description):
                    messages_buffer.append(message)

                    # Check for user questions in agent messages
                    if hasattr(message, "content"):
                        content = message.content
                        question_data = self._detect_user_question(content)

                        if question_data["is_question"]:
                            # Agent is asking a question!
                            logger.info(
                                f"❓ Agent asked a question: {question_data['question']}"
                            )

                            # Save state
                            self._save_conversation_state(
                                conversation_id,
                                task_description,
                                {"messages": messages_buffer},
                                {},
                            )

                            # Store question
                            self.pending_questions[conversation_id] = {
                                "question": question_data,
                                "timestamp": datetime.now().isoformat(),
                            }

                            # Yield user_question event
                            yield {
                                "agent": getattr(message, "source", "Agent"),
                                "type": "user_question",
                                "content": self._format_question_for_user(
                                    question_data
                                ),
                                "question_data": question_data,
                                "timestamp": datetime.now().isoformat(),
                                "conversation_id": conversation_id,
                            }

                            # Stop execution - wait for user response
                            return

                    # Regular message - stream it
                    yield self._format_message_for_streaming(message, conversation_id)

            else:
                # Fallback if run_stream not available
                logger.warning("Team doesn't support run_stream, using fallback")
                yield {
                    "agent": team_name,
                    "type": "thinking",
                    "content": "Processing your request...",
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id,
                }

                # Execute without streaming
                result = await team.run(task=task_description)

                # Check final result for questions
                if hasattr(result, "messages") and result.messages:
                    last_message = result.messages[-1]
                    if hasattr(last_message, "content"):
                        question_data = self._detect_user_question(last_message.content)

                        if question_data["is_question"]:
                            # Save and yield question
                            self._save_conversation_state(
                                conversation_id,
                                task_description,
                                {"result": result},
                                {},
                            )

                            self.pending_questions[conversation_id] = {
                                "question": question_data,
                                "timestamp": datetime.now().isoformat(),
                            }

                            yield {
                                "agent": "Agent",
                                "type": "user_question",
                                "content": self._format_question_for_user(
                                    question_data
                                ),
                                "question_data": question_data,
                                "timestamp": datetime.now().isoformat(),
                                "conversation_id": conversation_id,
                            }
                            return

                # No question - show final result
                content = self._extract_clean_content(result)
                yield {
                    "agent": team_name,
                    "type": "final",
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id,
                }

            # Done - clear state
            self._clear_conversation_state(conversation_id)

        except Exception as e:
            logger.error(f"Task stream failed: {e}")
            logger.exception("Full traceback:")
            raise

    def _format_message_for_streaming(
        self, message: Any, conversation_id: str
    ) -> Dict[str, Any]:
        """
        Format agent message for streaming
        """

        agent_name = getattr(message, "source", "Agent")
        content = getattr(message, "content", str(message))

        # Clean content
        clean_content = self._extract_clean_content(content)

        # Classify message type
        msg_type = self._classify_message_type(agent_name, clean_content)

        return {
            "agent": agent_name,
            "type": msg_type,
            "content": clean_content,
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id,
        }

    def _extract_clean_content(self, content: Any) -> str:
        """
        Extract clean text from message content
        """

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Extract text from list of message parts
            texts = []
            for item in content:
                if isinstance(item, str):
                    texts.append(item)
                elif hasattr(item, "content"):
                    texts.append(str(item.content))
                elif hasattr(item, "text"):
                    texts.append(str(item.text))
                else:
                    texts.append(str(item))
            return " ".join(texts)
        else:
            return str(content)

    def _classify_message_type(self, agent: str, content: str) -> str:
        """
        Classify message type for formatting
        """

        content_lower = content.lower()
        agent_lower = agent.lower()

        # Check for questions
        if "[NEED_USER_INPUT]" in content:
            return "user_question"

        # Tool-related
        if "tool" in content_lower or "function" in content_lower:
            if "call" in content_lower:
                return "action"
            elif "result" in content_lower:
                return "tool_result"

        # SQL-related
        if "select" in content_lower or "from" in content_lower:
            return "action"

        # Agent-specific
        if "validation" in agent_lower:
            return "validation"
        if "analysis" in agent_lower:
            return "analysis"

        # Thinking
        if any(word in content_lower for word in ["i will", "let me", "i need to"]):
            return "thinking"

        # Error
        if "error" in content_lower or "failed" in content_lower:
            return "error"

        return "message"


# ============================================================
# TESTING
# ============================================================


async def test_interactive_phase1():
    """
    Test Phase 1 interactive functionality
    """

    print("=" * 60)
    print("PHASE 1: TESTING INTERACTIVE AGENTS")
    print("=" * 60)

    orchestrator = EnhancedAgentOrchestrator()

    # Test 1: Ambiguous request that should trigger question
    print("\n[Test 1] Ambiguous request (should ask question)")
    print("-" * 60)

    conversation_id = None
    async for event in orchestrator.execute_with_interactive_streaming(
        "Show me sales data", "test_user"
    ):
        agent = event.get("agent", "Unknown")
        msg_type = event.get("type", "message")
        content = event.get("content", "")
        conversation_id = event.get("conversation_id")

        print(f"[{agent}] ({msg_type}): {content[:150]}...")

        if msg_type == "user_question":
            print("\n✅ SUCCESS! Agent asked a question!")
            print("Conversation paused, waiting for user response")
            break

    # Test 2: Resume with user response
    if conversation_id:
        print("\n[Test 2] Resuming with user answer")
        print("-" * 60)

        async for event in orchestrator.execute_with_interactive_streaming(
            "Show me sales data",  # Original task
            "test_user",
            conversation_id=conversation_id,
            user_response="monthly_summary table",
        ):
            agent = event.get("agent", "Unknown")
            msg_type = event.get("type", "message")
            content = event.get("content", "")

            print(f"[{agent}] ({msg_type}): {content[:150]}...")

    print("\n" + "=" * 60)
    print("Phase 1 test complete!")


if __name__ == "__main__":
    asyncio.run(test_interactive_phase1())
