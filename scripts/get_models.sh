#!/bin/sh
# Download the offline files Padi needs, once, while you have internet.
#   models/tessdata/tam.traineddata, eng.traineddata  Tesseract "best" models (Apache 2.0)
#   models/vendor/axe.min.js                           axe-core 4.10.2 (MPL 2.0), only for scripts/a11y_check.py
# After this, Padi runs with networking switched off.
set -eu
cd "$(dirname "$0")/.."
mkdir -p models/tessdata models/vendor
for lang in tam eng; do
  if [ ! -s "models/tessdata/$lang.traineddata" ]; then
    echo "Downloading $lang.traineddata"
    curl -fL --retry 3 -o "models/tessdata/$lang.traineddata" \
      "https://github.com/tesseract-ocr/tessdata_best/raw/main/$lang.traineddata"
  fi
done
if [ ! -s models/vendor/axe.min.js ]; then
  echo "Downloading axe.min.js (accessibility checker, development only)"
  curl -fL --retry 3 -o models/vendor/axe.min.js \
    "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
fi
echo "Models ready in models/"
