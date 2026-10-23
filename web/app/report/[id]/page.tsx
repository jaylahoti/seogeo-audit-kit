import { Suspense } from "react";
import { Report } from "@/components/Report";
import { SAMPLE_AUDIT } from "@/lib/mock";

export default function ReportPage() {
  // UI prototype: every report id shows the sample audit.
  return (
    <Suspense>
      <Report audit={SAMPLE_AUDIT} />
    </Suspense>
  );
}
