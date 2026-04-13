"""
sentiment/engine.py
───────────────────
NLP Sentiment Analysis Engine for Smart Campus

Pipeline:
1. Fine-tune a pretrained Russian BERT on scraped 2GIS reviews
2. Multi-category classification (cafe, classroom, study_space, facility)
3. Weighted reputation score with anti-spam + temporal decay
4. Trending analysis with exponential temporal weighting

Target: 85%+ precision/recall on campus-specific corpus
"""

from __future__ import annotations

import json
import math
import re
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

try:
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        Trainer,
        TrainingArguments,
        pipeline,
    )
    from datasets import Dataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch/Transformers not available – using rule-based fallback")

try:
    import pymorphy3
    MORPHY_AVAILABLE = True
except ImportError:
    MORPHY_AVAILABLE = False

from config import (
    SENTIMENT_MODEL_NAME,
    SENTIMENT_MODEL_PATH,
    SENTIMENT_CATEGORIES,
    SENTIMENT_LABELS,
    MIN_REVIEW_LENGTH,
    MAX_REVIEWS_PER_USER_PER_DAY,
    SPAM_SIMILARITY_THRESHOLD,
)

# ─── Text preprocessing ────────────────────────────────────────────────────────

class RussianTextPreprocessor:
    """Light normalisation for Russian campus reviews."""

    # Common campus abbreviations → full forms
    ABBREVS = {
        r"\bну\b": "назарбаев университет",
        r"\bбиб\b": "библиотека",
        r"\bкаф\b": "кафетерий",
        r"\bауд\b": "аудитория",
    }

    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer() if MORPHY_AVAILABLE else None

    def clean(self, text: str) -> str:
        text = text.lower().strip()
        # expand abbreviations
        for pattern, repl in self.ABBREVS.items():
            text = re.sub(pattern, repl, text)
        # strip urls, emails
        text = re.sub(r"http\S+|www\.\S+|\S+@\S+", "", text)
        # normalise whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def lemmatise(self, text: str) -> str:
        if not self.morph:
            return text
        tokens = text.split()
        lemmas = [self.morph.parse(t)[0].normal_form for t in tokens]
        return " ".join(lemmas)


# ─── Training ──────────────────────────────────────────────────────────────────

class SentimentTrainer:
    """Fine-tune rubert on the scraped review corpus."""

    LABEL2ID = {label: i for i, label in enumerate(SENTIMENT_LABELS)}
    ID2LABEL = {i: label for label, i in LABEL2ID.items()}

    def __init__(self, base_model: str = SENTIMENT_MODEL_NAME):
        self.base_model = base_model
        self.preprocessor = RussianTextPreprocessor()

    def load_data(self, reviews_path: str) -> tuple[list[str], list[int]]:
        """Load scraped reviews and derive labels from star ratings."""
        with open(reviews_path, encoding="utf-8") as f:
            raw = json.load(f)

        texts, labels = [], []
        for r in raw:
            text = self.preprocessor.clean(r["text"])
            if len(text) < MIN_REVIEW_LENGTH:
                continue
            label = r.get("sentiment_label") or _stars_to_label(r.get("rating", 0))
            if label not in self.LABEL2ID:
                continue
            texts.append(text)
            labels.append(self.LABEL2ID[label])

        logger.info(f"Loaded {len(texts)} reviews after filtering")
        return texts, labels

    def train(self, reviews_path: str, output_dir: str = SENTIMENT_MODEL_PATH,
              epochs: int = 4, batch_size: int = 16):
        if not TORCH_AVAILABLE:
            logger.error("Cannot train – PyTorch not available")
            return

        texts, labels = self.load_data(reviews_path)
        train_texts, val_texts, train_labels, val_labels = train_test_split(
            texts, labels, test_size=0.15, stratify=labels, random_state=42
        )

        tokenizer = AutoTokenizer.from_pretrained(self.base_model)

        def tokenise(batch):
            return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=256)

        train_ds = Dataset.from_dict({"text": train_texts, "label": train_labels}).map(tokenise, batched=True)
        val_ds   = Dataset.from_dict({"text": val_texts,   "label": val_labels  }).map(tokenise, batched=True)

        model = AutoModelForSequenceClassification.from_pretrained(
            self.base_model,
            num_labels=len(SENTIMENT_LABELS),
            id2label=self.ID2LABEL,
            label2id=self.LABEL2ID,
        )

        args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            warmup_ratio=0.1,
            weight_decay=0.01,
            logging_dir=f"{output_dir}/logs",
            report_to="none",
        )

        trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds)
        trainer.train()
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)

        # Evaluate
        preds_output = trainer.predict(val_ds)
        preds = np.argmax(preds_output.predictions, axis=1)
        report = classification_report(val_labels, preds, target_names=SENTIMENT_LABELS)
        logger.info(f"\n{report}")
        Path(f"{output_dir}/eval_report.txt").write_text(report)
        return report


# ─── Inference ─────────────────────────────────────────────────────────────────

class SentimentEngine:
    """
    Production inference engine.
    Falls back to rule-based lexicon when model is unavailable.
    """

    # Simple Russian sentiment lexicon for fallback
    POSITIVE_WORDS = {
        "хорошо", "отлично", "прекрасно", "удобно", "вкусно", "чисто",
        "быстро", "приятно", "советую", "рекомендую", "замечательно", "супер",
        "нравится", "доволен", "довольна", "лучший", "лучшая", "топ",
    }
    NEGATIVE_WORDS = {
        "плохо", "ужасно", "грязно", "медленно", "холодно", "невкусно",
        "очередь", "шумно", "дорого", "сломан", "сломана", "нет", "нельзя",
        "не работает", "недоволен", "разочарован", "отвратительно",
    }

    def __init__(self, model_path: str = SENTIMENT_MODEL_PATH):
        self.preprocessor = RussianTextPreprocessor()
        self.classifier = None
        self._try_load_model(model_path)

    def _try_load_model(self, path: str):
        if not TORCH_AVAILABLE:
            return
        if Path(path).exists():
            try:
                self.classifier = pipeline(
                    "text-classification",
                    model=path,
                    tokenizer=path,
                    device=0 if torch.cuda.is_available() else -1,
                )
                logger.info(f"Loaded fine-tuned model from {path}")
            except Exception as e:
                logger.warning(f"Could not load fine-tuned model: {e}")
        else:
            try:
                self.classifier = pipeline(
                    "text-classification",
                    model=SENTIMENT_MODEL_NAME,
                    device=-1,
                )
                logger.info(f"Loaded base model: {SENTIMENT_MODEL_NAME}")
            except Exception as e:
                logger.warning(f"Could not load base model: {e}. Using rule-based fallback.")

    def predict(self, text: str) -> dict:
        """Return sentiment label + confidence score."""
        cleaned = self.preprocessor.clean(text)

        if self.classifier:
            result = self.classifier(cleaned[:512])[0]
            label = result["label"].lower()
            # Normalise label names from different model variants
            if label in ("pos", "positive", "label_2"):
                label = "positive"
            elif label in ("neg", "negative", "label_0"):
                label = "negative"
            else:
                label = "neutral"
            return {"label": label, "score": round(result["score"], 4)}

        # ── Rule-based fallback ──
        return self._rule_based(cleaned)

    def _rule_based(self, text: str) -> dict:
        tokens = set(text.split())
        pos = len(tokens & self.POSITIVE_WORDS)
        neg = len(tokens & self.NEGATIVE_WORDS)
        if pos > neg:
            label, score = "positive", 0.6 + min(pos * 0.05, 0.35)
        elif neg > pos:
            label, score = "negative", 0.6 + min(neg * 0.05, 0.35)
        else:
            label, score = "neutral", 0.5
        return {"label": label, "score": round(score, 4)}

    def predict_batch(self, texts: list[str]) -> list[dict]:
        return [self.predict(t) for t in texts]


# ─── Reputation algorithm ──────────────────────────────────────────────────────

class ReputationEngine:
    """
    Weighted venue reputation with:
    - Temporal decay  (recent reviews matter more)
    - Anti-spam       (near-duplicate and flood detection)
    - Confidence      (model score weighting)
    - Category        (separate scores per venue category)
    """

    DECAY_HALF_LIFE_DAYS = 90   # reviews lose half their weight after 90 days

    def __init__(self, sentiment_engine: SentimentEngine):
        self.sentiment = sentiment_engine
        self._seen_hashes: dict[str, list[datetime]] = defaultdict(list)  # user_id → timestamps

    # ── anti-spam ─────────────────────────────────────────────────────────────

    def _is_duplicate(self, text: str, existing_texts: list[str]) -> bool:
        """Cosine similarity check using character n-gram overlap."""
        def ngrams(s, n=3):
            return set(s[i:i+n] for i in range(len(s)-n+1))
        a = ngrams(text)
        for existing in existing_texts[-50:]:  # check last 50 for efficiency
            b = ngrams(existing)
            union = len(a | b)
            if union == 0:
                continue
            sim = len(a & b) / union
            if sim > SPAM_SIMILARITY_THRESHOLD:
                return True
        return False

    def _is_flood(self, user_id: str) -> bool:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=1)
        self._seen_hashes[user_id] = [
            t for t in self._seen_hashes[user_id] if t > cutoff
        ]
        if len(self._seen_hashes[user_id]) >= MAX_REVIEWS_PER_USER_PER_DAY:
            return True
        self._seen_hashes[user_id].append(now)
        return False

    # ── temporal weighting ────────────────────────────────────────────────────

    def _temporal_weight(self, review_date: datetime) -> float:
        age_days = (datetime.utcnow() - review_date).days
        return math.exp(-math.log(2) * age_days / self.DECAY_HALF_LIFE_DAYS)

    # ── score computation ─────────────────────────────────────────────────────

    def compute_score(
        self,
        reviews: list[dict],
        existing_texts: Optional[list[str]] = None,
    ) -> dict:
        """
        reviews: list of dicts with keys: text, user_id, created_at (ISO str), category
        Returns: {
            "overall_score": 0–5,
            "reputation_score": 0–1,
            "by_category": {category: score},
            "trending": "up" | "stable" | "down",
            "total_valid": int,
            "total_spam": int,
        }
        """
        existing_texts = existing_texts or []
        weighted_sentiments: list[tuple[float, float]] = []  # (weight, sentiment_value)
        category_scores: dict[str, list[float]] = defaultdict(list)
        spam_count = 0

        # Temporal split for trending: recent vs. older
        now = datetime.utcnow()
        recent_cutoff = now - timedelta(days=30)
        recent_vals, older_vals = [], []

        for rev in reviews:
            # Anti-spam
            if self._is_flood(rev.get("user_id", "anon")):
                spam_count += 1
                continue
            if self._is_duplicate(rev["text"], existing_texts):
                spam_count += 1
                continue
            existing_texts.append(rev["text"])

            # Sentiment
            result = self.sentiment.predict(rev["text"])
            sentiment_val = {"positive": 1.0, "neutral": 0.5, "negative": 0.0}[result["label"]]
            confidence = result["score"]

            # Temporal weight
            try:
                created_at = datetime.fromisoformat(rev.get("created_at", now.isoformat()))
            except ValueError:
                created_at = now
            t_weight = self._temporal_weight(created_at)

            combined_weight = t_weight * confidence
            weighted_sentiments.append((combined_weight, sentiment_val))

            # Category breakdown
            cat = rev.get("category", "general")
            category_scores[cat].append(sentiment_val)

            # Trending
            if created_at > recent_cutoff:
                recent_vals.append(sentiment_val)
            else:
                older_vals.append(sentiment_val)

        if not weighted_sentiments:
            return {
                "overall_score": 0.0,
                "reputation_score": 0.0,
                "by_category": {},
                "trending": "stable",
                "total_valid": 0,
                "total_spam": spam_count,
            }

        # Weighted mean sentiment (0–1) → scale to 0–5
        total_w = sum(w for w, _ in weighted_sentiments)
        reputation = sum(w * v for w, v in weighted_sentiments) / total_w
        overall_score = round(reputation * 5, 2)

        # Trending
        recent_mean = np.mean(recent_vals) if recent_vals else reputation
        older_mean  = np.mean(older_vals)  if older_vals  else reputation
        delta = recent_mean - older_mean
        trending = "up" if delta > 0.08 else ("down" if delta < -0.08 else "stable")

        return {
            "overall_score":   overall_score,
            "reputation_score": round(reputation, 4),
            "by_category": {
                cat: round(float(np.mean(scores)) * 5, 2)
                for cat, scores in category_scores.items()
            },
            "trending":      trending,
            "total_valid":   len(weighted_sentiments),
            "total_spam":    spam_count,
        }


# ─── Utilities ─────────────────────────────────────────────────────────────────

def _stars_to_label(stars: int) -> str:
    if stars >= 4: return "positive"
    if stars == 3: return "neutral"
    if stars in (1, 2): return "negative"
    return "neutral"
