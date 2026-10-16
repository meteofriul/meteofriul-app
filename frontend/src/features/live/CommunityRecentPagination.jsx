import { useEffect, useRef } from "react";

export function CommunityRecentPagination({ loadMore }) {
  const sentinel = useRef(null);
  useEffect(() => {
    if (typeof IntersectionObserver !== "function") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadMore();
    }, { root: sentinel.current?.parentElement, rootMargin: "100px" });
    if (sentinel.current) observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [loadMore]);
  return <span className="mf-recent-list-sentinel" ref={sentinel} aria-hidden="true" />;
}
