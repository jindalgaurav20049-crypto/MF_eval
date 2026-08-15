import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Text } from "react-native";

import { HomeScreen } from "../screens/HomeScreen";
import { ExploreScreen } from "../screens/ExploreScreen";
import { FundDetailScreen } from "../screens/FundDetailScreen";
import { CompareScreen } from "../screens/CompareScreen";
import { PortfolioScreen } from "../screens/PortfolioScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { colors } from "../theme/colors";

export type ExploreStackParamList = {
  ExploreList: undefined;
  FundDetail: { schemeId: string; schemeName?: string };
};

export type RootTabParamList = {
  Home: undefined;
  Explore: undefined;
  Compare: undefined;
  Portfolio: undefined;
  Profile: undefined;
};

const Tab = createBottomTabNavigator<RootTabParamList>();
const ExploreStack = createNativeStackNavigator<ExploreStackParamList>();

function ExploreStackNavigator() {
  return (
    <ExploreStack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.primary },
        headerTintColor: colors.white,
        headerTitleStyle: { fontWeight: "bold" },
      }}
    >
      <ExploreStack.Screen
        name="ExploreList"
        component={ExploreScreen}
        options={{ title: "Explore" }}
      />
      <ExploreStack.Screen
        name="FundDetail"
        component={FundDetailScreen}
        options={({ route }) => ({ title: route.params.schemeName ?? "Fund Detail" })}
      />
    </ExploreStack.Navigator>
  );
}

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  const icons: Record<string, string> = {
    Home: "🏠",
    Explore: "🔍",
    Compare: "⚖️",
    Portfolio: "💼",
    Profile: "👤",
  };
  return (
    <Text style={{ fontSize: focused ? 22 : 20, opacity: focused ? 1 : 0.5 }}>
      {icons[label] ?? "●"}
    </Text>
  );
}

export function RootNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.primary },
        headerTintColor: colors.white,
        headerTitleStyle: { fontWeight: "bold" },
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
        },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarIcon: ({ focused }) => (
          <TabIcon label={route.name} focused={focused} />
        ),
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen
        name="Explore"
        component={ExploreStackNavigator}
        options={{ headerShown: false }}
      />
      <Tab.Screen name="Compare" component={CompareScreen} />
      <Tab.Screen name="Portfolio" component={PortfolioScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}