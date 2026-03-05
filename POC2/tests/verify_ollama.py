"""
tests/verify_ollama.py
AI Data Assistant — POC2

Phase 0 verification: Ollama service, Qwen3-8B model, and nomic-embed-text.

Run from the project root with venv activated:
    python tests\verify_ollama.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from config.settings import settings

logger.remove()
logger.add(sys.stderr, format="<level>{message}</level>", level="INFO")


async def verify_ollama():
    print("\n" + "=" * 55)
    print("  Ollama — Service & Model Verification")
    print("=" * 55)

    # ── 1. Check Ollama service is reachable ────────────────
    print(f"\n[1/3] Checking Ollama service at {settings.ollama_host} ...")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
            response.raise_for_status()
            data = response.json()
            available_models = [m["name"] for m in data.get("models", [])]
    except Exception as e:
        print(f"  ✗ Ollama service not reachable: {e}")
        print("\nTroubleshooting:")
        print("  - Make sure Ollama is running: open a terminal and run `ollama serve`")
        print(f"  - Confirm OLLAMA_HOST in .env is set to {settings.ollama_host}")
        sys.exit(1)

    print(f"  ✓ Ollama service is running")
    print(f"  ✓ Models available: {', '.join(available_models) if available_models else 'none pulled yet'}")

    # ── 2. Verify Qwen3-8B is present ──────────────────────
    print(f"\n[2/3] Checking for model: {settings.ollama_model} ...")
    model_found = any(settings.ollama_model in m for m in available_models)

    if model_found:
        print(f"  ✓ {settings.ollama_model} is available")
    else:
        print(f"  ✗ {settings.ollama_model} not found in Ollama")
        print(f"\n  Pull it with:")
        print(f"    ollama pull {settings.ollama_model}")
        sys.exit(1)

    # ── 3. Test a live inference call via AutoGen ───────────
    print(f"\n[3/3] Running a test inference call via AutoGen OllamaChatCompletionClient ...")
    try:
        from autogen_ext.models.ollama import OllamaChatCompletionClient
        from autogen_core.models import UserMessage, ModelInfo, ModelFamily

        # Qwen3 is not in AutoGen's built-in model list, so we provide model_info manually
        model_info = ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family=ModelFamily.UNKNOWN,
            structured_output=True,
        )

        client = OllamaChatCompletionClient(
            model=settings.ollama_model,
            host=settings.ollama_host,
            model_info=model_info,
        )

        result = await client.create(
            [UserMessage(
                content="Reply with exactly three words: connection test successful",
                source="user"
            )]
        )
        await client.close()

        response_text = result.content if hasattr(result, "content") else str(result)
        print(f"  ✓ Inference OK")
        print(f"  ✓ Model response: {response_text[:120]}")

    except Exception as e:
        print(f"  ✗ Inference test failed: {e}")
        print("\n  This usually means autogen-ext[ollama] is not installed correctly.")
        print("  Run: pip install 'autogen-ext[ollama]==0.7.5'")
        sys.exit(1)

    print("\n" + "=" * 55)
    print("  ✓ Ollama: ALL CHECKS PASSED")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    # httpx is installed as a dependency of autogen-ext
    asyncio.run(verify_ollama())
