from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
import pandas as pd
from chromadb.utils import embedding_functions

from .entities import data_path
from .reranker import rerank
from .state import AssistantState
from .state import RetrievedDocument


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "vikmo_catalogue_all_minilm_l6_v2"


class CatalogueRetriever:
    def __init__(self, catalogue_path: Path | None = None, persist_dir: Path | None = None) -> None:
        self.catalogue_path = catalogue_path or data_path("catalogue.csv")
        self.root_dir = Path(__file__).resolve().parents[1]
        self.persist_dir = persist_dir or self.root_dir / "chroma"
        self.model_cache_dir = self.root_dir / "models"
        self.df = pd.read_csv(self.catalogue_path)
        self.df["document"] = self.df.apply(self._row_to_text, axis=1)
        model_cache_exists = (self.model_cache_dir / "models--sentence-transformers--all-MiniLM-L6-v2").exists()
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL,
            cache_folder=str(self.model_cache_dir),
            local_files_only=model_cache_exists,
        )
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
        self._ensure_index()

    @staticmethod
    def _row_to_text(row: pd.Series) -> str:
        return (
            f"SKU: {row.sku}. Name: {row['name']}. Category: {row.category}. "
            f"Brand: {row.brand}. Vehicle Fitment: {row.vehicle_fitment}. "
            f"Price INR: {row.price_inr}. Stock: {row.stock}. Description: {row.description}"
        )

    def search(
        self,
        query: str,
        state: AssistantState,
        top_k: int = 3,
        candidate_k: int = 20,
    ) -> list[RetrievedDocument]:
        filters = state.get("metadata_filters", {}) or {}
        if sku := filters.get("sku"):
            doc = self.by_sku(sku)
            return [doc] if doc else []

        where = self._build_where(filters)
        results = self.collection.query(
            query_texts=[query],
            n_results=max(candidate_k, top_k),
            where=where,
            include=["metadatas", "distances"],
        )
        docs = self._results_to_docs(results)
        
        return rerank(query, docs, state.get("entities", {}), top_k=top_k)

    def filter_by_metadata(
        self,
        filters: dict[str, str],
        product_keyword: str | None = None,
    ) -> list[RetrievedDocument]:
        df = self.df
        if vehicle := filters.get("vehicle_fitment"):
            df = df[df["vehicle_fitment"] == vehicle]
        if category := filters.get("category"):
            df = df[df["category"] == category]
        if brand := filters.get("brand"):
            df = df[df["brand"] == brand]
        if sku := filters.get("sku"):
            df = df[df["sku"].astype(str).str.upper() == sku.upper()]

        docs = [self._row_to_doc(row) for _, row in df.iterrows()]
        if product_keyword:
            keyword = product_keyword.lower()
            docs = [
                doc
                for doc in docs
                if keyword in doc["name"].lower() or keyword in doc["description"].lower()
            ]
        return docs

    def by_sku(self, sku: str) -> RetrievedDocument | None:
        matches = self.df[self.df["sku"].astype(str).str.upper() == sku.upper()]
        if matches.empty:
            return None
        return self._row_to_doc(matches.iloc[0])

    @staticmethod
    def _row_to_doc(row: pd.Series) -> RetrievedDocument:
        return {
            "sku": str(row.sku),
            "name": str(row["name"]),
            "category": str(row.category),
            "brand": str(row.brand),
            "vehicle_fitment": str(row.vehicle_fitment),
            "price_inr": int(row.price_inr),
            "stock": int(row.stock),
            "description": str(row.description),
            "score": 1.0,
        }

    def _ensure_index(self) -> None:
        existing = self.collection.count()
        if existing == len(self.df):
            return

        if existing:
            self.client.delete_collection(COLLECTION_NAME)
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"},
            )

        ids = self.df["sku"].astype(str).tolist()
        documents = self.df["document"].astype(str).tolist()
        metadatas = [self._row_to_metadata(row) for _, row in self.df.iterrows()]
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    @staticmethod
    def _row_to_metadata(row: pd.Series) -> dict[str, str | int]:
        return {
            "sku": str(row.sku),
            "name": str(row["name"]),
            "category": str(row.category),
            "brand": str(row.brand),
            "vehicle_fitment": str(row.vehicle_fitment),
            "price_inr": int(row.price_inr),
            "stock": int(row.stock),
            "description": str(row.description),
        }

    @staticmethod
    def _build_where(filters: dict[str, str]) -> dict[str, Any] | None:
        clauses = [{key: {"$eq": value}} for key, value in filters.items()]
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    @staticmethod
    def _results_to_docs(results: dict[str, Any]) -> list[RetrievedDocument]:
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        docs: list[RetrievedDocument] = []
        for metadata, distance in zip(metadatas, distances):
            score = 1.0 - float(distance)
            docs.append(
                {
                    "sku": str(metadata["sku"]),
                    "name": str(metadata["name"]),
                    "category": str(metadata["category"]),
                    "brand": str(metadata["brand"]),
                    "vehicle_fitment": str(metadata["vehicle_fitment"]),
                    "price_inr": int(metadata["price_inr"]),
                    "stock": int(metadata["stock"]),
                    "description": str(metadata["description"]),
                    "score": score,
                }
            )
        return docs
