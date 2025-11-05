# verify_ollama_setup.py
# Diagnostic script to check Ollama performance and configuration

import requests
import time
import json
from loguru import logger

def check_ollama_running():
    """Check if Ollama is running"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info("✓ Ollama is running")
            return True, response.json()
        else:
            logger.error("✗ Ollama returned error")
            return False, None
    except Exception as e:
        logger.error(f"✗ Ollama is not running: {e}")
        return False, None

def test_model_speed(model_name: str, prompt: str = "Say hello"):
    """Test how fast a model responds"""
    logger.info(f"\nTesting {model_name} speed...")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✓ {model_name} responded in {elapsed:.2f} seconds")
            logger.info(f"  Response: {result.get('response', 'No response')[:100]}")
            
            # Warn if too slow
            if elapsed > 30:
                logger.warning(f"⚠️  Model is SLOW ({elapsed:.2f}s) - consider using smaller model")
            elif elapsed > 10:
                logger.warning(f"⚠️  Model is somewhat slow ({elapsed:.2f}s)")
            else:
                logger.info(f"✓ Model is FAST ({elapsed:.2f}s)")
            
            return True, elapsed
        else:
            logger.error(f"✗ Model returned error: {response.status_code}")
            return False, elapsed
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        logger.error(f"✗ Model TIMED OUT after {elapsed:.2f} seconds")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"✗ Error: {e}")
        return False, elapsed

def check_model_info(model_name: str):
    """Get model information"""
    try:
        response = requests.post(
            "http://localhost:11434/api/show",
            json={"name": model_name},
            timeout=10
        )
        
        if response.status_code == 200:
            info = response.json()
            logger.info(f"\nModel Info for {model_name}:")
            logger.info(f"  Parameters: {info.get('parameters', 'Unknown')}")
            logger.info(f"  Format: {info.get('format', 'Unknown')}")
            
            # Get size
            modelfile = info.get('modelfile', '')
            logger.info(f"  Modelfile preview: {modelfile[:200]}")
            
            return True
        else:
            logger.warning(f"⚠️  Could not get model info")
            return False
    except Exception as e:
        logger.error(f"✗ Error getting model info: {e}")
        return False

def recommend_settings(model_name: str, response_time: float):
    """Provide recommendations based on performance"""
    logger.info("\n" + "="*60)
    logger.info("RECOMMENDATIONS")
    logger.info("="*60)
    
    if response_time > 30:
        logger.warning("⚠️  CRITICAL: Model is too slow for real-time use")
        logger.info("\n  Immediate Actions:")
        logger.info("  1. Switch to smaller model:")
        logger.info("     ollama pull qwen2.5:7b  (7GB, fast)")
        logger.info("     ollama pull mistral:7b  (4GB, very fast)")
        logger.info("\n  2. Increase timeouts in AutoGen Studio:")
        logger.info("     'timeout': 300 in model config JSON")
        logger.info("\n  3. Pre-warm model:")
        logger.info(f"     ollama run {model_name} 'warmup' &")
    
    elif response_time > 10:
        logger.info("✓ Model speed is acceptable but could be improved")
        logger.info("\n  Optional Improvements:")
        logger.info("  1. Pre-load model to avoid cold starts:")
        logger.info(f"     ollama run {model_name} 'test' &")
        logger.info("\n  2. Adjust Ollama settings:")
        logger.info("     export OLLAMA_NUM_PARALLEL=1")
        logger.info("     export OLLAMA_MAX_LOADED_MODELS=1")
    
    else:
        logger.info("✓ Model speed is EXCELLENT - no changes needed!")
        logger.info("\n  Current settings are optimal")

def main():
    """Run full diagnostic"""
    logger.info("="*60)
    logger.info("OLLAMA SETUP VERIFICATION")
    logger.info("="*60)
    
    # Step 1: Check if Ollama is running
    running, tags_data = check_ollama_running()
    if not running:
        logger.error("\n✗ Ollama is not running!")
        logger.info("\nStart Ollama with: ollama serve")
        return
    
    # Step 2: List available models
    if tags_data:
        models = tags_data.get('models', [])
        logger.info(f"\n✓ Available models: {len(models)}")
        for model in models:
            name = model.get('name', 'Unknown')
            size = model.get('size', 0) / (1024**3)  # Convert to GB
            logger.info(f"  - {name} ({size:.1f} GB)")
    
    # Step 3: Test your current model
    logger.info("\n" + "="*60)
    logger.info("TESTING CURRENT MODEL: gpt-oss:120b-cloud")
    logger.info("="*60)
    
    success, response_time = test_model_speed("gpt-oss:120b-cloud", "Say hello in one sentence")
    
    if success:
        # Test with more complex prompt
        logger.info("\nTesting with complex prompt...")
        test_model_speed("gpt-oss:120b-cloud", "Explain what SQL is in 2 sentences")
    
    # Step 4: Get model info
    check_model_info("gpt-oss:120b-cloud")
    
    # Step 5: Recommendations
    if success:
        recommend_settings("gpt-oss:120b-cloud", response_time)
    
    # Step 6: Test alternative models if available
    logger.info("\n" + "="*60)
    logger.info("TESTING ALTERNATIVE MODELS")
    logger.info("="*60)
    
    alternative_models = ["qwen2.5:7b", "mistral:7b", "llama3.1:8b"]
    
    for model in alternative_models:
        if any(m.get('name', '').startswith(model.split(':')[0]) for m in models):
            test_model_speed(model, "Hello")
        else:
            logger.info(f"\n⊘ {model} not installed")
            logger.info(f"  Install with: ollama pull {model}")
    
    logger.info("\n" + "="*60)
    logger.info("DIAGNOSTIC COMPLETE")
    logger.info("="*60)

if __name__ == "__main__":
    main()
