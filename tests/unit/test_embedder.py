import pytest
import numpy as np
from app.indexing.embedder import E5Embedder, EmbeddingInputTooLongError

def test_embedder_initialization():
    embedder = E5Embedder.get_instance()
    assert embedder.model_name == "intfloat/multilingual-e5-base"
    assert embedder.embedding_dimension == 768
    assert embedder.max_tokens == 512

def test_encode_batch():
    embedder = E5Embedder.get_instance()
    chunks = [
        ("chunk1", "This is a test."),
        ("chunk2", "Hello world.")
    ]
    embeddings = embedder.encode_batch(chunks)
    assert len(embeddings) == 2
    assert embeddings[0].shape == (768,)
    # Verify L2 normalization
    norm = np.linalg.norm(embeddings[0])
    assert np.isclose(norm, 1.0, atol=1e-5)

def test_token_length_validation():
    embedder = E5Embedder.get_instance()
    # Create a string that is definitely longer than 512 tokens
    long_text = "word " * 600 
    
    with pytest.raises(EmbeddingInputTooLongError) as exc_info:
        embedder.encode_batch([("chunk_too_long", long_text)])
    
    assert exc_info.value.chunk_id == "chunk_too_long"
    assert exc_info.value.max_tokens == 512
    assert exc_info.value.token_count > 512
