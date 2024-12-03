from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable, Union
from rich.progress import Progress, BarColumn, TimeRemainingColumn
from rich.console import Console
import time
from .axicontraves import process_requests_multi, RequestMetrics

Message = Dict[str, str]

@dataclass
class ProviderConfig:
    name: str
    api_key: str
    config: Dict[str, Any]
    base_url: Optional[str] = None
    tokens_per_minute: Optional[int] = None
    test_mode: bool = False

@dataclass
class BatchRequestResult:
    total_requests: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_time: float
    metrics: List[RequestMetrics]
    total_request_bytes: int
    total_response_bytes: int
    provider_metrics: Dict[str, 'BatchRequestResult']

    @property
    def requests_per_second(self) -> float:
        return self.total_requests / self.total_time if self.total_time > 0 else 0

    @property
    def tokens_per_second(self) -> float:
        return self.total_tokens / self.total_time if self.total_time > 0 else 0
    
    @property
    def prompt_tokens_per_second(self) -> float:
        return self.prompt_tokens / self.total_time if self.total_time > 0 else 0
    
    @property
    def completion_tokens_per_second(self) -> float:
        return self.completion_tokens / self.total_time if self.total_time > 0 else 0
    
    @property
    def uplink_mbps(self) -> float:
        return (self.total_request_bytes * 8) / (self.total_time * 1_000_000) if self.total_time > 0 else 0
    
    @property
    def downlink_mbps(self) -> float:
        return (self.total_response_bytes * 8) / (self.total_time * 1_000_000) if self.total_time > 0 else 0

class BatchProcessor:
    def __init__(self, providers: Union[ProviderConfig, List[ProviderConfig]], progress_callback: Optional[Callable[[int, int], None]] = None):
        self.providers = [providers] if isinstance(providers, ProviderConfig) else providers
        self._progress_callback = progress_callback

    def process_batch(self, requests: List[List[Message]], show_progress: bool = True) -> BatchRequestResult:
        console = Console()
        start_time = time.time()
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        total_request_bytes = 0
        total_response_bytes = 0

        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            "{task.completed}/{task.total}",
            "•",
            TimeRemainingColumn(),
            "•",
            "[cyan]↑{task.fields[prompt_rate]:.0f}[/cyan]/[green]↓{task.fields[completion_rate]:.0f}[/green] tok/s",
            "•",
            "[yellow]↑{task.fields[uplink]:.2f}[/yellow]/[blue]↓{task.fields[downlink]:.2f}[/blue] Mbps",
            "•",
            "[magenta]{task.fields[threads]} threads",
            "•",
            "[red]{task.fields[providers]} providers",
            console=console,
            disable=not show_progress,
            expand=True
        ) as progress:
            task = progress.add_task(
                "[cyan]Processing batch requests...",
                total=len(requests),
                prompt_rate=0.0,
                completion_rate=0.0,
                uplink=0.0,
                downlink=0.0,
                threads=0,
                providers=len(self.providers)
            )

            def update_progress(completed: int, total: int, new_prompt_tokens: int, new_completion_tokens: int, new_request_bytes: int, new_response_bytes: int, thread_count: int):
                nonlocal total_tokens, prompt_tokens, completion_tokens, total_request_bytes, total_response_bytes
                prompt_tokens += new_prompt_tokens
                completion_tokens += new_completion_tokens
                total_tokens = prompt_tokens + completion_tokens
                total_request_bytes += new_request_bytes
                total_response_bytes += new_response_bytes
                
                elapsed = time.time() - start_time
                if elapsed > 0:
                    prompt_rate = prompt_tokens / elapsed
                    completion_rate = completion_tokens / elapsed
                    uplink_mbps = (total_request_bytes * 8) / (elapsed * 1_000_000)
                    downlink_mbps = (total_response_bytes * 8) / (elapsed * 1_000_000)
                else:
                    prompt_rate = completion_rate = uplink_mbps = downlink_mbps = 0.0
                
                progress.update(
                    task,
                    completed=completed,
                    prompt_rate=prompt_rate,
                    completion_rate=completion_rate,
                    uplink=uplink_mbps,
                    downlink=downlink_mbps,
                    threads=thread_count
                )
                if self._progress_callback:
                    self._progress_callback(completed, total)

            # Convert providers to format expected by Rust
            provider_configs = [
                (p.name, p.api_key, p.base_url, p.config)
                for p in self.providers
            ]

            # Process all requests through all providers in round-robin fashion
            metrics = process_requests_multi(
                provider_configs,
                requests,
                update_progress,
                self.providers[0].test_mode,  # Use first provider's test mode
                self.providers[0].tokens_per_minute,  # Use first provider's rate limit
            )

            # Create per-provider metrics
            provider_results = {}
            for provider in self.providers:
                provider_key = f"{provider.name}:{provider.base_url}"
                provider_metrics = [m for m in metrics if m.provider_name == provider_key]
                if provider_metrics:  # Only create metrics if we have results for this provider
                    provider_results[provider_key] = BatchRequestResult(
                        total_requests=len(provider_metrics),
                        total_tokens=sum(m.prompt_tokens + m.completion_tokens for m in provider_metrics),
                        prompt_tokens=sum(m.prompt_tokens for m in provider_metrics),
                        completion_tokens=sum(m.completion_tokens for m in provider_metrics),
                        total_time=time.time() - start_time,
                        metrics=provider_metrics,
                        total_request_bytes=sum(m.request_bytes for m in provider_metrics),
                        total_response_bytes=sum(m.response_bytes for m in provider_metrics),
                        provider_metrics={},
                    )

            return BatchRequestResult(
                total_requests=len(metrics),
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_time=time.time() - start_time,
                metrics=metrics,
                total_request_bytes=total_request_bytes,
                total_response_bytes=total_response_bytes,
                provider_metrics=provider_results,
            )
