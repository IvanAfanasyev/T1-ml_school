import math
import re
from collections import Counter

from algorithm.cloudmatch.data.service_text import build_service_text
from algorithm.cloudmatch.schemas.service import Service


TOKEN_PATTERN = re.compile(r"[a-zA-Zа-яА-Я0-9_\-+.]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """
    Превращает текст в список токенов.

    Пример:
    "Django-приложение с PostgreSQL"
    ->
    ["django-приложение", "с", "postgresql"]
    """

    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if token.strip()
    ]


class BM25Scorer:
    """
    Простая реализация BM25 без внешних библиотек.

    Она нужна, чтобы проект работал сразу,
    без установки rank_bm25 или поискового движка.
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b

    def score(
        self,
        query_text: str,
        services: list[Service],
    ) -> dict[str, float]:
        """
        Возвращает словарь:
        {
            service_id: normalized_bm25_score
        }
        """

        if not services:
            return {}

        query_tokens = tokenize(query_text)

        if not query_tokens:
            return {
                service.service_id: 0.0
                for service in services
            }

        documents = [
            tokenize(build_service_text(service))
            for service in services
        ]

        raw_scores = self._calculate_raw_scores(
            query_tokens=query_tokens,
            documents=documents,
        )

        normalized_scores = self._normalize_scores(raw_scores)

        return {
            service.service_id: normalized_scores[index]
            for index, service in enumerate(services)
        }

    def _calculate_raw_scores(
        self,
        query_tokens: list[str],
        documents: list[list[str]],
    ) -> list[float]:
        document_count = len(documents)

        document_lengths = [len(document) for document in documents]
        average_document_length = (
            sum(document_lengths) / document_count
            if document_count > 0
            else 0.0
        )

        document_frequencies = self._calculate_document_frequencies(documents)

        scores = []

        for document in documents:
            term_frequencies = Counter(document)
            document_length = len(document)

            score = 0.0

            for token in query_tokens:
                if token not in term_frequencies:
                    continue

                tf = term_frequencies[token]
                df = document_frequencies.get(token, 0)

                idf = math.log(
                    1 + (document_count - df + 0.5) / (df + 0.5)
                )

                denominator = (
                    tf
                    + self.k1
                    * (
                        1
                        - self.b
                        + self.b
                        * document_length
                        / average_document_length
                    )
                )

                token_score = idf * (tf * (self.k1 + 1)) / denominator
                score += token_score

            scores.append(score)

        return scores

    def _calculate_document_frequencies(
        self,
        documents: list[list[str]],
    ) -> dict[str, int]:
        document_frequencies = {}

        for document in documents:
            unique_tokens = set(document)

            for token in unique_tokens:
                document_frequencies[token] = (
                    document_frequencies.get(token, 0) + 1
                )

        return document_frequencies

    def _normalize_scores(self, scores: list[float]) -> list[float]:
        """
        Приводит BM25 scores к диапазону 0..1.

        Если все scores равны 0, возвращаем нули.
        """

        if not scores:
            return []

        max_score = max(scores)

        if max_score == 0:
            return [0.0 for _ in scores]

        return [score / max_score for score in scores]