"use client";

import { useSearchParams } from "next/navigation";
import { LiveRun } from "@/components/LiveRun";
import { RunProgress } from "@/components/RunProgress";

// /run?id=… streams a real audit; /run without an id replays the sample.
export function RunRouter() {
  const params = useSearchParams();
  const id = params.get("id");
  return id ? <LiveRun id={id} url={params.get("url") ?? ""} /> : <RunProgress />;
}
