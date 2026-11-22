# External OCR corpus sources

Downloaded 2026-11-22. All files are untrusted data; never executed. Converter: backend/scripts/convert_external_corpus.py (stdlib only, run with `python3 -I`).

## 1. Bankstatemently Open Benchmark -- SKIPPED (no usable ground truth)
- URL: https://github.com/bankstatemently/bank-statement-parsing-benchmark
- License (LICENSE file, first lines, verbatim): "MIT License / Copyright (c) 2026 Bankstatemently / Permission is hereby granted, free of charge, to any person obtaining a copy ..." Synthetic statements (README: "15 synthetic statements").
- Files kept: 0. Only bsb-001..005 PDFs are released; 006-015 are COMING_SOON.
- Reason skipped: README says "Known ground truth held server-side for tamper-proof scoring". The repo has statement-info.json (metadata only, no transactions) and examples/*-submission.json (example parser submissions, not answer keys). No ground truth, so nothing converted. The PDFs I fetched to inspect were deleted.

## 2. AgamiAI/Indian-Bank-Statements -- USED
- URL: https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements
- License (dataset card metadata, verbatim): `license: apache-2.0`; card body: "License: Apache 2.0".
- Personal data: card states "Fully synthetic - no real customer information." and "Entirely synthetic data. No real personal or financial information included."
- Files: 10 statements (20 MB+ of PDFs, 26 MB total dir) in agami/: 6 digital (Digital_Type1/2-00001..00003) and 4 scanned (Scanned_Type1-00001,00002; Scanned_Type2-00001,00002). Each has <name>.pdf, <name>.src.json (upstream JSON, unchanged) and <name>.expected.json (converted). README.upstream.md is the upstream card.
  Scanned_Type1-0000N has the same underlying data as Digital_Type1-0000N (digital vs scanned pair).
- Conversion notes:
  - Type1: debit/credit columns; date = date part of `date`. Type2: `cr_dr` + `transaction_amount`; date DD/MM/YYYY converted to ISO.
  - Failed rows (`failed: true`, amount 0.0) are dropped; zero-amount rows dropped.
  - totals = sums of kept rows.
  - Source balance anomaly: in every file, opening + credits - debits != closing_balance (e.g. Digital_Type1-00001 row 19 balance drops 9,562.10 for a printed 1,347.60 debit). The printed amount matches the JSON amount, so the row amounts are used; balances are ignored. The converter prints a WARN for each file.
  - Cross-check done: for all 6 digital PDFs, every expected row amount appears in `pdftotext -layout` output (0 missing). Scanned files were not text-checked (no OCR run); they share JSON with the digital twins (Type1) or are the same generator (Type2).
  - Digital PDFs carry a diagonal watermark that pdftotext interleaves into text.

## 3. AyonPal/bank-statement-pdf-parser -- SKIPPED (no ground truth)
- URL: https://github.com/AyonPal/bank-statement-pdf-parser
- License (README, verbatim): "This project is licensed under the MIT License." LICENSE file begins "MIT License / Copyright (c) 2026". Samples are synthetic per README ("All sample PDFs in this repository are synthetic.").
- Files kept: 0. samples/parsed/*.json are output of the repo's own parser ("regression artifacts"), not independent ground truth. Using them would score against a parser's output, so skipped per the no-hand-guess rule.

## 4. Voxel51/scanned_receipts (SROIE mirror) -- sroie/
- URL: https://huggingface.co/datasets/Voxel51/scanned_receipts
- License (dataset card metadata, verbatim): `license: cc-by-4.0`. Card body has no other license text (only "Development of commercial OCR systems (subject to licensing)" under use cases). The mirror tag is not verified against the upstream SROIE terms.
- Count: 712 receipts (712 .jpg + 712 .expected.json), 374 MB of images (full set; upstream 421 MB incl. samples.json and a demo gif, which were not kept). Downloaded via direct HTTPS from `resolve/main/`.
- Conversion (scripts/convert_receipt_corpus.py sroie): merchant = `company`; total = `total` with RM/$ and thousands separators stripped (1 empty total -> null); currency "MYR" is a dataset-level constant (Malaysian receipts; some totals print "$"); date -> ISO only when unambiguous. 337 of 712 dates are null: numeric DD/MM vs MM/DD with both parts <= 12, 2-digit-year and dotted forms are treated as ambiguous. Address, text boxes not kept.

## 5. Zarov888/consolidated_receipt_dataset (CORD v1, FiftyOne mirror) -- cord/
- URL: https://huggingface.co/datasets/Zarov888/consolidated_receipt_dataset
- License (dataset card, verbatim): "**License:** CC-BY-4.0 (Creative Commons Attribution 4.0 International License)"; metadata `license: cc-by-4.0`.
- Count: 800 receipts (800 .png + 800 .expected.json), about 1.2 GB of images (full set). The 43 MB cord_v1.gif demo, samples.json and metadata were not kept.
- Conversion (scripts/convert_receipt_corpus.py cord): total = `total_price` normalized (Rp prefix, "." / "," thousands and decimal forms handled; 24 null: 19 with no total_price, 5 ambiguous such as "57,0000", "39,200,00", "55,800 55,834"); currency "IDR" dataset-level constant; date null for all 800 and merchant null for all 800 (the mirror has no such fields; accepted by the requester). Subtotal, service, tax and line-item boxes not kept.

## 6. Mendeley 5n3jwggcjk "OCR Invoice" (Indonesian receipt OCR) -- indo_receipts/ -- SKIPPED
- URL: https://data.mendeley.com/datasets/5n3jwggcjk/1
- License (dataset page, verbatim): "CC BY 4.0" (Creative Commons Attribution 4.0 International; licence text: "You can share, copy and modify this dataset so long as you give appropriate credit, provide a link to the CC BY license, and indicate if changes were made ...").
- Reason skipped: license allows reuse, but the published files do not contain the receipts. The public file list (public-api .../files?folder_id=root&version=1; dataset size 311,438 bytes) is: `data testing.xlsx` (111 bytes, text: "Seluruh data gambar training dan evaluasi dapat diunduh melalui https://data.mendeley.com/datasets/z8f89t36rh/1"), `data training.xlsx` (26 KB; model-comparison rows: expected/extracted JSON, cost, time), `download` (156 KB xlsx; pivot/analysis sheets, tag glossary), `gambar_train.txt` (macOS .DS_Store, not text), `gemini_dataset_2.json` (165 bytes, empty of receipts), `_$hasil analisa aldo.xlsx` (analysis). No 800 OCR word sequences and no date/total/merchant ground truth (annotation schema is items + charge only). Nothing converted; temp downloads deleted.
