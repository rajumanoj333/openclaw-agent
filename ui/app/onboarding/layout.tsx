"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";

/**
 * Onboarding gate: ensures the user is logged in. The individual step
 * pages handle redirecting to the right wizard step.
 */
export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) return null;

  return (
    <main className="min-h-screen flex items-center justify-center px-3 sm:px-6 py-6 sm:py-10">
      <div className="w-full max-w-3xl">{children}</div>
    </main>
  );
}
