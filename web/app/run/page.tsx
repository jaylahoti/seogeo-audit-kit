import type { Metadata } from "next";
import { Suspense } from "react";

export const metadata: Metadata = { title: "Running audit" };
import { RunProgress } from "@/components/RunProgress";

export default function RunPage() {
  return (
    <Suspense>
      <RunProgress />
    </Suspense>
  );
}
