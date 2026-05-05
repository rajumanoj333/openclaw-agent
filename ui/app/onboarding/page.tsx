"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";

const ROUTE_BY_STEP: Record<string, string> = {
  scrape: "/onboarding/business",
  confirm: "/onboarding/confirm",
  agent: "/onboarding/agent",
  ready: "/chat",
};

export default function OnboardingIndex() {
  const router = useRouter();

  useEffect(() => {
    api
      .onboardingStatus()
      .then((s) => router.replace(ROUTE_BY_STEP[s.step] || "/onboarding/business"))
      .catch(() => router.replace("/onboarding/business"));
  }, [router]);

  return null;
}
