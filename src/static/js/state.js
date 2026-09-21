/**
 * Reach — Global State Management (src/static/js/state.js)
 */

window.state = {
  activeTab: 'tabAnalytics',
  expFilter: 'ALL',
  categoryFilter: 'EMAIL_OUTREACH',
  genStatusFilter: 'PENDING',
  sourceFilter: 'ALL',
  othersFilter: 'ALL',
  pendingCancelPostId: null,
  searchQuery: '',
  searchReview: '',
  searchSent: '',
  page: 1,
  limit: 25,
  total: 0,
  posts: [],
  selectedIds: new Set(),
  selectedDraftIds: new Set(),
  reviewPosts: [],
  activeReviewPost: null,
  sentPosts: [],
  sentPage: 1,
  sentLimit: 25,
  sentTotal: 0,
  config: {},
  health: {},
  pollingTimer: null,
  healthTimer: null,
  showLogs: false,
  awaitingSentPost: null,
  analyticsDays: 30,
  analyticsData: null,
  charts: {},
  sortBy: 'default',
  dateFilter: 'ALL',
  othersReason: 'ALL',
  locationFilter: 'ALL',
  discoveredReason: 'ALL',
};

Object.defineProperty(window, 'currentTab', {
  get() { return window.state ? window.state.activeTab : 'tabAnalytics'; },
  set(val) { if (window.state) window.state.activeTab = val; }
});

window.DEFAULT_OPPORTUNITY_SUBJECT = "Full-Stack Software Engineer – Job Opportunities";
window.DEFAULT_OPPORTUNITY_BODY = `Hi,

I’m Mohammed Rinshad, a Full-Stack Software Engineer with 3+ years of experience in web and enterprise application development.

My experience includes React, Next.js, Node.js, TypeScript, .NET Core, REST APIs, PostgreSQL, SQL Server, Azure, GCP, CI/CD, authentication, RBAC, and database design. I’ve worked on ERP, accounting, education, and enterprise applications, including both frontend and backend development.

I’m currently looking for opportunities in Frontend, Backend, Full-Stack, DevOps, or Cloud Engineering. I’m open to relocating for the right opportunity and am also interested in remote roles.

I’ve attached my resume for reference. If there are any current or upcoming openings that match my background, I’d be grateful to be considered.

Regards,
Mohammed Rinshad P
+91 98956 12423
rinshadmorayur09@gmail.com
LinkedIn: linkedin.com/in/mrinshad
GitHub: github.com/mrinshad`;

window.dialogResolver = null;
