from __future__ import annotations

import logging

import numpy as np

from .config import (DIMENSION, EMBEDDING_MODEL, EMBEDDING_REVISION, RERANKER_MODEL,
                     RERANKER_REVISION, Settings)

log = logging.getLogger(__name__)


class Models:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self._embedding = None
        self._reranker = None
        self._reranker_tokenizer = None

    @property
    def embedding(self):
        if self._embedding is None:
            import torch
            from sentence_transformers import SentenceTransformer
            torch.set_num_threads(self.settings.threads)
            log.info("임베딩 모델 로드: %s (%s)", EMBEDDING_MODEL, self.settings.device)
            self._embedding = SentenceTransformer(
                EMBEDDING_MODEL, revision=EMBEDDING_REVISION,
                device=self.settings.device, trust_remote_code=False)
            self._embedding.max_seq_length = 8192
        return self._embedding

    def encode(self, texts: list[str], progress: bool = False) -> np.ndarray:
        model = self.embedding
        for text in texts:
            if len(model.tokenizer.encode(text, add_special_tokens=True)) > model.max_seq_length:
                raise ValueError("8192 토큰을 넘는 원문입니다. 원문을 자르지 않고 적재를 중단합니다.")
        vectors = model.encode(texts, batch_size=self.settings.batch_size,
                               normalize_embeddings=True, convert_to_numpy=True,
                               show_progress_bar=progress)
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.shape != (len(texts), DIMENSION) or not np.isfinite(vectors).all():
            raise ValueError("임베딩 차원/유한값 검증 실패")
        return vectors

    def load_reranker(self):
        if self._reranker is None:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            torch.set_num_threads(self.settings.threads)
            log.info("재정렬 모델 로드: %s (%s)", RERANKER_MODEL, self.settings.device)
            self._reranker_tokenizer = AutoTokenizer.from_pretrained(
                RERANKER_MODEL, revision=RERANKER_REVISION, trust_remote_code=False)
            self._reranker = AutoModelForSequenceClassification.from_pretrained(
                RERANKER_MODEL, revision=RERANKER_REVISION, trust_remote_code=False,
                use_safetensors=True).to(self.settings.device).eval()

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """원문 전체를 겹치는 창으로 평가. 점수는 확률이 아닌 원시 logit입니다."""
        import torch
        self.load_reranker()
        tok = self._reranker_tokenizer
        query_ids = tok.encode(query, add_special_tokens=False)
        if len(query_ids) > 1024:
            raise ValueError("재정렬 질문은 1024 토큰 이내로 입력해 주세요.")
        capacity = 2048 - len(query_ids) - tok.num_special_tokens_to_add(pair=True)
        stride = capacity - min(128, capacity // 4)
        windows, owners = [], []
        for i, text in enumerate(texts):
            ids = tok.encode(text, add_special_tokens=False)
            for start in range(0, max(1, len(ids)), stride):
                window = ids[start:start + capacity]
                windows.append(tok.prepare_for_model(query_ids, window, truncation=False,
                                                      return_token_type_ids=False))
                owners.append(i)
                if start + capacity >= len(ids):
                    break
        scores = [float("-inf")] * len(texts)
        batch_size = min(2, self.settings.batch_size)
        for start in range(0, len(windows), batch_size):
            inputs = tok.pad(windows[start:start + batch_size], padding=True, return_tensors="pt")
            inputs = {key: value.to(self.settings.device) for key, value in inputs.items()}
            with torch.inference_mode():
                logits = self._reranker(**inputs).logits.view(-1).float().cpu().tolist()
            for owner, score in zip(owners[start:start + batch_size], logits, strict=True):
                scores[owner] = max(scores[owner], score)
        if not all(np.isfinite(scores)):
            raise ValueError("재정렬 점수 검증 실패")
        return scores
