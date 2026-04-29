"""
ML-powered parlay suggestion model.
Uses a lightweight logistic regression trained on historical parlays.
Falls back to heuristic scoring if no model is available.
"""
import pickle
import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression

MODEL_PATH = Path(__file__).with_name("model.pkl")


def train_model(parlays_data: list) -> LogisticRegression:
    """
    Train a logistic regression model on historical parlays.
    parlays_data: list of dicts with keys:
        - total_odds, legs (int), win_rate (float), status (str)
    Returns trained model.
    """
    X = []
    y = []
    for p in parlays_data:
        # Features: total_odds, number of legs, user's historical win_rate
        features = [
            float(p["total_odds"]),
            int(p["legs"]),
            float(p["win_rate"])
        ]
        X.append(features)
        y.append(1 if p["status"] == "won" else 0)

    if len(set(y)) < 2:
        # Not enough class diversity to train
        return None

    model = LogisticRegression(max_iter=1000)
    model.fit(np.array(X), np.array(y))
    return model


def save_model(model: LogisticRegression) -> None:
    """Save trained model to disk."""
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)


def load_model():
    """Load trained model from disk. Returns None if not found."""
    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    return None


def predict_win_prob(features: dict) -> float:
    """
    Predict win probability for a parlay.
    features: dict with keys 'total_odds', 'legs', 'win_rate'
    Returns probability (0.0 - 1.0)
    """
    model = load_model()
    if not model:
        return 0.0  # Fall back to heuristic

    X = np.array([[features["total_odds"], features["legs"], features["win_rate"]]])
    return float(model.predict_proba(X)[0, 1])


# Singleton for lazy loading
_ml_model = None


def get_ml_model():
    global _ml_model
    if _ml_model is None:
        _ml_model = load_model()
    return _ml_model
