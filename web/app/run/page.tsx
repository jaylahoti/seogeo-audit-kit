import type { Metadata } from "next";
import { Suspense } from "react";
import { RunRouter } from "@/components/RunRouter";

export const metadata: Metadata = { title: "Running audit" };

export default function RunPage() {
  return (
    <Suspense>
      <RunRouter />
    </Suspense>
  );
}
