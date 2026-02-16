## 1.0.1 (Work in Progress)
- Migration into Holmes Suite Application codebase

## 1.0.0 (Released) — 2026-02-01
- Release in PROD environment for UAT

## 0.7.0 (Released) — 2026-02-01
- Management – Testrig Statistics
  - Refactored dashboard layout with left-side filter panel and 2×2 plot grid
  - Switched data loading to SQL-based Databricks queries
  - Added Year and Sample Type filters aligned with underlying data granularity
  - Ensured consistent filter application across all visualizations
  - Improved page naming and navigation consistency

- Management – Testrig Activity
  - Refactored timeseries activity page layout and structure
  - Moved filters to a left-side panel (time range, location, test rig)
  - Linked all subplots for synchronized zooming and x-axis behavior
  - Synchronized legends across all plots
  - Added reset action to restore filters and legend state
  - Updated statistics page layout and underlying SQL query  

## 0.6.1 (Released) — 2026-02-01
- Fixed sample overview page data source, from gold_genericstack_sample to gold_sample
  
## 0.6.0 (Released) — 2026-02-01
- Added Timeseries viewer
- Added report feedback button 
- Changed table layout (migrated from DataTable to AG grid)
  - Improved visuals
  - Improved sorting option
  - Improved filtering options 
- CSV column sequence fix 
- Minor feedback fixes
  - Reverse order_id filter items in dropdown menu
  - Filter button visuals
  - Added loading spinner to timeseries exploration page
  - Added clause to handle empty data in timeseries exploration page

## 0.5.0 (Released) — 2026-02-01
- Added polarization curve data viewer
- Changed Sherlock logo (removed some bubbles)
- Changed dark mode logos

## 0.4.0 (Released) — 2026-02-01
-  Updated CCM overview:
   - Added a timeline (Gantt) visualization.
   - Timeline-based view using test_id as primary axis
   - Proper ordering by test_id and start time
   - Runtime and CCM labels directly visible on the chart
   - Custom and preset time range selection
   - Improved usability based on stakeholder feedback

## 0.3.0 (Released) — 2026-02-01
- Updated management pages with feedback
- Added CCM overview page in management section

## 0.2.0 (Released) — 2026-02-01
- Dark mode
- Link to versioning documentation
- (New) — 2026-02-01 Logo transparency for dark mode
- updated home page to show all application and logo's

## 0.1.1 (Released) — 2026-02-01
- Removed debug mode from deployment

## 0.1.0 (Released) — 2026-02-01
- Application framework in plotly dash
- Management pages
  - Testrig overview
  - Timeseries explorer lite (past 30 days specific test rigs)
- Sherlock classic features
  - Order browser page
  - Sample browser page
  - Cascading filters (per page)