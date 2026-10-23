import { Suspense } from "react";
import { RunProgress } from "@/components/RunProgress";

export default function RunPage() {
  return (
    <Suspense>
      <RunProgress />
    </Suspense>
  );
}
