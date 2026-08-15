import React, { useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { api, CompareResponse, FundSearchResult } from "../api/client";
import { useModeStore } from "../store/modeStore";
import { colors } from "../theme/colors";

const MAX_BEGINNER = 2;
const MAX_ADVANCED = 5;

function fmtPct(v: number | null | undefined): string {
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function fmtNum(v: number | null | undefined): string {
  return v == null ? "—" : v.toFixed(2);
}

export function CompareScreen() {
  const mode = useModeStore((s) => s.mode);
  const maxFunds = mode === "beginner" ? MAX_BEGINNER : MAX_ADVANCED;

  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<FundSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<FundSearchResult[]>([]);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [loadingCompare, setLoadingCompare] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const resp = await api.searchFunds(query.trim());
      setSearchResults(resp.results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const addFund = (fund: FundSearchResult) => {
    if (selected.length >= maxFunds) return;
    if (selected.some((f) => f.scheme_id === fund.scheme_id)) return;
    setSelected([...selected, fund]);
    setSearchResults([]);
    setQuery("");
    setComparison(null); // stale — user needs to re-run compare
  };

  const removeFund = (schemeId: string) => {
    setSelected(selected.filter((f) => f.scheme_id !== schemeId));
    setComparison(null);
  };

  const runCompare = async () => {
    if (selected.length < 2) return;
    setLoadingCompare(true);
    try {
      const resp = await api.compareFunds(
        selected.map((f) => f.scheme_id),
        mode
      );
      setComparison(resp);
    } catch {
      setComparison(null);
    } finally {
      setLoadingCompare(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Compare Funds</Text>
      <Text style={styles.subtitle}>
        {mode === "beginner"
          ? `Add up to ${MAX_BEGINNER} funds and compare them side by side.`
          : `Add up to ${MAX_ADVANCED} funds and compare across all metrics.`}
      </Text>

      {selected.length > 0 && (
        <View style={styles.chipRow}>
          {selected.map((f) => (
            <TouchableOpacity
              key={f.scheme_id}
              style={styles.chip}
              onPress={() => removeFund(f.scheme_id)}
            >
              <Text style={styles.chipText} numberOfLines={1}>
                {f.scheme_name}
              </Text>
              <Text style={styles.chipRemove}>✕</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {selected.length < maxFunds && (
        <View style={styles.searchRow}>
          <TextInput
            style={styles.input}
            placeholder="Search a fund to add…"
            placeholderTextColor={colors.textSecondary}
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={handleSearch}
            returnKeyType="search"
          />
          <TouchableOpacity style={styles.searchBtn} onPress={handleSearch}>
            <Text style={styles.searchBtnText}>Go</Text>
          </TouchableOpacity>
        </View>
      )}

      {searching && <ActivityIndicator color={colors.accent} style={{ marginTop: 12 }} />}

      {searchResults.map((f) => (
        <TouchableOpacity key={f.scheme_id} style={styles.resultRow} onPress={() => addFund(f)}>
          <Text style={styles.resultText} numberOfLines={1}>
            {f.scheme_name}
          </Text>
          <Text style={styles.resultAdd}>+ Add</Text>
        </TouchableOpacity>
      ))}

      {selected.length >= 2 && (
        <TouchableOpacity style={styles.compareBtn} onPress={runCompare}>
          {loadingCompare ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Text style={styles.compareBtnText}>Compare {selected.length} Funds</Text>
          )}
        </TouchableOpacity>
      )}

      {selected.length === 0 && !searching && searchResults.length === 0 && (
        <View style={styles.placeholder}>
          <Text style={styles.placeholderIcon}>⚖️</Text>
          <Text style={styles.placeholderText}>
            Search for funds above and add them here to compare.
          </Text>
        </View>
      )}

      {comparison && (
        <View style={styles.resultsTable}>
          {comparison.note && <Text style={styles.compareNote}>{comparison.note}</Text>}
          {comparison.schemes.map((s) => (
            <View key={s.scheme_id} style={styles.compareCard}>
              <Text style={styles.compareFundName}>{s.scheme_name}</Text>
              <View style={styles.metricGrid}>
                <Metric label="1Y" value={fmtPct(s.return_1y_pct)} />
                <Metric label="3Y CAGR" value={fmtPct(s.return_3y_cagr_pct)} />
                <Metric label="5Y CAGR" value={fmtPct(s.return_5y_cagr_pct)} />
                <Metric label="Sharpe (3Y)" value={fmtNum(s.sharpe_3y)} />
                <Metric label="Max Drawdown" value={fmtPct(s.max_drawdown_pct)} />
                <Metric label="Health Score" value={s.fund_health_score != null ? s.fund_health_score.toFixed(0) : "—"} />
              </View>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metricBox}>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary },
  content: { padding: 24, paddingBottom: 48 },
  title: { color: colors.text, fontSize: 24, fontWeight: "700", marginBottom: 8 },
  subtitle: { color: colors.textSecondary, fontSize: 14, lineHeight: 20, marginBottom: 20 },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 16 },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceAlt,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 8,
    maxWidth: 220,
  },
  chipText: { color: colors.text, fontSize: 12, fontWeight: "600", flexShrink: 1 },
  chipRemove: { color: colors.textSecondary, fontSize: 12, fontWeight: "700" },
  searchRow: { flexDirection: "row", gap: 10, marginBottom: 8 },
  input: {
    flex: 1,
    backgroundColor: colors.surfaceAlt,
    color: colors.text,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
  },
  searchBtn: {
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingHorizontal: 18,
    justifyContent: "center",
  },
  searchBtnText: { color: colors.primary, fontWeight: "700", fontSize: 14 },
  resultRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    marginTop: 8,
  },
  resultText: { color: colors.text, fontSize: 13, flex: 1, marginRight: 8 },
  resultAdd: { color: colors.accent, fontSize: 12, fontWeight: "700" },
  compareBtn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 20,
  },
  compareBtnText: { color: colors.primary, fontWeight: "700", fontSize: 15 },
  placeholder: {
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 40,
    alignItems: "center",
    gap: 16,
    marginTop: 12,
  },
  placeholderIcon: { fontSize: 48 },
  placeholderText: {
    color: colors.textSecondary,
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
  },
  resultsTable: { marginTop: 24, gap: 16 },
  compareNote: {
    color: colors.textSecondary,
    fontSize: 12,
    fontStyle: "italic",
    marginBottom: 4,
  },
  compareCard: {
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 16,
    gap: 12,
  },
  compareFundName: { color: colors.text, fontSize: 14, fontWeight: "700" },
  metricGrid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  metricBox: { width: "30%" },
  metricValue: { color: colors.accent, fontSize: 15, fontWeight: "700" },
  metricLabel: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
});
