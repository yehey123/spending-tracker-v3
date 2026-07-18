export interface Category {
  id: number;
  name: string;
  color: string | null;
  icon: string | null;
  slug: string | null;
  is_system: boolean;
  parent_id: number | null;
  children: Category[];
}

export interface CategoryCreate {
  name: string;
  color?: string | null;
  icon?: string | null;
  parent_id?: number | null;
}

export interface Statement {
  id: number;
  filename: string;
  type: string;
  status: string;
  ocr_provider: string | null;
  transaction_count: number;
  uploaded_at: string;
  error_message: string | null;
}

export interface Transaction {
  id: number;
  date: string;
  amount: string;
  description: string;
  direction: 'debit' | 'credit';
  category_id: number | null;
  category: Pick<Category, 'id' | 'name' | 'color'> | null;
  statement_id: number | null;
}

export interface TransactionCreate {
  date: string;
  amount: number;
  description: string;
  direction: 'debit' | 'credit';
  category_id?: number | null;
}

export interface TransactionPatch {
  category_id?: number | null;
  description?: string;
}

export interface CategoryBreakdown {
  category_id: number | null;
  category_name: string;
  color: string;
  amount: string;
  percent: number;
}

export interface ByCategoryResponse {
  month: string;
  total_debit: string;
  breakdown: CategoryBreakdown[];
}

export interface MonthCashFlow {
  month: string;
  total_credit: string;
  total_debit: string;
  net: string;
}

export interface CashFlowResponse {
  months: MonthCashFlow[];
}

export interface AppSettings {
  ocr_provider: 'tesseract' | 'claude' | 'openai';
  anthropic_api_key_set: boolean;
  openai_api_key_set: boolean;
}

export interface SettingsPut {
  ocr_provider: 'tesseract' | 'claude' | 'openai';
  anthropic_api_key?: string | null;
  openai_api_key?: string | null;
}
