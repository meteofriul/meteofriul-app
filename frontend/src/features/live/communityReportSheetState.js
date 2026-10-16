export const COMMUNITY_REPORT_SHEET_OPEN_CLASS = "mf-community-report-open";

export function lockCommunityReportSheetScroll(documentLike = globalThis.document) {
  const documentElement = documentLike?.documentElement;
  if (!documentElement?.classList) return () => {};

  const wasAlreadyLocked = documentElement.classList.contains(
    COMMUNITY_REPORT_SHEET_OPEN_CLASS,
  );
  documentElement.classList.add(COMMUNITY_REPORT_SHEET_OPEN_CLASS);

  return () => {
    if (!wasAlreadyLocked) {
      documentElement.classList.remove(COMMUNITY_REPORT_SHEET_OPEN_CLASS);
    }
  };
}
