# nlp_engine.py
"""
Improved NLPEngine for intent management and script lookup.

Changes vs your original:
- add_intent returns (created: bool, overwritten: bool)
- add_intent accepts allow_overwrite flag (default False)
- prevents accidental duplicate intents unless allow_overwrite=True
- atomic save to disk (write temp + rename)
- small utilities: list_intents(), remove_intent()
- configurable model name and similarity threshold
- thread-safe using a simple lock
"""
import json
import os
import tempfile
import threading
from typing import List, Tuple, Optional

import numpy as np
from sentence_transformers import SentenceTransformer, util


class NLPEngine:
    def __init__(
        self,
        intents_path: str = "intents.json",
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.5,
    ):
        self.intents_path = intents_path
        self.model_name = model_name
        self.similarity_threshold = float(similarity_threshold)
        self._lock = threading.Lock()

        # load intents and model
        self._load_intents()
        self.model = SentenceTransformer(self.model_name)

        # build index (phrases, scripts, embeddings)
        self._rebuild_index()

    # -------------------
    # Persistence & index
    # -------------------
    def _load_intents(self) -> None:
        if not os.path.exists(self.intents_path):
            self.intents = {}
        else:
            with open(self.intents_path, "r", encoding="utf-8") as f:
                self.intents = json.load(f)

    def save_intents(self) -> None:
        """
        Atomic save: write to a temporary file then rename.
        """
        dirpath = os.path.dirname(os.path.abspath(self.intents_path)) or "."
        os.makedirs(dirpath, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dirpath, prefix="intents_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.intents, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.intents_path)
        finally:
            # if something went wrong and tmp still exists, remove it
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def _rebuild_index(self) -> None:
        """
        Flatten intents -> phrase list and precompute embeddings.
        Called whenever intents are changed.
        """
        self.phrases: List[str] = []
        self.scripts: List[str] = []
        self.phrase_to_intent: List[str] = []

        for intent_name, data in self.intents.items():
            examples = data.get("examples", []) or []
            script = data.get("script")
            for ex in examples:
                self.phrases.append(ex)
                self.scripts.append(script)
                self.phrase_to_intent.append(intent_name)

        if self.phrases:
            # compute embeddings as a tensor-like numpy array / torch etc. SentenceTransformer returns numpy by default
            self.embeddings = self.model.encode(self.phrases, convert_to_tensor=True)
        else:
            self.embeddings = None

    # -------------------
    # Lookup
    # -------------------
    def find_script(self, user_input: str) -> Tuple[Optional[str], float]:
        """
        Return (script_name, score). If no good match (score < threshold) returns (None, score).
        """
        user_input = (user_input or "").strip()
        if not user_input:
            return None, 0.0

        if self.embeddings is None:
            return None, 0.0

        user_emb = self.model.encode(user_input, convert_to_tensor=True)
        cosine_scores = util.cos_sim(user_emb, self.embeddings)[0]
        best_idx = int(np.argmax(cosine_scores))
        best_score = float(cosine_scores[best_idx])

        if best_score < self.similarity_threshold:
            return None, best_score

        return self.scripts[best_idx], best_score

    # -------------------
    # Management
    # -------------------
    def add_intent(
        self,
        intent_name: str,
        script: str,
        examples: List[str],
        description: str = "",
        allow_overwrite: bool = False,
    ) -> Tuple[bool, bool]:
        """
        Add or update an intent.

        Returns:
            (created: bool, overwritten: bool)
        Raises:
            ValueError if required fields missing or if intent exists and allow_overwrite is False.
        """
        intent_name = (intent_name or "").strip()
        script = (script or "").strip()
        examples = [e.strip() for e in (examples or []) if e and e.strip()]
        description = (description or "").strip()

        if not intent_name or not script or not examples:
            raise ValueError("intent_name, script and at least one example are required")

        with self._lock:
            created = False
            overwritten = False
            if intent_name in self.intents:
                if not allow_overwrite:
                    raise ValueError(f"Intent '{intent_name}' already exists. Set allow_overwrite=True to replace.")
                else:
                    overwritten = True

            # set / replace intent
            self.intents[intent_name] = {
                "script": script,
                "description": description,
                "examples": examples,
            }

            # persist and rebuild
            self.save_intents()
            self._rebuild_index()

            if overwritten:
                return False, True
            else:
                return True, False

    def remove_intent(self, intent_name: str) -> bool:
        """
        Remove an intent. Returns True if removed, False if intent not found.
        """
        intent_name = (intent_name or "").strip()
        if not intent_name:
            return False
        with self._lock:
            if intent_name in self.intents:
                del self.intents[intent_name]
                self.save_intents()
                self._rebuild_index()
                return True
            return False

    def list_intents(self) -> List[str]:
        return list(self.intents.keys())

    def get_intent(self, intent_name: str):
        return self.intents.get(intent_name)

    # Optional small helper to update threshold at runtime
    def set_threshold(self, t: float):
        self.similarity_threshold = float(t)
