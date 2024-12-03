from axicontraves import BatchProcessor, ProviderConfig
import time
import signal
import sys
import random

def signal_handler(sig, frame):
    print("\nGracefully shutting down...")
    sys.exit(0)

def create_demo_messages():
    # Base questions with variations
    questions = [
        "Is water wet? Explain in one sentence.",
        "Can birds fly? Answer yes or no and why briefly.",
        "Do fish swim? Provide a short explanation.",
        "Is the sky blue? Answer in one brief sentence.",
        "Are plants alive? Give a quick answer.",
    ]
    
    # Add slight variations to make each question unique
    variations = [
        "Please answer:",
        "Tell me:",
        "I wonder:",
        "Quick question:",
        "Simple query:",
    ]
    
    question = random.choice(questions)
    variation = random.choice(variations)
    
    return [
        {"role": "system", "content": "You are a direct and concise assistant. Keep answers under 10 words."},
        {"role": "user", "content": f"{variation} {question}"}
    ]

def main():
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create requests with varied questions
    requests = [create_demo_messages() for _ in range(1000)]

    # Configure multiple providers
    providers = [
        ProviderConfig(
            name="openai",
            api_key="EMPTY",
            base_url="http://134.155.85.9:8080",
            config={
                "model": "",
                "temperature": 0.7,
                "max_tokens": 50
            },
            test_mode=False,
        ),
        ProviderConfig(
            name="openai",
            api_key="EMPTY",
            base_url="http://134.155.85.9:8081",
            config={
                "model": "",
                "temperature": 0.7,
                "max_tokens": 50
            },
            test_mode=False,
        ),
    ]
    
    processor = BatchProcessor(providers=providers)
    
    print(f"\nStarting batch processing of {len(requests)} requests...")
    print(f"Number of providers: {len(providers)}")
    for i, provider in enumerate(providers, 1):
        print(f"\nProvider {i}:")
        print(f"  Base URL: {provider.base_url}")
        print(f"  Model: {provider.config.get('model') or '<empty>'}")
        print(f"  Temperature: {provider.config['temperature']}")
        print(f"  Max tokens: {provider.config['max_tokens']}")
    print("\nProcessing...")
    
    try:
        start_time = time.time()
        result = processor.process_batch(requests)
        total_time = time.time() - start_time
        
        print(f"\nOverall Results:")
        print(f"Total Requests: {result.total_requests}")
        print(f"Total Tokens: {result.total_tokens}")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Requests/Second: {result.requests_per_second:.2f}")
        print(f"Tokens/Second: {result.tokens_per_second:.2f}")
        
        print("\nPer Provider Results:")
        for provider_name, provider_result in result.provider_metrics.items():
            print(f"\nProvider {provider_name}:")
            print(f"  Requests: {provider_result.total_requests}")
            print(f"  Tokens: {provider_result.total_tokens}")
            print(f"  Requests/Second: {provider_result.requests_per_second:.2f}")
            print(f"  Tokens/Second: {provider_result.tokens_per_second:.2f}")
            print(f"  Uplink: {provider_result.uplink_mbps:.2f} Mbps")
            print(f"  Downlink: {provider_result.downlink_mbps:.2f} Mbps")
            
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 