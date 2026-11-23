---
language:
- en
- hi
license: apache-2.0
size_categories:
- 10K<n<100K
task_categories:
- text-classification
- table-question-answering
- text-generation
tags:
- finance
- synthetic
- banking
- india
- transactions
- bank-statements
- document-ai
pretty_name: Indian Bank Statement Synthetic Dataset
---

# Indian Bank Statement Synthetic Dataset

Synthetically generated Indian **business bank statements** with realistic transaction patterns, proper banking workflows, and India-specific features. Available in **scanned PDF** and **digital JSON** formats.

**Scope:** Current Accounts (business banking) only. Does not include personal/savings accounts.

## Dataset Details

- **Curated by:** AgamiAI Inc.
- **Language(s):** English, Hindi (romanized)
- **License:** Apache 2.0
- **Repository:** https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements
- **Website:** https://www.agami.ai

**Note:** Contains only legitimate transactions (no fraud patterns).

## Uses

### Suitable For
- Document AI and OCR training
- Information extraction (account numbers, balances, transactions)
- Transaction categorization and classification
- Financial document understanding
- Table extraction and parsing
- Named Entity Recognition (NER)
- Testing data processing pipelines
- Educational purposes

### Not Suitable For
- Fraud detection or AML (no fraudulent patterns)
- Production compliance or regulatory reporting
- Credit decisions (lacks real creditworthiness signals)
- Personal banking AI (business accounts only)

## Dataset Structure

### Statement Formats

**Type 1: Separate Debit/Credit Columns**
| Date | Description | Debit | Credit | Balance |
|------|-------------|-------|--------|---------|
| 01/01/2024 | UPI-Vendor | 450.00 | - | 25,780.50 |
| 02/01/2024 | NEFT Credit | - | 50,000.00 | 75,780.50 |

**Type 2: Single Transaction Column**
| Date | Description | Transaction | Balance |
|------|-------------|-------------|---------|
| 01/01/2024 | UPI-Vendor | -450.00 | 25,780.50 |
| 02/01/2024 | NEFT Credit | +50,000.00 | 75,780.50 |

### JSON Structure

```json
{
  "bank_name": "Paramount Banking Corporation",
  "account_holder": "CYIENT TECHNOLOGIES",
  "account_holder_address": "F-346\nThird Floor\nHinjewadi\nPune\nMaharashtra\n520018",
  "account_number": "90823789756",
  "ifsc_code": "PARA0761987",
  "micr_code": "899946557",
  "branch_name": "PUNE HINJEWADI",
  "branch_code": "6738",
  "account_type": "CURRENT ACCOUNT- GENERAL",
  "currency": "INR",
  "customer_id": "134743833",
  "opening_balance": 158458.03,
  "closing_balance": 64424.49,
  "start_date": "2024-01-01",
  "end_date": "2024-03-31",
  "statement_date": "2025-11-20",
  "interest_rate": 2.83,
  "transactions": [
    {
      "date": "2024-01-01 12:40:40",
      "value_date": "2024-01-01",
      "description": "NEFT Dr-471179370408-HDFC0009038-RIDDHI RAVAL",
      "cheque_no": "862512",
      "debit": 13932.79,
      "credit": null,
      "balance": 144525.24,
      "branch_code": "3421",
      "failed": false
    }
  ]
}
```

### Transaction Types

- **UPI**: Unified Payments Interface (DR/CR)
- **NEFT**: National Electronic Funds Transfer
- **RTGS**: Real Time Gross Settlement (high-value)
- **IMPS**: Immediate Payment Service, salary transfers
- **Cheques**: Chq Paid, By Clg (Clearing)
- **Cash**: Withdrawals and deposits
- **ATM**: ATM withdrawals
- **Service Charges**: Bank fees
- **Reversals**: Failed transaction reversals

## Dataset Creation

### Why This Dataset

India's digital payment ecosystem is rapidly growing, but publicly available datasets for training AI models on Indian business banking documents are scarce due to privacy constraints. This dataset provides production-quality synthetic data for:

- Training document AI on Indian bank statement formats
- Testing OCR and information extraction systems
- Building fintech applications without real customer data
- Both scanned (unstructured) and digital (structured) formats
- India-specific payment systems (UPI, IMPS, NEFT, RTGS)

### Data Generation

**Fully synthetic** - no real customer information:
- Probabilistic modeling of realistic business transaction patterns
- Proper debit/credit flows with accurate balance calculations
- India-specific features: UPI references, IFSC/MICR codes, Indian business names
- Business entities: IT companies, manufacturing, retail, financial services
- Geographic coverage: Mumbai, Delhi, Bangalore, Pune, Chennai, Kolkata, Hyderabad
- Both scanned PDFs and structured JSON

All data is algorithmically generated. No real individuals or businesses contributed data.

### What's Included

- **Account holders:** Business entities (companies, partnerships, corporations)
- **Transaction patterns:** B2B payments, employee salaries, vendor payments, business expenses
- **Regional diversity:** Major Indian metros
- **Temporal patterns:** Quarterly statements, monthly salary cycles, vendor payment patterns

## Limitations

1. **No fraud patterns** - Not suitable for fraud detection
2. **Business-only** - No personal/savings account patterns
3. **Urban business focus** - May not represent rural small businesses
4. **Simplified patterns** - Real-world complexity is higher
5. **Format coverage** - Common layouts only, not exhaustive
6. **Synthetic OCR** - May not include all real-world OCR challenges

This dataset is for structure and format learning, not behavioral modeling. Always validate on real data before production deployment.

## Citation

**BibTeX:**

```bibtex
@dataset{indian_bank_statement_synthetic_2025,
  author = {AgamiAI Inc.},
  title = {Indian Bank Statement Synthetic Dataset},
  year = {2025},
  publisher = {HuggingFace},
  url = {https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements}
}
```

**APA:**

AgamiAI Inc. (2025). *Indian Bank Statement Synthetic Dataset* [Data set]. HuggingFace. https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements

## Glossary

**Indian Banking Terms:**
- **UPI**: Unified Payments Interface - instant real-time payment system
- **NEFT**: National Electronic Funds Transfer - batch processing (half-hourly)
- **RTGS**: Real Time Gross Settlement - high-value transactions (₹2 lakh+)
- **IMPS**: Immediate Payment Service - instant transfer, 24/7
- **IFSC Code**: Indian Financial System Code - 11-character bank branch identifier
- **MICR Code**: Magnetic Ink Character Recognition - 9-digit code for cheque processing
- **Current Account**: Business/commercial account, no transaction limits

## More Information

### About AgamiAI

AgamiAI builds private AI solutions for enterprises where privacy, accuracy, and compliance are critical. Specialized in Finance, Healthcare, Legal, and Consulting.

Visit: **https://www.agami.ai**

### File Structure

Each statement includes:
- `[statement_id].pdf` - Scanned bank statement
- `[statement_id].json` - Structured data with full metadata

### Related Datasets

Part of AgamiAI's Indian Financial Documents collection:
- **Indian Bank Statements** (this dataset)
- Indian GST Documents (coming soon)
- Indian Tax Documents (coming soon)
- Indian Audited Financial Documents (coming soon)

### Contact

- **Website**: https://www.agami.ai
- **HuggingFace**: https://huggingface.co/AgamiAI

---

**Version:** 1.0.0 | **License:** Apache 2.0 | **Last Updated:** November 2025

**Privacy Notice:** Entirely synthetic data. No real personal or financial information included.