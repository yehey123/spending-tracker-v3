import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.spendingtracker.app",
  appName: "Spending Tracker",
  webDir: "out",
  server: {
    androidScheme: "https",
  },
};

export default config;
