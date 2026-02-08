from typing import List, Optional
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
from . import config

class EmbeddingModel:
    _instance: Optional['EmbeddingModel'] = None

    def __init__(self):
        """
        Initializes the embedding model and tokenizer.
        This is a singleton class to ensure the model is loaded only once.
        """
        model_path = config.MODEL_DIR / "model.onnx"
        tokenizer_path = config.MODEL_DIR / "tokenizer.json"

        if not model_path.exists() or not tokenizer_path.exists():
            raise FileNotFoundError(
                f"Model or tokenizer not found. Please run 'filemind init'. "
                f"Checked paths: {model_path}, {tokenizer_path}"
            )
        
        self.session = ort.InferenceSession(str(model_path))
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        
        # Set a max length for the tokenizer
        self.tokenizer.enable_truncation(max_length=512)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=512)

    @classmethod
    def get_instance(cls) -> 'EmbeddingModel':
        """Gets the singleton instance of the EmbeddingModel."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _l2_normalize(self, v: np.ndarray) -> np.ndarray:
        """Performs L2 normalization on a vector."""
        norm = np.linalg.norm(v, axis=1, keepdims=True)
        return v / (norm + 1e-12) # Add epsilon for stability

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generates L2-normalized embeddings for a list of texts.
        
        Args:
            texts: A list of strings to embed.
            
        Returns:
            A numpy array of shape (num_texts, embedding_dim) containing
            the L2-normalized embeddings.
        """
        # 1. Tokenize the input texts
        encoded = [self.tokenizer.encode(text) for text in texts]
        
        input_ids = np.array([e.ids for e in encoded])
        attention_mask = np.array([e.attention_mask for e in encoded])
        # The BGE model from Qdrant also expects token_type_ids
        token_type_ids = np.array([e.type_ids for e in encoded])

        # 2. Run inference with ONNX Runtime
        onnx_input = {
            'input_ids': input_ids.astype(np.int64),
            'attention_mask': attention_mask.astype(np.int64),
            'token_type_ids': token_type_ids.astype(np.int64)
        }

        model_output = self.session.run(None, onnx_input)

        last_hidden_state = model_output[0]
        
        # 3. Extract the [CLS] token embedding (first token)
        cls_embeddings = last_hidden_state[:, 0, :]
        
        # 4. Normalize the embeddings
        normalized_embeddings = self._l2_normalize(cls_embeddings)
        
        return normalized_embeddings.astype(np.float32)

# Convenience function to be used by other modules
def generate_embeddings(texts: List[str]) -> np.ndarray:
    """
    A wrapper function to get the model instance and generate embeddings.
    """
    model = EmbeddingModel.get_instance()
    return model.generate_embeddings(texts)
