import React from "react";
import {
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useModeStore } from "../store/modeStore";
import { colors } from "../theme/colors";

export function ProfileScreen() {
  const insets = useSafeAreaInsets();
  const { mode, toggleMode } = useModeStore();

  const isAdvanced = mode === "advanced";

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}
    >
      <View style={styles.header}>
        <Text style={styles.avatar}>👤</Text>
        <Text style={styles.username}>Investor</Text>
        <Text style={styles.tagline}>All features unlocked · Free</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Analysis Mode</Text>

        <View style={styles.modeCard}>
          <View style={styles.modeInfo}>
            <Text style={styles.modeTitle}>
              {isAdvanced ? "Institutional View" : "Guided Investor"}
            </Text>
            <Text style={styles.modeDesc}>
              {isAdvanced
                ? "Full metric suite — ratios, matrices, heatmaps."
                : "Simplified view — plain language, verdict chips."}
            </Text>
          </View>
          <Switch
            value={isAdvanced}
            onValueChange={toggleMode}
            trackColor={{ false: colors.border, true: colors.accent }}
            thumbColor={colors.white}
          />
        </View>

        <View style={styles.modeLabels}>
          <Text style={[styles.modeLabel, !isAdvanced && styles.modeLabelActive]}>
            Beginner
          </Text>
          <Text style={[styles.modeLabel, isAdvanced && styles.modeLabelActive]}>
            Advanced
          </Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About FundLens</Text>
        <View style={styles.infoCard}>
          <Text style={styles.infoText}>
            FundLens is a fully free mutual fund evaluation platform for Indian investors.
            Both Beginner and Advanced modes are completely unlocked — no paywall, no subscription.
          </Text>
          <Text style={[styles.infoText, { marginTop: 8 }]}>
            Version 0.1.0 · Open Beta
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary },
  header: {
    alignItems: "center",
    padding: 32,
    gap: 8,
  },
  avatar: { fontSize: 56 },
  username: { color: colors.text, fontSize: 20, fontWeight: "700" },
  tagline: { color: colors.accent, fontSize: 13 },
  section: { paddingHorizontal: 16, marginBottom: 24 },
  sectionTitle: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: 12,
  },
  modeCard: {
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
  },
  modeInfo: { flex: 1 },
  modeTitle: { color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: 4 },
  modeDesc: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  modeLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 8,
    marginTop: 8,
  },
  modeLabel: { color: colors.textSecondary, fontSize: 12 },
  modeLabelActive: { color: colors.accent, fontWeight: "600" },
  infoCard: {
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 20,
  },
  infoText: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },
});
