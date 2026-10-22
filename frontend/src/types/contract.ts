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

export interface SavingsContributionCandidate {
  goal_id: number;
  goal_name: string;
  target_amount: number;
  saved_amount: number;
}

export interface SavingsContributionSpec {
  type: "savings_contribution";
  status: "select_goal" | "confirm_required" | "completed";
  goal_id?: number | null;
  goal_name?: string | null;
  target_amount?: number | null;
  saved_amount?: number | null;
  remaining_before?: number | null;
  contribution_amount?: number | null;
  remaining_after?: number | null;
  available_balance?: number | null;
  confirmation_token?: string | null;
  idempotency_key?: string | null;
  candidates: SavingsContributionCandidate[];
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

export interface PurchaseOption {
  option_id: "cash" | "savings_12" | "credit_12" | "credit_18" | "credit_24";
  kind: "cash" | "savings" | "credit";
  label: string;
  amount: number;
  months?: number | null;
  monthly_payment: number;
  total_cost: number;
  monthly_balance_after: number;
}

export interface PurchasePlanSpec {
  type: "purchase_plan";
  title: string;
  purchase_amount: number;
  current_balance: number;
  balance_after_cash_purchase: number;
  monthly_balance: number;
  fixed_payments_monthly: number;
  annual_rate: number;
  options: PurchaseOption[];
  selected_option_id?: PurchaseOption["option_id"] | null;
  goal_status: "not_requested" | "confirm_required" | "created";
  goal_name?: string | null;
  goal_deadline?: string | null;
  goal_confirmation_token?: string | null;
  goal_idempotency_key?: string | null;
  goal_created_id?: number | null;
  disclaimer: string;
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

export interface TrendPoint {
  label: string;
  amount: number;
  month?: string | null;
}

export interface TrendChartSpec {
  type: "trend_chart";
  title: string;
  period: string;
  chart_type: "line" | "bar" | "area";
  series: TrendPoint[];
  conclusion?: string | null;
}

export interface ComparisonRow {
  label: string;
  value_a: string;
  value_b: string;
}

export interface ComparisonSpec {
  type: "comparison";
  title: string;
  column_a: string;
  column_b: string;
  rows: ComparisonRow[];
}

export interface TimelineItem {
  date: string;
  title: string;
  detail: string;
}

export interface TimelineSpec {
  type: "timeline";
  title: string;
  items: TimelineItem[];
}

export interface AlertItem {
  severity: "info" | "warning" | "critical";
  title: string;
  detail: string;
}

export interface AlertListSpec {
  type: "alert_list";
  title: string;
  items: AlertItem[];
}

export type UISpec =
  | FinancialSummarySpec
  | SpendingChartSpec
  | TransactionsTableSpec
  | SavingsGoalFormSpec
  | SavingsProgressSpec
  | SavingsContributionSpec
  | CreditSimulatorSpec
  | PurchasePlanSpec
  | BudgetPlannerSpec
  | RecommendationListSpec
  | TrendChartSpec
  | ComparisonSpec
  | TimelineSpec
  | AlertListSpec;

export const AUTHORIZED_COMPONENTS = [
  "financial_summary",
  "spending_chart",
  "transactions_table",
  "savings_goal_form",
  "savings_progress",
  "savings_contribution",
  "credit_simulator",
  "purchase_plan",
  "budget_planner",
  "recommendation_list",
  "trend_chart",
  "comparison",
  "timeline",
  "alert_list",
] as const;

export interface PendingAction {
  id: string;
  action: "create_savings_goal";
  params: Record<string, unknown>;
  description: string;
}

export interface ChatResponse {
  schema_version: "1.0";
  trace_id?: string | null;
  message: string;
  mode: "demo" | "live";
  ui: UISpec[];
  tools_used: string[];
  suggestions?: string[];
  pending_action?: PendingAction | null;
  interaction_context?: Record<string, unknown>;
}

export type UIEvent =
  | {
      id: string;
      type: "purchase_option_selected";
      payload: { option_id: PurchaseOption["option_id"] };
      trace_id: string;
    }
  | {
      id: string;
      type: "purchase_goal_create_requested";
      payload: { option_id: "savings_12" };
      trace_id: string;
    }
  | {
      id: string;
      type: "purchase_goal_confirmed";
      payload: {
        option_id: "savings_12";
        confirmation_token: string;
        idempotency_key: string;
      };
      trace_id: string;
    }
  | {
      id: string;
      type: "savings_goal_selected";
      payload: { goal_id: number };
      trace_id: string;
    }
  | {
      id: string;
      type: "savings_contribution_amount_changed";
      payload: { amount: number };
      trace_id: string;
    }
  | {
      id: string;
      type: "savings_contribution_confirmed";
      payload: {
        goal_id: number;
        amount: number;
        confirmation_token: string;
        idempotency_key: string;
      };
      trace_id: string;
    };

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
