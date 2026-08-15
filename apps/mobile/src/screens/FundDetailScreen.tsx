import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { api, AdvancedSummary, BeginnerSummary, FundSummary } from "../api/client";
import { useModeStore } from "../store/modeStore";
import { colors } from "../theme/colors";

interface Props {
  route: { params: { schemeId: string; schemeName?: string } };
}

function isAdvanced(summary: FundSummary): summary is AdvancedSummary {
  return summary.mode === "advanced";
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metricRow}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  return v == null ? "—" : v.toFixed(digits);
}

function verdictColor(verdict: string | null | undefined): string {
  if (verdict === "Strong") return colors.positive;
  if (verdict === "Weak") return colors.negative;
  return colors.accent;
}

export function FundDetailScreen({ route }: Props) {
  const { schemeId, schemeName } = route.params;
  const mode = useModeStore((s) => s.mode);
  const [summary, setSummary] = useState<FundSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getFundSummary(schemeId, mode)
      .then(setSummary)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [schemeId, mode]);

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (error || !summary) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>
          Couldn't load this fund{error ? `: ${error}` : ""}
        </Text>
      </View>
    );
  }

  const health = summary.fund_health_score;

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.fundName}>{schemeName ?? summary.scheme_name}</Text>

      <View style={styles.healthCard}>
        <Text style={styles.healthScore}>
          {health.overall != null ? health.overall.toFixed(0) : "—"}
        </Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.healthLabel}>Health Score</Text>
          {health.confidence && (
            <Text style={styles.healthConfidence}>
              {health.confidence} confidence — directional estimate, not a
              validated rating
            </Text>
          )}
        </View>
      </View>

      {!isAdvanced(summary) ? (
        <BeginnerBody summary={summary} />
      ) : (
        <AdvancedBody summary={summary} />
      )}
    </ScrollView>
  );
}

function BeginnerBody({ summary }: { summary: BeginnerSummary }) {
  return (
    <View style={styles.section}>
      <View style={[styles.verdictBadge, { borderColor: verdictColor(summary.verdict) }]}>
        <Text style={[styles.verdictText, { color: verdictColor(summary.verdict) }]}>
          {summary.verdict ?? "Insufficient Data"}
        </Text>
      </View>

      <View style={styles.card}>
        <Metric label="3Y Growth Rate" value={fmtPct(summary.yearly_growth_rate_3y)} />
        <Metric label="Risk Level" value={summary.risk_level ?? "—"} />
        <Metric label="Fund Age" value={summary.fund_age_years ? `${summary.fund_age_years.toFixed(1)} yrs` : "—"} />
        <Metric label="Expense Ratio" value={summary.expense_ratio_pct != null ? `${summary.expense_ratio_pct}%` : "Not yet available"} />
      </View>

      {summary.sip_note && (
        <View style={styles.noteCard}>
          <Text style={styles.noteText}>{summary.sip_note}</Text>
        </View>
      )}
    </View>
  );
}

function AdvancedBody({ summary }: { summary: AdvancedSummary }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Returns by Period</Text>
      <View style={styles.card}>
        {summary.return_metrics.map((rm) => (
          <Metric key={rm.period} label={`${rm.period} CAGR`} value={fmtPct(rm.cagr_pct)} />
        ))}
      </View>

      <Text style={styles.sectionTitle}>Risk Metrics</Text>
      <View style={styles.card}>
        <Metric label="Std Dev (annualized)" value={fmtPct(summary.risk_metrics?.std_dev_annualized)} />
        <Metric label="Sharpe Ratio" value={fmtNum(summary.risk_metrics?.sharpe_ratio)} />
        <Metric label="Max Drawdown" value={fmtPct(summary.risk_metrics?.max_drawdown_pct)} />
        <Metric label="Sortino Ratio" value={summary.risk_metrics?.sortino_ratio != null ? fmtNum(summary.risk_metrics.sortino_ratio) : "Not yet available"} />
      </View>

      <Text style={styles.sectionTitle}>Fund Details</Text>
      <View style={styles.card}>
        <Metric label="Category" value={summary.sebi_category ?? "—"} />
        <Metric label="Fund Age" value={summary.fund_age_years ? `${summary.fund_age_years.toFixed(1)} yrs` : "—"} />
        <Metric label="Expense Ratio" value={summary.expense_ratio_pct != null ? `${summary.expense_ratio_pct}%` : "Not yet available"} />
        <Metric label="AUM" value={summary.aum_cr != null ? `₹${summary.aum_cr.toFixed(0)}Cr` : "Not yet available"} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary },
  centerContainer: {
    flex: 1,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  errorText: { color: colors.negative, fontSize: 14, textAlign: "center" },
  fundName: { color: colors.text, fontSize: 20, fontWeight: "700", marginBottom: 16 },
  healthCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 20,
    marginBottom: 20,
  },
  healthScore: { color: colors.accent, fontSize: 36, fontWeight: "800" },
  healthLabel: { color: colors.text, fontSize: 14, fontWeight: "600" },
  healthConfidence: { color: colors.textSecondary, fontSize: 11, marginTop: 4, lineHeight: 15 },
  section: { gap: 12 },
  sectionTitle: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: 1,
    textTransform: "uppercase",
    marginTop: 8,
  },
  verdictBadge: {
    alignSelf: "flex-start",
    borderWidth: 1.5,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  verdictText: { fontSize: 14, fontWeight: "700" },
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 16,
    gap: 12,
  },
  metricRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  metricLabel: { color: colors.textSecondary, fontSize: 13 },
  metricValue: { color: colors.text, fontSize: 14, fontWeight: "600" },
  noteCard: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 12,
    padding: 14,
  },
  noteText: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
});