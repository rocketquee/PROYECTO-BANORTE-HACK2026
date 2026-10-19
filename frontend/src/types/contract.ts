export type UITone = "positive" | "negative" | "neutral";

export interface Metric {
  label: string;
  value: string;
  delta?: string | null;
  tone?: UITone;
}

export interface FinancialSummarySpec {
  type: "financial_summary";
  title: string;
  metrics: Metric[];
  note?: string | null;
}

export interface CategorySlice {
  category: string;
  amount: number;
  pct: number;
  count?: number | null;
}

export interface SpendingChartSpec {
  type: "spending_chart";
  title: string;
  period: string;
  chart_type: "pie" | "bar";
  series: CategorySlice[];
}

export interface TransactionItem {
  id: number;
  date: string;
  description: string;
  category: string;
  amount: number;
  type: "income" | "expense";
}

export interface TransactionsTableSpec {
  type: "transactions_table";
  title: string;
  period_label: string;
  transactions: TransactionItem[];
  total_count: number;
  categories: string[];
}

export interface SavingsGoalFormSpec {
  type: "savings_goal_form";
  title: string;
  suggested_name?: string | null;
  suggested_amount?: number | null;
  suggested_deadline?: string | null;
}

export interface GoalProgress {
  id: number;
  name: string;
  target_amount: number;
  saved_amount: number;
  progress_pct: number;
  deadline?: string | null;
  status: string;
}

export interface SavingsProgressSpec {
  type: "savings_progress";
  title: string;
  goals: GoalProgress[];
}

export interface CreditParams {
  amount: number;
  months: number;
  annual_rate: number;
  method: "frances" | "aleman";
}

export interface CreditResult {
  monthly_payment: number;
  total_interest: number;
  total_paid: number;
}

export interface ScheduleRow {
  n: number;
  payment: number;
  interest: number;
  principal: number;
  balance: number;
}

export interface CreditSimulatorSpec {
  type: "credit_simulator";
  title: string;
  params: CreditParams;
  result: CreditResult;
  schedule: ScheduleRow[];
  disclaimer: string;
}

export interface BudgetCategory {
  category: string;
  spent: number;
  limit: number;
  pct?: number | null;
}

export interface BudgetPlannerSpec {
  type: "budget_planner";
  title: string;
  month: string;
  income: number;
  total_spent: number;
  available: number;
  categories: BudgetCategory[];
}

export interface RecommendationItem {
  title: string;
  detail: string;
  kind: "fact" | "suggestion";
  basis: string;
}

export interface RecommendationListSpec {
  type: "recommendation_list";
  title: string;
  items: RecommendationItem[];
}

export type UISpec =
  | FinancialSummarySpec
  | SpendingChartSpec
  | TransactionsTableSpec
  | SavingsGoalFormSpec
  | SavingsProgressSpec
  | CreditSimulatorSpec
  | BudgetPlannerSpec
  | RecommendationListSpec;

export const AUTHORIZED_COMPONENTS = [
  "financial_summary",
  "spending_chart",
  "transactions_table",
  "savings_goal_form",
  "savings_progress",
  "credit_simulator",
  "budget_planner",
  "recommendation_list",
] as const;

export interface PendingAction {
  id: string;
  action: "create_savings_goal";
  params: Record<string, unknown>;
  description: string;
}

export interface ChatResponse {
  message: string;
  mode: "demo" | "live";
  ui: UISpec[];
  tools_used: string[];
  pending_action?: PendingAction | null;
  interaction_context?: Record<string, unknown>;
}

export interface DashboardData {
  total_balance: number;
  accounts: { id: number; name: string; type: string; balance: number; currency: string }[];
  cards: { id: number; name: string; type: string; last4: string; balance: number; credit_limit: number }[];
  summary: {
    month_label: string;
    income: number;
    expense: number;
    net: number;
    transaction_count: number;
  };
  categories: CategorySlice[];
  monthly_series: { month: string; label: string; income: number; expense: number }[];
  goals: GoalProgress[];
  recent_transactions: TransactionItem[];
  budget_overview: {
    month: string;
    income: number;
    total_spent: number;
    available: number;
    categories: BudgetCategory[];
  };
}
