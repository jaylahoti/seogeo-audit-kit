// Sample audit used by the UI until the API is wired up. The site is fictional.

export type Severity = "high" | "medium" | "low";
export type Area = "ai" | "seo";

export type Finding = {
  id?: string;
  area: Area;
  severity: Severity;
  title: string;
  detail: string;
  pages: number;
  affected?: number; // sample pages that failed (live audits)
  sampled?: number;
  examples?: string[];
  method?: string; // rule | heuristic | render | psi | crawl | claude
  fix?: { kind: "jsonld" | "html"; label: string; content: string };
};

export type SamplePage = {
  url: string;
  status: number;
  words: number;
  schema: string[];
  title?: string | null;
  ms?: number;
  factsFound?: number; // from Claude's fact-extraction test
  factsTotal?: number;
  lcp?: number;
};

export type Template = {
  id: string;
  pattern: string;
  pages: number;
  seo: number;
  ai: number;
  // Search Console, citations and questions come from connected accounts / Claude.
  submitted?: number;
  indexed?: number;
  clicks?: number;
  impressions?: number;
  cwv?: { lcp: number | null; cls: number | null; inp: number | null; source?: string };
  questions?: string[];
  citation?: { asked: number; cited: number; citedInstead: string[] };
  notIndexedReasons?: { reason: string; share: number }[];
  findings: Finding[];
  samples: SamplePage[];
  examples?: string[];
  passed?: string[];
  evidence?: ClaudeEvidence[]; // what Claude was shown and answered for each sample page
};

export type ClaudeEvidence = {
  url: string;
  shown: { title: string | null; words: number; excerpt: string; jsonld_types: string[] };
  answer: {
    page_type: string;
    facts: { name: string; value: string | null; in_text: boolean; in_structured_data: boolean }[];
    verdict_sentence: string | null;
    facts_up_front: boolean;
    title_matches_intent: boolean;
    better_title_template: string | null;
    questions: { question: string; answered: "yes" | "partial" | "no" }[];
  };
  guardrail: { check: string; passed: boolean; quote: string } | null;
};

export type Stage = { key: string; label: string; detail: string; ms: number; cost: number; tokens?: number; model?: string };

export type Audit = {
  id: string;
  site: string;
  sitemap: string;
  ranAt: string;
  urls: number;
  scores: { seo: number; ai: number };
  cost: number;
  naiveCost: number;
  durationSec: number;
  templates: Template[];
  stages: Stage[];
  inputUrl?: string; // what the user typed (live audits), used by Re-run
  geo?: GeoScore;
  live?: LiveExtras; // present on real audits from the API
};

export type RenderDiffLive = {
  pattern: string; url: string; raw_words: number; rendered_words: number; raw_links: number;
  rendered_links: number; raw_jsonld: number; rendered_jsonld: number; js_only_headings: string[];
  js_text_share: number; error: string | null;
};

export type GeoSignal = { label: string; detail: string; impact: number };
export type GeoScore = {
  score: number | null;
  partial: boolean;
  access: { score: number; signals: GeoSignal[] };
  readiness: { score: number | null; method?: string };
  visibility: { score: number | null; reason?: string; asked?: number; confidence?: number; engines?: { name: string; cited: number; asked: number; live: boolean }[] };
};

export type FamilyStat = { family: string; files_total: number; files_read: number; urls_listed: number; urls_sampled: number; estimated: number };

export type ExactCount = {
  status: "running" | "done" | "error";
  files_total: number;
  files_done: number;
  files_failed: number;
  urls: number;
  families: Record<string, { files: number; urls: number }>;
  templates: Record<string, number>;
  unmatched: number;
  error: string | null;
};

export type ClaudePage = {
  page_type: string | null; pages: number; facts_in_text: number | null; facts_in_structured_data: number | null;
  missing_facts: string[]; verdicts: string[]; has_verdict: number | null; facts_up_front: number | null;
  title_matches_intent: number | null; better_title_template: string | null;
  questions: { question: string; answered: "yes" | "partial" | "no" }[];
};
export type VisibilityAnswer = { engine?: string; page_type: string; question: string; status: "cited" | "found" | "missing" | "not_searched"; position: number | null; cited_instead: string[]; answer: string };
export type Visibility = {
  score: number | null; asked?: number; cited?: number; found_not_cited?: number; reason?: string;
  answers: VisibilityAnswer[]; share_of_voice: { domain: string; share: number; you: boolean }[];
  engines?: { name: string; cited: number; asked: number; found_not_cited?: number; score?: number | null; errors?: number; live: boolean }[];
};
export type Judgement = {
  summary: string;
  top_fixes: { page_type: string; title: string; why: string; effort: "low" | "medium" | "high" }[];
  template_fixes: { page_type: string; notes: string; jsonld: string | null; jsonld_valid?: boolean; jsonld_rejected?: string; verdict_html: string | null; title_template: string | null }[];
};
export type GapRow = { page_type: string; question: string; answered_on_page: "yes" | "partial" | "no"; facts_extractable: number | null; ai_cites_site: "cited" | "found" | "missing" | null };
export type Monitoring = {
  previous_id: string | null; previous_at: number | null;
  changes: { severity: "high" | "medium" | "low"; kind: string; title: string; detail: string; pages: number; page_type: string | null }[];
  trend: { id: string; at: number; seo: number | null; ai: number | null; geo: number | null }[];
  monitors: { id: string; every_hours: number; next_run_at: number }[];
};

export type CrawlerBot = {
  name: string; operator: string; kind: "training" | "ai_search" | "ai_user" | "search"; hits: number;
  by_page_type: Record<string, number>; status: Record<string, number>; error_rate: number;
  last_seen: number | null; special: Record<string, number>; verification: string; spoofed: number;
};
export type CrawlerLogs = {
  analyzed_at: number; synthetic: boolean; lines: number; unread_lines: number; asset_requests: number; other_requests: number;
  from: number | null; to: number | null; ai_hits: number; ai_error_rate: number; llms_txt_fetched_by: string[];
  bots: CrawlerBot[];
  page_types: { pattern: string; estimated_pages: number; ai_hits: number; search_hits: number; ai_distinct_pages: number; ai_coverage: number | null }[];
  top_errors: { bot: string; page_type: string; status: number; count: number; example: string }[];
  daily: { day: string; ai?: number; search?: number }[];
  spoofed: number;
};

export type LiveExtras = {
  crawlerLogs: CrawlerLogs | null;
  claudeSkipped: string | null; // why Claude didn't run on this audit (e.g. the demo's daily budget)
  claudeEnabled: boolean;
  claudeSpent: number;
  claudeBudget: number;
  claudeCalls: { stage: string; model: string; input_tokens: number; output_tokens: number; searches: number; cost: number; ms: number; ok: boolean }[];
  claudePages: Record<string, ClaudePage>;
  visibility: Visibility | null;
  judge: Judgement | null;
  gaps: GapRow[];
  monitoring: Monitoring | null;
  sitemapSource: "sitemap" | "links";
  pageCount: { leavesTotal: number; leavesRead: number; urlsSampled: number; families: FamilyStat[]; estimatedTotal: number };
  exactCount: ExactCount | null;
  robots: { found: boolean; sitemaps: string[]; ai_crawlers: { agent: string; kind: string; allowed: boolean }[]; blocked_retrieval_bots: string[] };
  llmsTxt: { found: boolean; title: string | null; sections: string[]; links: number; issues: string[] };
  render: RenderDiffLive[];
  cwvErrors: string[];
  fixes: { llms_txt: string; robots_txt: string };
  links: { depth: Record<string, number | null>; bfs_pages: number; probed: number; broken: { target: string; status: number; found_on: string | null }[]; redirecting: { target: string; to: string; hops: number }[] };
  siteFindings: { id: string; severity: Severity; title: string; detail: string }[];
  ml: { pages: number; layouts: number; noise: number; points: { x: number; y: number; layout: number; url: string }[] };
  crawl: { requested: number; ok: number; non_200: number; errors: number; blocked_by_robots: number; avg_ms: number };
};

const BUILDING_JSONLD = `{
  "@context": "https://schema.org",
  "@type": "ApartmentComplex",
  "name": "{{building.name}}",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "{{building.street}}",
    "addressLocality": "{{building.city}}",
    "postalCode": "{{building.zip}}"
  },
  "numberOfAccommodationUnits": {{building.units}},
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": {{building.rating}},
    "reviewCount": {{building.reviews}}
  }
}`;

const SUMMARY_HTML = `<section class="summary">
  <h2>{{building.name}} at a glance</h2>
  <p>{{building.units}} units in {{building.neighborhood}}.
     Rents from {{rent.min}} to {{rent.max}}.
     Rated {{building.rating}}/5 by {{building.reviews}} renters.</p>
</section>`;

const FAQ_JSONLD = `{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "Is {{neighborhood.name}} safe?",
    "acceptedAnswer": { "@type": "Answer", "text": "{{neighborhood.safety_summary}}" }
  }]
}`;

export const SAMPLE_AUDIT: Audit = {
  id: "demo-nestlist",
  site: "nestlist.example",
  sitemap: "https://nestlist.example/sitemap.xml",
  ranAt: "2026-10-22T14:05:00Z",
  urls: 4812,
  scores: { seo: 71, ai: 48 },
  cost: 0.11,
  naiveCost: 38.4,
  durationSec: 94,
  geo: {
    score: 50,
    partial: false,
    access: {
      score: 62,
      signals: [
        { label: "robots.txt blocks PerplexityBot", detail: "Retrieval bots fetch pages to answer live questions.", impact: -25 },
        { label: "No /llms.txt", detail: "A short guide for AI assistants to the site and its key pages.", impact: -10 },
        { label: "6% of text needs JavaScript (weighted by pages)", detail: "Worst: /buildings/{slug} at 78%.", impact: -3 },
      ],
    },
    readiness: { score: 48, method: "rules + claude" },
    visibility: {
      score: 41,
      engines: [
        { name: "Claude", cited: 3, asked: 6, live: true },
        { name: "ChatGPT", cited: 3, asked: 6, live: false },
        { name: "Perplexity", cited: 3, asked: 6, live: false },
        { name: "Gemini", cited: 1, asked: 6, live: false },
      ],
    },
  },
  stages: [
    { key: "ingest", label: "Read sitemap", detail: "3 sitemaps · 4,812 URLs", ms: 3100, cost: 0 },
    { key: "crawl", label: "Crawl sample", detail: "180 pages fetched · robots.txt respected", ms: 21400, cost: 0 },
    { key: "cluster", label: "Detect templates", detail: "HDBSCAN on URL + DOM features → 6 templates", ms: 420, cost: 0 },
    { key: "sample", label: "Pick sample pages", detail: "5 per template · 30 pages", ms: 40, cost: 0 },
    { key: "seo", label: "SEO checks", detail: "14 rule checks × 30 pages", ms: 1900, cost: 0 },
    { key: "cwv", label: "Core Web Vitals", detail: "PageSpeed Insights · 12 pages", ms: 38200, cost: 0 },
    { key: "facts", label: "Fact extraction", detail: "30 pages", ms: 9800, cost: 0.018, tokens: 132000, model: "Haiku 5.5" },
    { key: "cite", label: "Citation check", detail: "18 questions with web search", ms: 12600, cost: 0.004, tokens: 21000, model: "Haiku 5.5" },
    { key: "judge", label: "Judge and fixes", detail: "Rank findings, write JSON-LD, validate", ms: 6500, cost: 0.088, tokens: 31000, model: "Sonnet 5.5" },
  ],
  templates: [
    {
      id: "t1",
      pattern: "/buildings/{slug}",
      pages: 3940,
      seo: 64,
      ai: 31,
      submitted: 3940,
      indexed: 1302,
      clicks: 18400,
      impressions: 912000,
      cwv: { lcp: 3.4, cls: 0.21, inp: 240 },
      questions: [
        "How much is rent at {building}?",
        "Is {building} pet friendly?",
        "What do tenants say about {building}?",
      ],
      citation: { asked: 6, cited: 1, citedInstead: ["streeteasy.com", "apartments.com", "reddit.com"] },
      notIndexedReasons: [
        { reason: "Crawled – currently not indexed", share: 0.61 },
        { reason: "Duplicate without user-selected canonical", share: 0.27 },
        { reason: "Discovered – not crawled", share: 0.12 },
      ],
      findings: [
        {
          area: "ai",
          severity: "high",
          title: "No JSON-LD for the building",
          detail: "Claude pulled the right address from 1 of 5 sample pages. Without structured data, AI answers can't reliably quote these pages.",
          pages: 3940,
          fix: { kind: "jsonld", label: "Add to the building template", content: BUILDING_JSONLD },
        },
        {
          area: "ai",
          severity: "medium",
          title: "Key answer buried below the fold",
          detail: "Rent range first appears after ~600 words. Put a short summary block at the top.",
          pages: 3940,
          fix: { kind: "html", label: "Summary block", content: SUMMARY_HTML },
        },
        {
          area: "seo",
          severity: "high",
          title: "82% near-duplicate text across pages",
          detail: "Boilerplate dominates; unique data is under 18% of each page. Likely cause of 'Crawled – currently not indexed'.",
          pages: 3940,
        },
        {
          area: "seo",
          severity: "medium",
          title: "Missing canonical on paginated reviews",
          detail: "/buildings/{slug}?page=N pages have no canonical and compete with the main page.",
          pages: 1210,
        },
        {
          area: "seo",
          severity: "medium",
          title: "LCP 3.4s on mobile",
          detail: "Hero image is 1.8 MB and not preloaded. Target is under 2.5s.",
          pages: 3940,
        },
        {
          area: "seo",
          severity: "low",
          title: "Titles over 60 characters",
          detail: "Titles get cut off in results. Shorten the template.",
          pages: 2870,
        },
      ],
      samples: [
        { url: "/buildings/the-larkin-210-w-77th", status: 200, words: 1420, schema: ["BreadcrumbList"], factsFound: 2, factsTotal: 6, lcp: 3.6 },
        { url: "/buildings/harbor-view-88-river-st", status: 200, words: 1310, schema: ["BreadcrumbList"], factsFound: 1, factsTotal: 6, lcp: 3.1 },
        { url: "/buildings/maple-court-12", status: 200, words: 980, schema: [], factsFound: 3, factsTotal: 6, lcp: 3.9 },
        { url: "/buildings/park-lane-tower", status: 200, words: 1650, schema: ["BreadcrumbList"], factsFound: 2, factsTotal: 6, lcp: 2.9 },
        { url: "/buildings/the-ashford-401", status: 301, words: 0, schema: [], factsFound: 0, factsTotal: 6, lcp: 0 },
      ],
    },
    {
      id: "t2",
      pattern: "/neighborhoods/{slug}",
      pages: 310,
      seo: 78,
      ai: 55,
      submitted: 310,
      indexed: 251,
      clicks: 9100,
      impressions: 301000,
      cwv: { lcp: 2.3, cls: 0.04, inp: 160 },
      questions: ["Is {neighborhood} safe?", "Average rent in {neighborhood}?", "Best buildings in {neighborhood}?"],
      citation: { asked: 6, cited: 2, citedInstead: ["niche.com", "nytimes.com"] },
      notIndexedReasons: [{ reason: "Crawled – currently not indexed", share: 1 }],
      findings: [
        {
          area: "ai",
          severity: "medium",
          title: "FAQ answers not marked up",
          detail: "Pages answer common questions but have no FAQPage schema.",
          pages: 310,
          fix: { kind: "jsonld", label: "Add FAQPage", content: FAQ_JSONLD },
        },
        { area: "seo", severity: "medium", title: "42 orphan pages", detail: "In the sitemap but no internal links point to them.", pages: 42 },
      ],
      samples: [
        { url: "/neighborhoods/upper-west-side", status: 200, words: 2100, schema: ["Place", "BreadcrumbList"], factsFound: 4, factsTotal: 5, lcp: 2.2 },
        { url: "/neighborhoods/astoria", status: 200, words: 1870, schema: ["Place"], factsFound: 3, factsTotal: 5, lcp: 2.4 },
        { url: "/neighborhoods/park-slope", status: 200, words: 1990, schema: ["Place", "BreadcrumbList"], factsFound: 4, factsTotal: 5, lcp: 2.1 },
      ],
    },
    {
      id: "t3",
      pattern: "/landlords/{slug}",
      pages: 286,
      seo: 69,
      ai: 44,
      submitted: 286,
      indexed: 140,
      clicks: 2300,
      impressions: 88000,
      cwv: { lcp: 2.8, cls: 0.09, inp: 190 },
      questions: ["Is {landlord} a good landlord?", "How many buildings does {landlord} own?"],
      citation: { asked: 4, cited: 0, citedInstead: ["yelp.com", "reddit.com"] },
      notIndexedReasons: [
        { reason: "Crawled – currently not indexed", share: 0.7 },
        { reason: "Soft 404", share: 0.3 },
      ],
      findings: [
        { area: "ai", severity: "high", title: "Rating shown only as an image", detail: "Star rating is an SVG with no text, so neither search nor AI can read it.", pages: 286 },
        { area: "seo", severity: "medium", title: "Thin pages for small landlords", detail: "61 pages under 150 words. Merge or noindex until they have data.", pages: 61 },
      ],
      samples: [
        { url: "/landlords/northbridge-mgmt", status: 200, words: 640, schema: ["Organization"], factsFound: 2, factsTotal: 4, lcp: 2.7 },
        { url: "/landlords/a-and-l-realty", status: 200, words: 120, schema: [], factsFound: 1, factsTotal: 4, lcp: 2.9 },
      ],
    },
    {
      id: "t4",
      pattern: "/near/{station}-station",
      pages: 172,
      seo: 81,
      ai: 62,
      submitted: 172,
      indexed: 160,
      clicks: 3400,
      impressions: 97000,
      cwv: { lcp: 2.0, cls: 0.03, inp: 140 },
      questions: ["Apartments near {station}?", "Rent near {station}?"],
      citation: { asked: 4, cited: 2, citedInstead: ["zillow.com"] },
      notIndexedReasons: [{ reason: "Discovered – not crawled", share: 1 }],
      findings: [{ area: "ai", severity: "low", title: "No distance data in text", detail: "Walk times are in a map widget only.", pages: 172 }],
      samples: [{ url: "/near/72nd-st-station", status: 200, words: 900, schema: ["Place"], factsFound: 3, factsTotal: 4, lcp: 1.9 }],
    },
    {
      id: "t5",
      pattern: "/blog/{slug}",
      pages: 64,
      seo: 88,
      ai: 81,
      submitted: 64,
      indexed: 63,
      clicks: 1200,
      impressions: 41000,
      cwv: { lcp: 1.7, cls: 0.02, inp: 110 },
      questions: ["How to negotiate rent?"],
      citation: { asked: 2, cited: 1, citedInstead: ["nerdwallet.com"] },
      notIndexedReasons: [{ reason: "Duplicate, Google chose different canonical", share: 1 }],
      findings: [{ area: "seo", severity: "low", title: "3 posts missing meta descriptions", detail: "Google writes its own snippet.", pages: 3 }],
      samples: [{ url: "/blog/how-to-negotiate-rent", status: 200, words: 1800, schema: ["Article"], factsFound: 4, factsTotal: 4, lcp: 1.6 }],
    },
    {
      id: "t6",
      pattern: "/{static}",
      pages: 40,
      seo: 92,
      ai: 70,
      submitted: 40,
      indexed: 40,
      clicks: 5200,
      impressions: 60000,
      cwv: { lcp: 1.5, cls: 0.01, inp: 100 },
      questions: [],
      citation: { asked: 0, cited: 0, citedInstead: [] },
      notIndexedReasons: [],
      findings: [{ area: "ai", severity: "low", title: "No llms.txt", detail: "Optional, but helps AI crawlers find key pages.", pages: 1 }],
      samples: [{ url: "/about", status: 200, words: 700, schema: ["Organization"], factsFound: 3, factsTotal: 3, lcp: 1.4 }],
    },
  ],
};

export const SAMPLE_REPORTS = [
  { id: "demo-nestlist", site: "nestlist.example", kind: "Rental listings", urls: 4812, templates: 6, ai: 48, seo: 71, geo: 50 },
  { id: "demo-nestlist", site: "tripstack.example", kind: "Travel guides", urls: 3120, templates: 5, ai: 57, seo: 76, geo: 61 },
  { id: "demo-nestlist", site: "stackcompare.example", kind: "SaaS comparisons", urls: 1940, templates: 4, ai: 66, seo: 83, geo: 70 },
  { id: "demo-nestlist", site: "jobsnear.example", kind: "Job listings", urls: 4990, templates: 7, ai: 39, seo: 62, geo: 44 },
];

export const fmt = (n: number) => n.toLocaleString("en-US");
export const money = (n: number) => (n < 1 ? `$${n.toFixed(2)}` : `$${n.toFixed(2)}`);
