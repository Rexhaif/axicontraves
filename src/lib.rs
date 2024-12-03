use std::error::Error;
use std::sync::Arc;
use std::time::Duration;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
use reqwest::Client;
use reqwest::ClientBuilder;
use tokio::runtime::Runtime;
use futures::future::join_all;
use serde::{Serialize, Deserialize};
use async_trait::async_trait;
use rand::Rng;
use num_cpus;
use tokio::sync::{Mutex, Semaphore, RwLock};
use tokio::time::{sleep, Instant};

// Helper functions for config extraction
fn extract_config_value<'a, T: FromPyObject<'a>>(dict: &'a PyDict, key: &str) -> PyResult<Option<T>> {
    match dict.get_item(key)? {
        Some(value) => Ok(Some(value.extract()?)),
        None => Ok(None),
    }
}

fn get_required_value<'a, T: FromPyObject<'a>>(dict: &'a PyDict, key: &str) -> PyResult<T> {
    match dict.get_item(key)? {
        Some(value) => value.extract(),
        None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Missing required key: {}", key),
        )),
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
}

#[pyclass]
#[derive(Clone)]
pub struct RequestMetrics {
    #[pyo3(get)]
    pub prompt_tokens: usize,
    #[pyo3(get)]
    pub completion_tokens: usize,
    #[pyo3(get)]
    pub total_tokens: usize,
    #[pyo3(get)]
    pub request_bytes: usize,
    #[pyo3(get)]
    pub response_bytes: usize,
    #[pyo3(get)]
    pub provider_name: String,
}

impl RequestMetrics {
    pub fn new(
        prompt_tokens: usize,
        completion_tokens: usize,
        request_bytes: usize,
        response_bytes: usize,
        provider_name: String,
    ) -> Self {
        Self {
            prompt_tokens,
            completion_tokens,
            total_tokens: prompt_tokens + completion_tokens,
            request_bytes,
            response_bytes,
            provider_name,
        }
    }
}

#[async_trait]
pub trait LLMProvider: Send + Sync {
    async fn send_chat_request(&self, messages: Vec<Message>) -> Result<RequestMetrics, Box<dyn Error + Send + Sync>>;
    fn name(&self) -> &str;
}

#[derive(Debug)]
struct OpenAIConfig {
    model: String,
    temperature: f32,
    max_tokens: Option<usize>,
    top_p: Option<f32>,
    frequency_penalty: Option<f32>,
    presence_penalty: Option<f32>,
}

struct OpenAIProvider {
    client: Client,
    api_key: String,
    base_url: String,
    config: OpenAIConfig,
    test_mode: bool,
}

#[async_trait]
impl LLMProvider for OpenAIProvider {
    async fn send_chat_request(&self, messages: Vec<Message>) -> Result<RequestMetrics, Box<dyn Error + Send + Sync>> {
        if self.test_mode {
            let prompt_tokens = calculate_prompt_tokens(&messages);
            let completion_tokens = simulate_completion_tokens(prompt_tokens);
            let total_tokens = prompt_tokens + completion_tokens;
            
            // Simulate API latency
            let base_latency = Duration::from_millis(50);
            let token_processing_time = Duration::from_micros((total_tokens * 100) as u64);
            sleep(base_latency + token_processing_time).await;
            
            // Simulate request/response sizes
            let request_bytes = serde_json::to_string(&messages).unwrap_or_default().len();
            let response_bytes = completion_tokens * 4;
            
            return Ok(RequestMetrics::new(
                prompt_tokens,
                completion_tokens,
                request_bytes,
                response_bytes,
                format!("{}:{}", self.name(), self.base_url),
            ));
        }

        let url = format!("{}/v1/chat/completions", self.base_url.trim_end_matches('/'));
        
        let mut payload = serde_json::Map::new();
        if !self.config.model.is_empty() {
            payload.insert("model".to_string(), serde_json::Value::String(self.config.model.clone()));
        }
        payload.insert("messages".to_string(), serde_json::to_value(messages).unwrap());
        payload.insert("temperature".to_string(), serde_json::Value::Number(serde_json::Number::from_f64(self.config.temperature as f64).unwrap()));
        
        if let Some(max_tokens) = self.config.max_tokens {
            payload.insert("max_tokens".to_string(), serde_json::Value::Number(serde_json::Number::from(max_tokens)));
        }
        if let Some(top_p) = self.config.top_p {
            payload.insert("top_p".to_string(), serde_json::Value::Number(serde_json::Number::from_f64(top_p as f64).unwrap()));
        }
        if let Some(frequency_penalty) = self.config.frequency_penalty {
            payload.insert("frequency_penalty".to_string(), serde_json::Value::Number(serde_json::Number::from_f64(frequency_penalty as f64).unwrap()));
        }
        if let Some(presence_penalty) = self.config.presence_penalty {
            payload.insert("presence_penalty".to_string(), serde_json::Value::Number(serde_json::Number::from_f64(presence_penalty as f64).unwrap()));
        }

        let request_body = serde_json::to_string(&payload)?;
        let request_bytes = request_body.len() + format!("Authorization: Bearer {}\n", self.api_key).len();
        
        let response = self.client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&payload)
            .send()
            .await?;
            
        let response_bytes = response.content_length().unwrap_or(0) as usize;
            
        let response_data: serde_json::Value = response.json().await?;
            
        let usage = response_data["usage"].as_object()
            .ok_or("Missing usage data")?;
            
        Ok(RequestMetrics::new(
            usage["prompt_tokens"].as_u64().unwrap_or(0) as usize,
            usage["completion_tokens"].as_u64().unwrap_or(0) as usize,
            request_bytes,
            response_bytes,
            format!("{}:{}", self.name(), self.base_url),
        ))
    }

    fn name(&self) -> &str {
        "openai"
    }
}

fn calculate_prompt_tokens(messages: &[Message]) -> usize {
    messages.iter().map(|m| m.content.len() / 4).sum()
}

fn simulate_completion_tokens(prompt_tokens: usize) -> usize {
    let mut rng = rand::thread_rng();
    let base = prompt_tokens as f64 * 1.5;
    let variation = rng.gen_range(-0.2..=0.2);
    ((base * (1.0 + variation)) as usize).max(50)
}

struct BatchProcessor {
    runtime: Runtime,
    thread_count: usize,
    rate_limiter: Arc<RwLock<()>>,
}

impl BatchProcessor {
    fn new(tokens_per_minute: Option<usize>) -> Self {
        let thread_count = num_cpus::get();
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .worker_threads(thread_count)
            .enable_all()
            .build()
            .unwrap();
        
        Self {
            runtime,
            thread_count,
            rate_limiter: Arc::new(RwLock::new(())),
        }
    }

    async fn process_request(
        provider: Arc<dyn LLMProvider>,
        messages: Vec<Message>,
        rate_limiter: Arc<RwLock<()>>,
    ) -> Result<RequestMetrics, Box<dyn Error + Send + Sync>> {
        let _lock = rate_limiter.read().await;
        provider.send_chat_request(messages).await
    }
}

// Build an optimized HTTP client
fn build_client() -> Client {
    ClientBuilder::new()
        .pool_max_idle_per_host(100)
        .pool_idle_timeout(Duration::from_secs(30))
        .tcp_nodelay(true)
        .tcp_keepalive(Duration::from_secs(30))
        .http2_keep_alive_interval(Duration::from_secs(20))
        .http2_keep_alive_timeout(Duration::from_secs(10))
        .http2_adaptive_window(true)
        .build()
        .unwrap()
}

#[pyfunction]
fn process_requests_multi(
    py: Python<'_>,
    providers: Vec<(&str, &str, Option<&str>, PyObject)>, // (name, api_key, base_url, config)
    requests: Vec<PyObject>,
    callback: PyObject,
    test_mode: bool,
    tokens_per_minute: Option<usize>,
) -> PyResult<Vec<RequestMetrics>> {
    let client = build_client();
    let processor = BatchProcessor::new(tokens_per_minute);
    let total_requests = requests.len();
    let mut completed = 0;
    let mut results = Vec::new();

    // Create provider instances
    let providers: Vec<Arc<dyn LLMProvider>> = providers
        .into_iter()
        .map(|(name, api_key, base_url, config)| {
            let config = config.extract::<&PyDict>(py)?;
            match name {
                "openai" => Ok(Arc::new(OpenAIProvider {
                    client: client.clone(),
                    api_key: api_key.to_string(),
                    base_url: base_url.unwrap_or("https://api.openai.com").to_string(),
                    config: OpenAIConfig {
                        model: get_required_value(config, "model")?,
                        temperature: get_required_value(config, "temperature")?,
                        max_tokens: extract_config_value(config, "max_tokens")?,
                        top_p: extract_config_value(config, "top_p")?,
                        frequency_penalty: extract_config_value(config, "frequency_penalty")?,
                        presence_penalty: extract_config_value(config, "presence_penalty")?,
                    },
                    test_mode,
                }) as Arc<dyn LLMProvider>),
                _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Unsupported provider")),
            }
        })
        .collect::<PyResult<Vec<_>>>()?;

    // Convert Python messages to Rust messages
    let requests: Vec<Vec<Message>> = requests
        .into_iter()
        .map(|req| {
            let messages = req.extract::<Vec<&PyDict>>(py)?;
            messages
                .into_iter()
                .map(|msg| {
                    Ok(Message {
                        role: get_required_value(msg, "role")?,
                        content: get_required_value(msg, "content")?,
                    })
                })
                .collect::<PyResult<Vec<Message>>>()
        })
        .collect::<PyResult<Vec<Vec<Message>>>>()?;

    let batch_size = std::cmp::min(processor.thread_count, 4);
    let mut provider_index = 0;

    // Process requests in parallel batches with round-robin provider selection
    for chunk in requests.chunks(batch_size) {
        let chunk_futures = chunk.iter().enumerate().map(|(i, messages)| {
            let provider = Arc::clone(&providers[provider_index]);
            provider_index = (provider_index + 1) % providers.len();
            let rate_limiter = processor.rate_limiter.clone();
            BatchProcessor::process_request(provider, messages.clone(), rate_limiter)
        });
        
        let batch_results = processor.runtime.block_on(join_all(chunk_futures));
        let valid_results: Vec<_> = batch_results.into_iter().filter_map(Result::ok).collect();
        
        completed += valid_results.len();
        
        let batch_prompt_tokens: usize = valid_results.iter().map(|m| m.prompt_tokens).sum();
        let batch_completion_tokens: usize = valid_results.iter().map(|m| m.completion_tokens).sum();
        let batch_request_bytes: usize = valid_results.iter().map(|m| m.request_bytes).sum();
        let batch_response_bytes: usize = valid_results.iter().map(|m| m.response_bytes).sum();
        
        let args = PyTuple::new(
            py,
            &[
                completed as i32,
                total_requests as i32,
                batch_prompt_tokens as i32,
                batch_completion_tokens as i32,
                batch_request_bytes as i32,
                batch_response_bytes as i32,
                processor.thread_count as i32
            ],
        );
        callback.call1(py, args)?;

        results.extend(valid_results);
    }

    Ok(results)
}

#[pymodule]
fn axicontraves(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<RequestMetrics>()?;
    m.add_function(wrap_pyfunction!(process_requests_multi, m)?)?;
    Ok(())
}