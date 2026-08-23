# Model provisioning and identity V1

Production generation remains `qwen3.5:9b`. The verified Ollama digest is `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`. Startup and restore compare the exact tag and digest; a missing or mismatched model fails readiness.

There is no automatic model download. Online provisioning is an explicit operations-profile action and requires `--network-download-ack`. Offline provisioning first verifies the supplied artifact SHA-256. The model volume is mounted from an operator-selected persistent host path.

The embedding model remains `intfloat/multilingual-e5-base`. Production/recovery services set Hugging Face and Transformers offline mode so a missing cache fails quickly instead of silently reaching the network. API and indexing worker share the same persistent cache.

The model-loss drill started a second Ollama instance against an empty isolated model directory. `model-check` failed closed with `MODEL_NOT_PROVISIONED`; the real host model was not removed or changed.
