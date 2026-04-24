import React, { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { api, FundSearchResult } from "../api/client";
import { useModeStore } from "../store/modeStore";
import { colors } from "../theme/colors";

export function ExploreScreen() {
  const mode = useModeStore((s) => s.mode);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<FundSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const resp = await api.searchFunds(query.trim());
      setResults(resp.results);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.searchRow}>
        <TextInput
          style={styles.input}
          placeholder="Search fund name, AMC, category…"
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

      {loading && (
        <ActivityIndicator style={{ marginTop: 32 }} color={colors.accent} />
      )}

      {!loading && searched && results.length === 0 && (
        <Text style={styles.emptyText}>No funds found for "{query}"</Text>
      )}

      <FlatList
        data={results}
        keyExtractor={(item) => item.scheme_id}
        contentContainerStyle={{ padding: 16 }}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.fundName}>{item.scheme_name}</Text>
            <Text style={styles.meta}>
              {item.amc_name} · {item.sub_category}
            </Text>
            <View style={styles.row}>
              {item.nav != null && (
                <Text style={styles.tag}>NAV ₹{item.nav.toFixed(2)}</Text>
              )}
              {mode === "advanced" && item.aum_cr != null && (
                <Text style={styles.tag}>
                  AUM ₹{(item.aum_cr / 100).toFixed(0)}Cr
                </Text>
              )}
            </View>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary },
  searchRow: {
    flexDirection: "row",
    padding: 16,
    gap: 10,
  },
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
  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    gap: 6,
  },
  fundName: { color: colors.text, fontSize: 14, fontWeight: "600" },
  meta: { color: colors.textSecondary, fontSize: 12 },
  row: { flexDirection: "row", gap: 8, marginTop: 4 },
  tag: {
    backgroundColor: colors.surfaceAlt,
    color: colors.accent,
    fontSize: 11,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  emptyText: {
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: 48,
    fontSize: 14,
  },
});
