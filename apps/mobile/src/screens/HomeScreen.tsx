import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, HealthResponse } from "../api/client";
import { useModeStore } from "../store/modeStore";
import { colors } from "../theme/colors";

export function HomeScreen() {
  const insets = useSafeAreaInsets();
  const mode = useModeStore((s) => s.mode);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .health()
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}
    >
      <View style={styles.hero}>
        <Text style={styles.tagline}>See through the noise.</Text>
        <View style={styles.modeBadge}>
          <Text style={styles.modeText}>
            {mode === "beginner" ? "🟢 Guided Investor" : "🔵 Institutional View"}
          </Text>
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>API Status</Text>
        {loading && <ActivityIndicator color={colors.accent} />}
        {error && <Text style={styles.errorText}>⚠ {error}</Text>}
        {health && (
          <View>
            <Text style={styles.statusText}>
              ● {health.status.toUpperCase()}
            </Text>
            <Text style={styles.meta}>
              v{health.version} · {health.environment}
            </Text>
          </View>
        )}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>
          {mode === "beginner" ? "Start Exploring Funds" : "Quick Screener"}
        </Text>
        <Text style={styles.cardBody}>
          {mode === "beginner"
            ? "Search and compare mutual funds to find the right fit for your goals."
            : "Use Explore to filter funds by CAGR, Sharpe, drawdown, and more."}
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary },
  hero: {
    padding: 24,
    paddingTop: 32,
    gap: 12,
  },
  tagline: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "700",
    letterSpacing: -0.5,
  },
  modeBadge: {
    alignSelf: "flex-start",
    backgroundColor: colors.surfaceAlt,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  modeText: { color: colors.accent, fontSize: 13, fontWeight: "600" },
  card: {
    margin: 16,
    marginTop: 0,
    padding: 20,
    backgroundColor: colors.card,
    borderRadius: 14,
    gap: 8,
  },
  cardTitle: { color: colors.text, fontSize: 16, fontWeight: "700" },
  cardBody: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },
  statusText: { color: colors.positive, fontSize: 15, fontWeight: "600" },
  errorText: { color: colors.negative, fontSize: 14 },
  meta: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
});
