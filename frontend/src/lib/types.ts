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

export interface Account {
  id: number;
  name: string;
  type: 'checking' | 'savings' | 'credit_card' | 'cash' | 'broker';
  currency: string;
  institution: string | null;
  last_four: string | null;
  opening_balance: string;
  opening_date: string;
  is_active: boolean;
  current_balance: string;
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
  account_id?: number | null;
  account_created?: boolean;
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
  currency?: string | null;
  converted_amount?: string | null;
  converted_currency?: string | null;
  status?: string;
  transaction_origin?: string;
  parent_transaction_id?: number | null;
  reversed_by?: number | null;
  reversal_of?: number | null;
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
  display_currency?: string | null;
  unconverted_count?: number;
  totals_available?: boolean;
}

export interface MonthCashFlow {
  month: string;
  total_credit: string;
  total_debit: string;
  net: string;
}

export interface CashFlowResponse {
  months: MonthCashFlow[];
  display_currency?: string | null;
  unconverted_count?: number;
  totals_available?: boolean;
}

export interface AppSettings {
  ocr_provider: 'tesseract' | 'claude' | 'openai' | 'gemini' | 'vertex';
  anthropic_api_key_set: boolean;
  openai_api_key_set: boolean;
  review_before_commit?: boolean;
  home_currency?: string | null;
  ai_category_confidence_auto?: number;
  ai_category_confidence_suggest?: number;
  ai_provider?: string;
  ai_model?: string | null;
  ai_api_url?: string | null;
  gemini_api_key_set?: boolean;
  google_project_id?: string | null;
  google_location?: string | null;
}

export interface SettingsPut {
  ocr_provider?: 'tesseract' | 'claude' | 'openai' | 'gemini' | 'vertex';
  anthropic_api_key?: string | null;
  openai_api_key?: string | null;
  review_before_commit?: boolean | null;
  home_currency?: string | null;
  ai_provider?: 'anthropic' | 'openai' | 'gemini' | 'vertex' | 'local' | null;
  ai_model?: string | null;
  ai_api_url?: string | null;
  gemini_api_key?: string | null;
  google_project_id?: string | null;
  google_location?: string | null;
}

export interface StagedTransaction {
  id: number;
  date: string;
  description: string;
  amount: string;
  direction: 'debit' | 'credit';
  category_id: number | null;
}

export interface StagedReviewResponse {
  statement_id: number;
  declared_total: string | null;
  extracted_total: string;
  total_match: boolean;
  transactions: StagedTransaction[];
}

export interface InvestmentTransaction {
  id: number;
  date: string;
  symbol: string;
  direction: 'buy' | 'sell';
  shares: string;
  price_per_share: string;
  amount: string;
  commission: string | null;
  currency: string;
}

export interface PortfolioHolding {
  symbol: string;
  currency: string;
  shares_held: string;
  avg_cost_per_share: string;
  total_cost_basis: string;
  last_price: null;
}

export interface PortfolioResponse {
  account_id: number;
  holdings: PortfolioHolding[];
  last_price_note: string;
}
