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
    fetchJSON<unknown>(`/funds/${schemeId}/summary`, { mode }),
  compareFunds: (schemeIds: string[], mode: "beginner" | "advanced") =>
    fetchJSON<unknown>("/compare", {
      scheme_ids: schemeIds.join(","),
      mode,
    }),
};
