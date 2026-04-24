import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";

export function PortfolioScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>My Portfolio</Text>
      <Text style={styles.subtitle}>
        Track your mutual fund investments, analyse overlap, and model tax scenarios.
      </Text>

      <View style={styles.placeholder}>
        <Text style={styles.placeholderIcon}>💼</Text>
        <Text style={styles.placeholderText}>
          Portfolio import coming in Phase 2.{"\n"}You'll be able to import via CAS or add
          transactions manually.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary },
  content: { padding: 24 },
  title: { color: colors.text, fontSize: 24, fontWeight: "700", marginBottom: 8 },
  subtitle: { color: colors.textSecondary, fontSize: 14, lineHeight: 20, marginBottom: 32 },
  placeholder: {
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 40,
    alignItems: "center",
    gap: 16,
  },
  placeholderIcon: { fontSize: 48 },
  placeholderText: {
    color: colors.textSecondary,
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
  },
});
