import { PULL_REFRESH_STATE } from "../../domain/runtime/pullRefreshPolicy";

export function getPullRefreshFeedbackLabel(pullRefresh, pullRefreshCopy) {
  return {
    [PULL_REFRESH_STATE.ready]: pullRefreshCopy.release,
    [PULL_REFRESH_STATE.refreshing]: pullRefreshCopy.loading,
    [PULL_REFRESH_STATE.success]: pullRefreshCopy.success,
    [PULL_REFRESH_STATE.partial]: pullRefreshCopy.success,
    [PULL_REFRESH_STATE.failed]: pullRefreshCopy.failed,
  }[pullRefresh.state] || pullRefreshCopy.pull;
}
