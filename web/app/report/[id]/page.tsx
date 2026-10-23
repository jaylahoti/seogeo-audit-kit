import type { Metadata } from "next";
import { Suspense } from "react";
import { ReportLoader } from "@/components/ReportLoader";
import { SAMPLE_AUDIT } from "@/lib/mock";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: id === SAMPLE_AUDIT.id ? `${SAMPLE_AUDIT.site} report (sample)` : "Audit report" };
}

export default async function ReportPage({ params }: Props) {
  const { id } = await params;
  return (
    <Suspense>
      <ReportLoader id={id} />
    </Suspense>
  );
}
