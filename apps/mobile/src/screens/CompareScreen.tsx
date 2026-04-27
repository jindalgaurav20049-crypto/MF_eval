import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { useModeStore } from "../store/modeStore";
import { colors } from "../theme/colors";

export function CompareScreen() {
  const mode = useModeStore((s) => s.mode);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Compare Funds</Text>
      <Text style={styles.subtitle}>
        {mode === "beginner"
          ? "Add up to 2 funds and compare them side by side."
          : "Add up to 5 funds and compare across all metrics."}
      </Text>

      <View style={styles.placeholder}>
        <Text style={styles.placeholderIcon}>⚖️</Text>
        <Text style={styles.placeholderText}>
          Search for funds in Explore and add them here to compare.
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
