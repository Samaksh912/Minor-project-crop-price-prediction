from __future__ import annotations

import logging

from config import CROP_NAME
from data_loader import load_data
from predictor import predict


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main():
    df = load_data()
    predict(crop_name=CROP_NAME, df=df, force_retrain=True)


if __name__ == "__main__":
    main()

