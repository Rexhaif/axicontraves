import pytest
from axicontraves import (
    LLMBatchProcessor,
    BatchRequestResult,
    Message,
    OpenAIConfig,
    AnthropicConfig,
)
import time

def create_chat_messages(content: str) -> list[Message]:
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": content}
    ]

def test_openai_batch_processing():
    config: OpenAIConfig = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    processor = LLMBatchProcessor("openai", "dummy-key", config, test_mode=True)
    requests = [create_chat_messages("Hello, world!")] * 5
    
    result = processor.process_batch(requests, show_progress=False)
    
    assert isinstance(result, BatchRequestResult)
    assert result.total_requests == 5
    assert result.requests_per_second > 0
    assert result.tokens_per_second > 0
    assert len(result.metrics) == 5
    
    for metric in result.metrics:
        assert metric.completion_tokens > 0
        assert metric.prompt_tokens > 0
        assert metric.total_tokens == metric.completion_tokens + metric.prompt_tokens
        assert metric.request_time > 0

def test_rate_limiting():
    config: OpenAIConfig = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    # Create a processor with a very low rate limit (1000 tokens per minute)
    processor = LLMBatchProcessor(
        provider="openai",
        api_key="dummy-key",
        config=config,
        test_mode=True,
        tokens_per_minute=1000
    )
    
    # Create 5 requests that should generate about 100 tokens each
    requests = [create_chat_messages("Test request.")] * 5
    
    start_time = time.time()
    result = processor.process_batch(requests, show_progress=False)
    elapsed_time = time.time() - start_time
    
    total_tokens = sum(m.total_tokens for m in result.metrics)
    tokens_per_minute = total_tokens / (elapsed_time / 60)
    
    # Allow for some margin in rate limiting (±20%)
    assert tokens_per_minute <= 1200, f"Rate limit exceeded: {tokens_per_minute:.0f} tokens/minute"
    assert tokens_per_minute >= 800, f"Rate too low: {tokens_per_minute:.0f} tokens/minute"

def test_rate_limiting_small_requests():
    config: OpenAIConfig = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    # Set a rate limit of 600 tokens per minute (10 tokens per second)
    processor = LLMBatchProcessor(
        provider="openai",
        api_key="dummy-key",
        config=config,
        test_mode=True,
        tokens_per_minute=600
    )
    
    # Create 3 small requests
    requests = [create_chat_messages("Short response.")] * 3
    
    start_time = time.time()
    result = processor.process_batch(requests, show_progress=False)
    elapsed_time = time.time() - start_time
    
    total_tokens = sum(m.total_tokens for m in result.metrics)
    tokens_per_minute = total_tokens / (elapsed_time / 60)
    
    assert tokens_per_minute <= 700, f"Rate limit exceeded: {tokens_per_minute:.0f} tokens/minute"
    assert tokens_per_minute >= 500, f"Rate too low: {tokens_per_minute:.0f} tokens/minute"

def test_rate_limiting_burst():
    config: OpenAIConfig = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    # Set a rate limit of 1200 tokens per minute (20 tokens per second)
    processor = LLMBatchProcessor(
        provider="openai",
        api_key="dummy-key",
        config=config,
        test_mode=True,
        tokens_per_minute=1200
    )
    
    # Create 3 bursts of requests with pauses
    results = []
    for _ in range(3):
        requests = [create_chat_messages("Burst request.")] * 3
        result = processor.process_batch(requests, show_progress=False)
        results.append(result)
        time.sleep(1)  # Wait for token bucket to refill
    
    # Check that all bursts were processed
    assert all(r.total_requests == 3 for r in results)
    
    # Check that token counts are consistent
    token_counts = [sum(m.total_tokens for m in r.metrics) for r in results]
    assert max(token_counts) - min(token_counts) < 50  # Allow small variation

def test_default_config():
    processor = LLMBatchProcessor("openai", "dummy-key", test_mode=True)
    assert processor.config["model"] == "gpt-3.5-turbo"
    assert processor.config["temperature"] == 0.7
    
    processor = LLMBatchProcessor("anthropic", "dummy-key", test_mode=True)
    assert processor.config["model"] == "claude-3-opus-20240229"
    assert processor.config["temperature"] == 0.7

def test_custom_progress_callback():
    progress_calls = []
    
    def progress_callback(completed: int, total: int):
        progress_calls.append((completed, total))
    
    processor = LLMBatchProcessor(
        "openai",
        "dummy-key",
        progress_callback=progress_callback,
        test_mode=True
    )
    
    requests = [create_chat_messages("Test")] * 10
    result = processor.process_batch(requests, show_progress=False)
    
    assert len(progress_calls) > 0
    assert progress_calls[-1][0] == 10  # Last call should show all completed
    assert progress_calls[-1][1] == 10  # Total should match request count

def test_invalid_provider():
    with pytest.raises(ValueError):
        LLMBatchProcessor("invalid", "dummy-key", test_mode=True)