// Sample data for the 13 report modules. Fictional site; replaced by API data later.

export type Access = "free" | "claude" | "connect" | "key";

export type ModuleDef = { id: string; label: string; group: "Audit" | "Connect" | "Track" | "Lab"; access: Access; num?: number };

export const MODULES: ModuleDef[] = [
  { id: "overview", label: "Overview", group: "Audit", access: "free" },
  { id: "technical", label: "Technical SEO", group: "Audit", access: "free", num: 1 },
  { id: "cwv", label: "Core Web Vitals", group: "Audit", access: "free", num: 3 },
  { id: "ai", label: "AI readiness", group: "Audit", access: "claude", num: 4 },
  { id: "whatai", label: "What AI sees", group: "Audit", access: "free", num: 7 },
  { id: "fixes", label: "Fixes", group: "Audit", access: "claude", num: 12 },
  { id: "gsc", label: "Search Console", group: "Connect", access: "connect", num: 2 },
  { id: "bing", label: "Bing Webmaster", group: "Connect", access: "connect", num: 8 },
  { id: "traffic", label: "AI referral traffic", group: "Connect", access: "connect", num: 9 },
  { id: "visibility", label: "AI visibility", group: "Track", access: "claude", num: 5 },
  { id: "crawlers", label: "AI crawlers", group: "Track", access: "free", num: 6 },
  { id: "monitoring", label: "Monitoring", group: "Track", access: "free", num: 10 },
  { id: "gaps", label: "Question gaps", group: "Track", access: "claude", num: 13 },
  { id: "ci", label: "CI and MCP", group: "Track", access: "free", num: 11 },
  { id: "ml", label: "ML Lab", group: "Lab", access: "free" },
  { id: "trace", label: "Under the hood", group: "Lab", access: "free" },
];

// Need the visitor's own accounts, so they arrive with self-hosting. Shown with sample data until then.
export const COMING_SOON = new Set(["gsc", "bing", "traffic"]);

export const ACCESS_LABEL: Record<Access, string> = {
  free: "Free",
  claude: "Claude",
  connect: "Connect",
  key: "Your key",
};

// --- Module 1: technical SEO ---------------------------------------------------
export type TechCheck = { check: string; category: string; severity: "high" | "medium" | "low"; affected: { pattern: string; pages: number }[] };

export const TECH_CHECKS: TechCheck[] = [
  { check: "Near-duplicate content (>80% similar)", category: "Content", severity: "high", affected: [{ pattern: "/buildings/{slug}", pages: 3940 }] },
  { check: "Missing canonical tag", category: "Indexability", severity: "medium", affected: [{ pattern: "/buildings/{slug}", pages: 1210 }] },
  { check: "Thin content (<150 words)", category: "Content", severity: "medium", affected: [{ pattern: "/landlords/{slug}", pages: 61 }] },
  { check: "Sitemap URLs returning errors (404)", category: "Sitemap", severity: "medium", affected: [{ pattern: "/neighborhoods/{slug}", pages: 42 }, { pattern: "/near/{station}-station", pages: 9 }] },
  { check: "Title longer than 60 characters", category: "Metadata", severity: "low", affected: [{ pattern: "/buildings/{slug}", pages: 2870 }, { pattern: "/landlords/{slug}", pages: 40 }] },
  { check: "Missing meta description", category: "Metadata", severity: "low", affected: [{ pattern: "/blog/{slug}", pages: 3 }] },
  { check: "Sitemap URLs that redirect", category: "Sitemap", severity: "medium", affected: [{ pattern: "/buildings/{slug}", pages: 188 }] },
  { check: "Sitemap lastmod older than 180 days", category: "Sitemap", severity: "low", affected: [{ pattern: "/landlords/{slug}", pages: 286 }] },
  { check: "Images without alt text", category: "Accessibility", severity: "low", affected: [{ pattern: "/buildings/{slug}", pages: 3940 }] },
  { check: "Link depth more than 4 clicks", category: "Linking", severity: "medium", affected: [{ pattern: "/buildings/{slug}", pages: 2210 }] },
];

export const TECH_PASSED = ["HTTPS everywhere", "No noindex on sitemap URLs", "Single H1 per page", "hreflang not needed (one locale)", "No redirect chains longer than 1 hop", "robots.txt allows all templates"];

// --- Module 4: AI readiness ------------------------------------------------------
export type AiRow = {
  pattern: string;
  jsonld: "valid" | "invalid" | "missing";
  fresh: boolean;
  verdict: boolean;
  answerFirst: boolean;
  noPlaceholders?: boolean; // live audits
  facts: number | null; // Claude's fact-extraction score; null until Claude checks run
  titleIntent: boolean | null; // Claude; null until Claude checks run
};

export const AI_ROWS: AiRow[] = [
  { pattern: "/buildings/{slug}", jsonld: "missing", fresh: false, verdict: false, answerFirst: false, facts: 0.2, titleIntent: false },
  { pattern: "/neighborhoods/{slug}", jsonld: "valid", fresh: true, verdict: true, answerFirst: true, facts: 0.75, titleIntent: true },
  { pattern: "/landlords/{slug}", jsonld: "invalid", fresh: false, verdict: false, answerFirst: true, facts: 0.5, titleIntent: false },
  { pattern: "/near/{station}-station", jsonld: "valid", fresh: true, verdict: false, answerFirst: true, facts: 0.75, titleIntent: true },
  { pattern: "/blog/{slug}", jsonld: "valid", fresh: true, verdict: true, answerFirst: true, facts: 1, titleIntent: true },
];

export const AI_CRAWLERS = [
  { agent: "OAI-SearchBot", kind: "retrieval", allowed: true },
  { agent: "ChatGPT-User", kind: "retrieval", allowed: true },
  { agent: "PerplexityBot", kind: "retrieval", allowed: false },
  { agent: "Claude-User", kind: "retrieval", allowed: true },
  { agent: "GPTBot", kind: "training", allowed: false },
  { agent: "ClaudeBot", kind: "training", allowed: true },
  { agent: "CCBot", kind: "training", allowed: false },
  { agent: "Google-Extended", kind: "training", allowed: true },
];

export const LLMS_TXT = { found: false, issues: ["No /llms.txt at nestlist.example"] };

// --- Module 7: what AI sees ------------------------------------------------------
export type RenderDiff = { pattern: string; rawWords: number; renderedWords: number; rawLinks: number; renderedLinks: number; jsonldRaw: boolean; jsonldRendered: boolean; jsOnly: string[] };

export const RENDER_DIFFS: RenderDiff[] = [
  { pattern: "/buildings/{slug}", rawWords: 310, renderedWords: 1420, rawLinks: 22, renderedLinks: 96, jsonldRaw: false, jsonldRendered: true, jsOnly: ["Rent range", "Tenant reviews", "Violation counts", "Nearby buildings links"] },
  { pattern: "/landlords/{slug}", rawWords: 520, renderedWords: 640, rawLinks: 40, renderedLinks: 52, jsonldRaw: true, jsonldRendered: true, jsOnly: ["Star rating"] },
  { pattern: "/neighborhoods/{slug}", rawWords: 2080, renderedWords: 2100, rawLinks: 140, renderedLinks: 141, jsonldRaw: true, jsonldRendered: true, jsOnly: [] },
  { pattern: "/near/{station}-station", rawWords: 880, renderedWords: 900, rawLinks: 60, renderedLinks: 64, jsonldRaw: true, jsonldRendered: true, jsOnly: ["Walk times (map widget)"] },
];

// --- Module 12: fix generators ---------------------------------------------------
export const GENERATED_LLMS_TXT = `# Nestlist

> Nestlist lists NYC rental buildings with verified tenant reviews,
> rents and building records.

Entity pages are too many to list here. Full set: https://nestlist.example/sitemap.xml

## Entity pages

- [Buildings](https://nestlist.example/buildings): One page per building — rating, reviews, rents.
- [Landlords](https://nestlist.example/landlords): One page per owner or manager.

## Guides

- [Neighborhoods](https://nestlist.example/neighborhoods): Renting guides by neighborhood.
- [Blog](https://nestlist.example/blog): How-tos for NYC renters.`;

export const GENERATED_ROBOTS = `# Retrieval bots answer live questions — keep them allowed.
User-agent: OAI-SearchBot
User-agent: ChatGPT-User
User-agent: PerplexityBot
User-agent: Claude-User
Allow: /

User-agent: *
Allow: /
Disallow: /api/

Sitemap: https://nestlist.example/sitemap.xml`;

export const VERDICT_EXAMPLE = `<p class="verdict">
  {{building.name}} is rated {{building.rating}}/5 by {{building.reviews}} renters,
  with {{building.open_violations}} open violations — {{verdict_label}} than most
  buildings in {{building.neighborhood}}.
</p>`;

export const TITLE_EXAMPLE = {
  before: "{{building.name}} - Apartments for Rent in {{neighborhood}} | Nestlist",
  after: "{{building.name}} Reviews, Rents and Violations | Nestlist",
  why: "People ask about reviews and rents for a specific building; the current title leads with listings.",
};

// --- Module 8: Bing --------------------------------------------------------------
export const BING_ROWS = [
  { pattern: "/buildings/{slug}", submitted: 3940, bing: 610, google: 1302 },
  { pattern: "/neighborhoods/{slug}", submitted: 310, bing: 198, google: 251 },
  { pattern: "/landlords/{slug}", submitted: 286, bing: 51, google: 140 },
  { pattern: "/near/{station}-station", submitted: 172, bing: 120, google: 160 },
  { pattern: "/blog/{slug}", submitted: 64, bing: 60, google: 63 },
];

// --- Module 9: AI referral traffic -----------------------------------------------
export const ENGINES = ["ChatGPT", "Perplexity", "Gemini", "Claude", "Copilot"] as const;
export const ENGINE_COLORS: Record<(typeof ENGINES)[number], string> = {
  ChatGPT: "#1f9e89",
  Perplexity: "#3b82c4",
  Gemini: "#d9822b",
  Claude: "#c2407a",
  Copilot: "#7a8a2e",
};
export const TRAFFIC_WEEKS = ["Aug 31", "Sep 7", "Sep 14", "Sep 21", "Sep 28", "Oct 5", "Oct 12", "Oct 19"];
export const TRAFFIC_TREND: Record<(typeof ENGINES)[number], number[]> = {
  ChatGPT: [310, 342, 380, 402, 455, 498, 540, 611],
  Perplexity: [120, 118, 131, 140, 152, 149, 166, 171],
  Gemini: [40, 44, 52, 61, 58, 66, 74, 80],
  Claude: [18, 22, 25, 24, 31, 35, 38, 44],
  Copilot: [12, 11, 14, 16, 15, 17, 19, 18],
};
export const TRAFFIC_BY_TEMPLATE = [
  { pattern: "/buildings/{slug}", visits: 3120, conv: 0.041 },
  { pattern: "/neighborhoods/{slug}", visits: 1840, conv: 0.028 },
  { pattern: "/blog/{slug}", visits: 690, conv: 0.012 },
  { pattern: "/landlords/{slug}", visits: 310, conv: 0.035 },
  { pattern: "/near/{station}-station", visits: 260, conv: 0.019 },
];

// --- Module 5: AI visibility -----------------------------------------------------
export type Cell = { cited: boolean; pos?: number };
export type VisQuestion = { q: string; family: string; template: string; results: Record<(typeof ENGINES)[number], Cell | null>; citedInstead: string[] };

export const VIS_ENGINES_LIVE: Record<(typeof ENGINES)[number], boolean> = { Claude: true, ChatGPT: false, Perplexity: false, Gemini: false, Copilot: false };

export const VIS_QUESTIONS: VisQuestion[] = [
  { q: "Is The Larkin on W 77th a good building?", family: "Building verdict", template: "/buildings/{slug}", results: { Claude: { cited: true, pos: 2 }, ChatGPT: { cited: true, pos: 1 }, Perplexity: { cited: false }, Gemini: { cited: false }, Copilot: null }, citedInstead: ["reddit.com", "streeteasy.com"] },
  { q: "Reviews of Harbor View, 88 River St", family: "Building reviews", template: "/buildings/{slug}", results: { Claude: { cited: false }, ChatGPT: { cited: false }, Perplexity: { cited: true, pos: 3 }, Gemini: { cited: false }, Copilot: null }, citedInstead: ["apartments.com", "yelp.com"] },
  { q: "Is Astoria safe to rent in?", family: "Neighborhood", template: "/neighborhoods/{slug}", results: { Claude: { cited: true, pos: 1 }, ChatGPT: { cited: true, pos: 2 }, Perplexity: { cited: true, pos: 1 }, Gemini: { cited: false }, Copilot: null }, citedInstead: ["niche.com"] },
  { q: "Is Northbridge Management a good landlord?", family: "Landlord", template: "/landlords/{slug}", results: { Claude: { cited: false }, ChatGPT: { cited: false }, Perplexity: { cited: false }, Gemini: { cited: false }, Copilot: null }, citedInstead: ["yelp.com", "reddit.com", "bbb.org"] },
  { q: "Apartments near 72nd St station", family: "Transit", template: "/near/{station}-station", results: { Claude: { cited: true, pos: 3 }, ChatGPT: { cited: false }, Perplexity: { cited: true, pos: 2 }, Gemini: { cited: true, pos: 4 }, Copilot: null }, citedInstead: ["zillow.com"] },
  { q: "How do I negotiate rent in NYC?", family: "How-to", template: "/blog/{slug}", results: { Claude: { cited: false }, ChatGPT: { cited: true, pos: 4 }, Perplexity: { cited: false }, Gemini: { cited: false }, Copilot: null }, citedInstead: ["nerdwallet.com", "nytimes.com"] },
];

export const SHARE_OF_VOICE = [
  { domain: "nestlist.example", share: 0.18, you: true },
  { domain: "streeteasy.com", share: 0.24 },
  { domain: "reddit.com", share: 0.21 },
  { domain: "apartments.com", share: 0.14 },
  { domain: "yelp.com", share: 0.09 },
];

// --- Module 6: AI crawlers (from access logs) -------------------------------------
export const CRAWLER_TEMPLATES = ["/buildings/{slug}", "/neighborhoods/{slug}", "/landlords/{slug}", "/blog/{slug}"];
export const CRAWLER_HITS: { agent: string; kind: string; hits: number[]; errors: number; lastSeen: string }[] = [
  { agent: "OAI-SearchBot", kind: "retrieval", hits: [4210, 880, 190, 120], errors: 0.012, lastSeen: "2 min ago" },
  { agent: "ChatGPT-User", kind: "retrieval", hits: [1120, 640, 40, 210], errors: 0.004, lastSeen: "11 min ago" },
  { agent: "PerplexityBot", kind: "retrieval", hits: [0, 0, 0, 0], errors: 0, lastSeen: "Blocked by robots.txt" },
  { agent: "GPTBot", kind: "training", hits: [0, 0, 0, 0], errors: 0, lastSeen: "Blocked by robots.txt" },
  { agent: "ClaudeBot", kind: "training", hits: [2890, 310, 260, 64], errors: 0.031, lastSeen: "1 hr ago" },
  { agent: "Googlebot", kind: "search", hits: [18400, 2210, 1430, 410], errors: 0.006, lastSeen: "just now" },
  { agent: "Bingbot", kind: "search", hits: [3020, 640, 280, 120], errors: 0.009, lastSeen: "4 min ago" },
];
export const CRAWL_COVERAGE = [
  { pattern: "/buildings/{slug}", pages: 3940, crawledByAI: 0.29 },
  { pattern: "/neighborhoods/{slug}", pages: 310, crawledByAI: 0.92 },
  { pattern: "/landlords/{slug}", pages: 286, crawledByAI: 0.41 },
  { pattern: "/blog/{slug}", pages: 64, crawledByAI: 1 },
];

// --- Module 10: monitoring ---------------------------------------------------------
export const RUNS = [
  { date: "Sep 21", seo: 74, ai: 52 },
  { date: "Sep 28", seo: 74, ai: 53 },
  { date: "Oct 5", seo: 75, ai: 55 },
  { date: "Oct 12", seo: 73, ai: 56 },
  { date: "Oct 19", seo: 71, ai: 48 },
];
export const ALERTS = [
  { when: "Oct 19, 09:12", severity: "high" as const, title: "JSON-LD disappeared from /buildings/{slug}", detail: "Present on Oct 12, missing on all 5 samples today. Likely the Oct 17 deploy.", pages: 3940 },
  { when: "Oct 19, 09:12", severity: "medium" as const, title: "LCP regressed on /buildings/{slug}", detail: "2.6s → 3.4s p75 mobile.", pages: 3940 },
  { when: "Oct 12, 09:10", severity: "low" as const, title: "PerplexityBot blocked in robots.txt", detail: "Retrieval bot — this removes the site from Perplexity answers.", pages: 4812 },
];

// --- Module 13: question gaps -----------------------------------------------------
export type Gap = { family: string; example: string; template: string; exists: boolean; answers: "yes" | "partial" | "no"; extractable: "yes" | "partial" | "no"; fix: string; priority: "P0" | "P1" | "P2" };
export const GAPS: Gap[] = [
  { family: "Building verdict", example: "is {building} a good building?", template: "/buildings/{slug}", exists: true, answers: "partial", extractable: "no", fix: "Verdict sentence", priority: "P0" },
  { family: "Building reviews", example: "reviews of {building}", template: "/buildings/{slug}", exists: true, answers: "yes", extractable: "partial", fix: "Title template + Review schema", priority: "P0" },
  { family: "Landlord reputation", example: "is {landlord} a good landlord?", template: "/landlords/{slug}", exists: true, answers: "partial", extractable: "no", fix: "Text rating + verdict", priority: "P0" },
  { family: "Neighborhood safety", example: "is {neighborhood} safe?", template: "/neighborhoods/{slug}", exists: true, answers: "yes", extractable: "yes", fix: "—", priority: "P2" },
  { family: "Rent by area", example: "average rent in {neighborhood}", template: "—", exists: false, answers: "no", extractable: "no", fix: "New template: /rent/{neighborhood}", priority: "P1" },
  { family: "Comparisons", example: "{neighborhood} vs {neighborhood}", template: "—", exists: false, answers: "no", extractable: "no", fix: "New template: /compare/{a}-vs-{b}", priority: "P1" },
];

// --- Module 11: CI and MCP ---------------------------------------------------------
export const GH_ACTION = `# .github/workflows/seogeo-audit-kit.yml
name: SEOGEO Audit Kit
on: [pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: jaylahoti/seogeo-audit-kit/action@main
        with:
          url: \${{ steps.deploy.outputs.preview-url }}
          fail-on: "geo<60,high-issues>0,missing-jsonld"
          anthropic-api-key: \${{ secrets.ANTHROPIC_API_KEY }}  # optional`;

export const MCP_CONFIG = `{
  "mcpServers": {
    "seogeo-audit-kit": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/jaylahoti/seogeo-audit-kit#subdirectory=api", "seogeo-audit-mcp"],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-..." }
    }
  }
}`;

export const MCP_TOOLS = [
  ["audit_site", "Run a full audit on a site or sitemap; returns page types, scores and top fixes"],
  ["get_report", "The saved report for an audit id"],
  ["get_page_type", "Findings and ready-to-paste fixes for one page type"],
  ["check_page", "Run every check on a single URL, in seconds"],
  ["get_llms_txt", "The generated llms.txt for an audited site"],
];
