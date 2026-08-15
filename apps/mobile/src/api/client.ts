const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}

export interface FundSearchResult {
  scheme_id: string;
  scheme_name: string;
  amc_name: string;
  category: string;
  sub_category: string;
  plan: string;
  option: string;
  nav?: number;
  aum_cr?: number;
}

export interface FundSearchResponse {
  query: string;
  total: number;
  results: FundSearchResult[];
}

export interface FundHealthScore {
  overall: number | null;
  returns_consistency: number | null;
  risk_containment: number | null;
  risk_adjusted_efficiency: number | null;
  portfolio_quality: number | null;
  stability_governance: number | null;
  cost_efficiency: number | null;
  confidence: "high" | "medium" | "low" | null;
}

export interface BeginnerSummary {
  scheme_id: string;
  scheme_name: string;
  mode: "beginner";
  fund_health_score: FundHealthScore;
  yearly_growth_rate_3y: number | null;
  did_it_beat_index_3y: boolean | null;
  risk_level: string | null;
  expense_ratio_pct: number | null;
  fund_age_years: number | null;
  verdict: string | null;
  sip_note: string | null;
}

export interface ReturnMetrics {
  period: string;
  absolute_return_pct: number | null;
  cagr_pct: number | null;
  vs_benchmark_pct: number | null;
  vs_category_avg_pct: number | null;
  category_percentile: number | null;
}

export interface RiskMetrics {
  std_dev_annualized: number | null;
  beta: number | null;
  max_drawdown_pct: number | null;
  downside_capture_ratio: number | null;
  upside_capture_ratio: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
}

export interface AdvancedSummary {
  scheme_id: string;
  scheme_name: string;
  mode: "advanced";
  fund_health_score: FundHealthScore;
  return_metrics: ReturnMetrics[];
  risk_metrics: RiskMetrics | null;
  expense_ratio_pct: number | null;
  aum_cr: number | null;
  fund_age_years: number | null;
  fund_manager: string | null;
  manager_tenure_years: number | null;
  benchmark: string | null;
  sebi_category: string | null;
}

export type FundSummary = BeginnerSummary | AdvancedSummary;

export interface CompareSchemeSlot {
  scheme_id: string;
  scheme_name: string;
  category: string;
  expense_ratio_pct: number | null;
  nav: number | null;
  return_1y_pct: number | null;
  return_3y_cagr_pct: number | null;
  return_5y_cagr_pct: number | null;
  std_dev_3y: number | null;
  sharpe_3y: number | null;
  max_drawdown_pct: number | null;
  fund_health_score: number | null;
}

export interface CompareResponse {
  mode: "beginner" | "advanced";
  schemes: CompareSchemeSlot[];
  note: string | null;
}

async function fetchJSON<T>(
  path: string,
  params?: Record<string, string>
): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => fetchJSON<HealthResponse>("/health"),
  searchFunds: (q: string) =>
    fetchJSON<FundSearchResponse>("/funds/search", { q }),
  getFundSummary: (schemeId: string, mode: "beginner" | "advanced") =>
    fetchJSON<FundSummary>(`/funds/${schemeId}/summary`, { mode }),
  compareFunds: (schemeIds: string[], mode: "beginner" | "advanced") =>
    fetchJSON<CompareResponse>("/compare", {
      scheme_ids: schemeIds.join(","),
      mode,
    }),
};