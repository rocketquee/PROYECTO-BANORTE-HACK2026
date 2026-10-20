"use client";

import { AUTHORIZED_COMPONENTS, UISpec } from "@/types/contract";
import FinancialSummary from "./FinancialSummary";
import SpendingChart from "./SpendingChart";
import TransactionsTable from "./TransactionsTable";
import SavingsGoalForm from "./SavingsGoalForm";
import SavingsProgress from "./SavingsProgress";
import CreditSimulator from "./CreditSimulator";
import BudgetPlanner from "./BudgetPlanner";
import RecommendationList from "./RecommendationList";
import TrendChart from "./TrendChart";
import Comparison from "./Comparison";
import Timeline from "./Timeline";
import AlertList from "./AlertList";

interface RendererProps {
  spec: UISpec;
  onAsk: (message: string) => void;
  onGoalCreated: (name: string, target: number) => void;
  onGoalsChanged: () => void;
  pendingAction?: { id: string; description: string } | null;
  onConfirmPending?: (actionId: string) => Promise<void>;
}

/**
 * Renders ONLY the authorized component types from the validated JSON contract.
 * Unknown types or tampered payloads fall back to an error card — the JSON is
 * never interpreted as executable code.
 */
export default function DynamicRenderer(props: RendererProps) {
  const { spec } = props;
  if (!(AUTHORIZED_COMPONENTS as readonly string[]).includes(spec.type)) {
    return (
      <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-base text-amber-800">
        Componente no autorizado: {String((spec as { type?: string }).type)}
      </div>
    );
  }
  switch (spec.type) {
    case "financial_summary":
      return <FinancialSummary title={spec.title} metrics={spec.metrics} note={spec.note} />;
    case "spending_chart":
      return <SpendingChart spec={spec} onAsk={props.onAsk} />;
    case "transactions_table":
      return <TransactionsTable spec={spec} />;
    case "savings_goal_form":
      return (
        <SavingsGoalForm
          spec={spec}
          pending={props.pendingAction}
          onCreated={props.onGoalCreated}
          onConfirmPending={props.onConfirmPending}
        />
      );
    case "savings_progress":
      return <SavingsProgress title={spec.title} goals={spec.goals} onChanged={props.onGoalsChanged} />;
    case "credit_simulator":
      return <CreditSimulator spec={spec} onAsk={props.onAsk} />;
    case "budget_planner":
      return (
        <BudgetPlanner
          title={spec.title}
          month={spec.month}
          income={spec.income}
          total_spent={spec.total_spent}
          categories={spec.categories}
        />
      );
    case "recommendation_list":
      return <RecommendationList spec={spec} />;
    case "trend_chart":
      return <TrendChart spec={spec} />;
    case "comparison":
      return <Comparison spec={spec} />;
    case "timeline":
      return <Timeline spec={spec} />;
    case "alert_list":
      return <AlertList spec={spec} />;
  }
}
