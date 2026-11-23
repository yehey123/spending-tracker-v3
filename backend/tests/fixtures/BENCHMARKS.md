# OCR / transaction-extraction benchmark candidates (research notes, 2026-11-22)

One pass, breadth medium. Licenses quoted from fetched pages; "UNKNOWN" = not found on page. Fit = 1-5 for date + amount + total ground truth with a Tesseract+regex parser (PH/US statements).
Search note: no Philippine/Singapore/Malaysia receipt dataset found. No public US credit-card statement dataset found. "Find-It" and "ExpressExpense" returned nothing in search (UNKNOWN). Kaggle was not fetched directly.

## Already known (not re-researched)
- AgamiAI/Indian-Bank-Statements (used). Re-confirmed: https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements -- license "apache-2.0" (metadata) / "License: Apache 2.0" (card); 10K<n<100K; 1.37 GB; synthetic scanned PDF + JSON (date, value_date, description, debit, credit, balance; opening/closing balance). Mirrors exist (shashankshingare/, Akashved/) -- dedupe.
- Bankstatemently benchmark: MIT repo, 5 synthetic statements, 5 countries (via search snippet, https://www.producthunt.com/products/bankstatemently-open-benchmark).
- CORD v1: https://github.com/clovaai/cord -- "This work is licensed under a Creative Commons Attribution 4.0 International License." 1,000 receipts per version (800/100/100). Indonesian receipts. HF mirror says sensitive fields removed.
- SROIE: license unclear. 1,000 scanned receipts, fields company/date/address/total (https://arxiv.org/pdf/2103.10213 via search snippet).

## Candidates

### 1. Voxel51/scanned_receipts (SROIE mirror)
- URL: https://huggingface.co/datasets/Voxel51/scanned_receipts
- License: "cc-by-4.0" (page metadata). NOTE: conflicts with SROIE original "unclear" status -- mirror's tag is unverified against upstream.
- Size: 712-713 samples, 421 MB. Type: receipt. Image: scanned JPEG.
- GT: company, date, address, total, text boxes + transcripts. No per-line items.
- Personal data: store addresses; real receipts. Fit 4 (date+total; no line items).

### 2. Zarov888/consolidated_receipt_dataset (CORD v1, FiftyOne)
- URL: https://huggingface.co/datasets/Zarov888/consolidated_receipt_dataset
- License: "CC-BY-4.0 (Creative Commons Attribution 4.0 International License)."
- Size: 800 samples, 1.3 GB. Type: receipt. Image: PNG ~864x1296.
- GT: num_items, subtotal_price, service_price, tax_price, total_price; per-box text, group_id (line items). NO date field listed on this card.
- Fit 4 (amounts + totals + line items; no date).

### 3. tusharshah2006/bank_statements_transactions (HF)
- URL: https://huggingface.co/datasets/tusharshah2006/bank_statements_transactions
- License: UNKNOWN ("No dataset card yet").
- Size: 149 rows (119/22/8), 26.7 MB. Type: bank statement. Image: UNKNOWN (imagefolder, widths up to 1.28k px).
- GT: gt_parse.bank_stmt_entries with TXN_DATE, TXN_DESC, CHEQUE_REF_NO, WITHDRAWAL_AMT, DEPOSIT_AMT, BALANCE_AMT -- exactly per-line date/amount/balance.
- Personal data: likely real (names, UPI handles, partially masked account numbers) -- inference by fetcher, not confirmed. Indian banks (HDFC, Bank of Baroda per search snippet).
- Fit 4 on fields, but license unknown + probable real PII: do not redistribute; check before committing to repo.

### 4. CORU / ReceiptSense
- URLs: https://github.com/Update-For-Integrated-Business-AI/CORU ; https://arxiv.org/abs/2406.04493v2
- License: arXiv page links "CC BY 4.0"; GitHub page states no license. CONFLICT, record both.
- Size: 20,000 annotated receipts, 30,000 OCR images, 10,000 item-level, 1,265 QA images. Type: receipt, Arabic+English. Image: photo/scan, noisy.
- GT: merchant, items, prices, receipt number, dates, totals. Real receipts presumed (not explicit). Region not specified.
- Fit 3 (right fields, wrong language mix, large).

### 5. WildReceipt (MMOCR)
- URLs: https://huggingface.co/datasets/jinhybr/WildReceipt ; https://github.com/open-mmlab/mmocr/blob/main/dataset_zoo/wildreceipt/metafile.yml ; download https://download.openmmlab.com/mmocr/data/wildreceipt.tar
- License: metafile "Type: N/A" "Link: N/A"; HF page: license UNKNOWN.
- Size: 1.74k rows (1.27k train / 472 test). Image: JPEG receipt photos.
- GT: words, bboxes, ner_tags (25 numeric classes). Class names (date/total) NOT verified on fetched pages.
- Fit 3 (license unknown, class mapping unverified).

### 6. Indonesian receipt OCR (Mendeley)
- URL: https://data.mendeley.com/datasets/5n3jwggcjk/1
- License: "CC BY 4.0". Size: "800 training samples, 90 testing samples". Image: none (OCR-derived word sequences + JSON).
- GT: items (names, quantities, prices), charge (tax, service, discount). Date not confirmed.
- Fit 2 (no images; good for regex-on-text tests only).

### 7. DocILE
- URLs: https://github.com/rossumai/docile ; https://docile.rossum.ai/
- License: repo code "MIT license"; dataset: not stated, "for research purposes" via access request form. 
- Size: 106,680 docs (6,680 annotated, 100k synthetic, ~1M unlabeled). Type: invoices/orders. Image: UNKNOWN (PDFs).
- GT: KILE + LIR fieldtypes; amounts/dates not explicitly listed on fetched pages.
- Fit 2 (invoices, gated access).

### 8. katanaml-org/invoices-donut-data-v1
- URL: https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1
- License: "MIT". Size: 501 rows, 198 MB. Type: invoice (source: Mendeley "Samples of electronic invoices", Kozlowski & Weichbroth 2021). English.
- GT: invoice number, date, seller, client, tax IDs, IBAN, line items. Fit 2 (invoices, not statements).

### 9. mychen76/invoices-and-receipts_ocr_v1
- URL: https://huggingface.co/datasets/mychen76/invoices-and-receipts_ocr_v1
- License: UNKNOWN ("More Information needed"). 2.24k rows, 282 MB. Invoices (header + items) + ocr_words. Fit 2.

### 10. FUNSD
- URL: https://guillaumejaume.github.io/FUNSD/
- License: UNKNOWN (links to /FUNSD/work, not quoted). 199 scanned forms. No amounts/dates schema. Fit 1.

### 11. TrainingDataPro/ocr-receipts-text-detection
- URL: https://huggingface.co/datasets/TrainingDataPro/ocr-receipts-text-detection
- License: "cc-by-nc-nd-4.0" (non-commercial, no derivatives). Sample only ("This is just an example of the data"); full set paid. Classes store, item, date_time, total. 54.6 MB. Fit 2.

### 12. AyonPal/bank-statement-pdf-parser (generator + samples)
- URL: https://github.com/AyonPal/bank-statement-pdf-parser
- License: "This project is licensed under the MIT License. It is provided as-is, without warranty of any kind."
- 3 synthetic statements (PDF+PNG+JSON/CSV); has Playwright generator scripts/generate_synthetic_statements.js. Sample JSON is parser OUTPUT, not independent ground truth. Indian-style labels (inference). Fit 2 (generator is a starting point for US/PH synthetic statements).

### Other mentions (not fetched)
- Voxel51 high-quality-invoice-images-for-ocr (synthetic invoices, ~18% annotated, per search snippet): https://docs.voxel51.com/dataset_zoo/datasets_hf/high_quality_invoice_images_for_ocr.html
- electrovir/statement-parser (US issuers Chase/Citi/USAA; parser only, no data).

## Unknowns
- Any Philippine bank/credit-card statement or PH receipt dataset: none found.
- Any US statement dataset with ground truth: none found.
- Find-It, ExpressExpense: not found. Kaggle sets: not searched directly.
- WildReceipt class names; DocILE image kind/field list; SROIE upstream license; FUNSD license text.
- Practical gap: for PH/US statements, a custom synthetic generator (extend AyonPal approach) is the only found route.
