from __future__ import annotations

import logging
import os
import zipfile

from config import BASE_DIR, CROP_NAME, MODELS_DIR, OUTPUTS_DIR
from data_loader import load_data
from predictor import predict


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main():
    df = load_data()
    predict(crop_name=CROP_NAME, df=df, force_retrain=True)

    zip_path = os.path.join(BASE_DIR, "bestcropprice_outputs.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in (MODELS_DIR, OUTPUTS_DIR):
            for root, _, files in os.walk(directory):
                for file_name in files:
                    abs_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(abs_path, BASE_DIR)
                    archive.write(abs_path, arcname=rel_path)

    print(os.path.abspath(zip_path))


if __name__ == "__main__":
    main()

