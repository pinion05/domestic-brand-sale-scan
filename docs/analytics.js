(function (root, factory) {
  const analytics = factory(root);
  if (typeof module === "object" && module.exports) module.exports = analytics;
  if (root) root.SaleAnalytics = analytics;
})(typeof window !== "undefined" ? window : globalThis, function (root) {
  "use strict";

  function event(name, properties) {
    return { name, properties };
  }

  function buildShareUrl(rawUrl, reportDate) {
    const url = new URL(rawUrl);
    url.search = "";
    url.hash = "";
    url.searchParams.set("utm_source", "direct_share");
    url.searchParams.set("utm_medium", "referral");
    url.searchParams.set("utm_campaign", `daily_sale_${String(reportDate).replaceAll("-", "")}`);
    url.searchParams.set("utm_content", "daily_report");
    return url.toString();
  }

  function searchEvent({ resultCount, filter, reportDate }) {
    return event("search_used", {
      result_count: resultCount,
      filter,
      report_date: reportDate,
    });
  }

  function filterEvent(filter, resultCount, reportDate) {
    return event("filter_select", {
      filter,
      result_count: resultCount,
      report_date: reportDate,
    });
  }

  function saleClickEvent(sale, position, section, reportDate) {
    return event("official_store_click", {
      brand: sale.brand,
      tier: sale.tier,
      max_discount: (section === "ends_today" ? sale.urgentMax ?? sale.max : sale.max) || 0,
      urgent: sale.urgent ? "yes" : "no",
      position,
      section,
      report_date: reportDate,
    });
  }

  function shareEvent(channel, reportDate) {
    return event("share_click", {
      channel,
      content_type: "daily_report",
      report_date: reportDate,
    });
  }

  function track(payload) {
    try {
      if (root?.umami && typeof root.umami.track === "function") {
        root.umami.track(payload.name, payload.properties);
      }
    } catch (error) {
      console.warn("Analytics event was not sent", error);
    }
    return payload;
  }

  return {
    buildShareUrl,
    filterEvent,
    saleClickEvent,
    searchEvent,
    shareEvent,
    track,
  };
});
