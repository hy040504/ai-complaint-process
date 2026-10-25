"""임베딩·재정렬 모델을 지연 로드하고 원문 전체를 평가합니다."""
from __future__ import annotations

import logging

import numpy as np

from .config import (DIMENSION, EMBEDDING_MODEL, EMBEDDING_REVISION, RERANKER_MODEL,
                     RERANKER_REVISION, Settings)

log = logging.getLogger(__name__)


class Models:
    """필요할 때 모델을 로드하고 같은 인스턴스에서 재사용합니다.

    Attributes:
        settings: 실행 장치·스레드·배치 크기를 포함한 모델 설정입니다.
    """

    def __init__(self, settings: Settings | None = None):
        """실행 설정을 보관하고 지연 로드할 모델 상태를 초기화합니다.

        Args:
            settings: 모델 실행 설정입니다. None이면 기본 설정을 사용합니다.
        """
        self.settings = settings or Settings()
        self._embedding = None
        self._reranker = None
        self._reranker_tokenizer = None

    @property
    def embedding(self):
        """최초 접근 시 BGE-M3를 로드하고 이후에는 같은 모델을 반환합니다.

        Returns:
            최대 입력 길이를 8192 토큰으로 설정한 임베딩 모델입니다.
        """
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
        """입력 길이를 검사하고 정규화된 임베딩을 생성합니다.

        Args:
            texts: 순서대로 임베딩할 원문 목록입니다.
            progress: 모델의 진행률 표시 여부입니다.

        Returns:
            원문 수 × 1024 형태의 float32 벡터 배열입니다.

        Raises:
            ValueError: 입력이 모델의 토큰 한도를 넘거나 벡터 차원·유한값 검증이 실패하면 발생합니다.
        """
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
        """최초 호출 시 재정렬 토크나이저와 평가 모드의 분류 모델을 로드합니다."""
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
        """원문 전체를 겹치는 창으로 평가하고 문서별 최대 logit을 반환합니다.

        Args:
            query: 재정렬 기준 질문이며 최대 1024 토큰입니다.
            texts: 질문과의 관련성을 평가할 후보 원문 목록입니다.

        Returns:
            입력 문서 순서의 원시 logit 목록입니다. 답변·이관 정답 확률이 아닙니다.

        Raises:
            ValueError: 질문의 토큰 한도를 넘거나 점수가 유한하지 않으면 발생합니다.
        """
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
