import { Suspense } from "react";
import { Report } from "@/components/Report";
import type { Metadata } from "next";
import { SAMPLE_AUDIT } from "@/lib/mock";

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: `${SAMPLE_AUDIT.site} report`,
    description: `SEO ${SAMPLE_AUDIT.scores.seo} · AI readiness ${SAMPLE_AUDIT.scores.ai} across ${SAMPLE_AUDIT.templates.length} templates.`,
  };
}

export default function ReportPage() {
  // UI prototype: every report id shows the sample audit.
  return (
    <Suspense>
      <Report audit={SAMPLE_AUDIT} />
    </Suspense>
  );
}
