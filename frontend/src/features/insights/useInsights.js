import { useFilteredRequest } from '../analytics/useFilteredRequest.js'
import { getInsights } from './insightsService.js'

/** Insights for the dashboard's selected filters (states as in useFilteredRequest). */
export function useInsights(filters) {
  return useFilteredRequest(getInsights, filters)
}
