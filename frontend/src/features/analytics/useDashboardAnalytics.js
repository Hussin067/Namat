import { getDashboardAnalytics } from './analyticsService.js'
import { useFilteredRequest } from './useFilteredRequest.js'

/** Dashboard analytics for the selected filters (see useFilteredRequest for the states). */
export function useDashboardAnalytics(filters) {
  return useFilteredRequest(getDashboardAnalytics, filters)
}
