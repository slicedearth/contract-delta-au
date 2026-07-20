import type { ChangeEvent } from "../types";
import { formatDate, formatValue } from "./format";
import {
  CHANGE_PAGE_SIZE,
  getChangePage,
  getChangePageCount,
  getChangePaginationItems
} from "./pagination";

interface Filters {
  query: string;
  agency: string;
  field: string;
  direction: string;
}

type HistoryMode = "none" | "push" | "replace";

const FILTER_NAMES = ["query", "agency", "field", "direction"] as const;
const FILTER_PAGE_PARAMETER = "filtered-page";
const FILTER_NOTE =
  "Filters and the filtered CSV cover all published events. Results are shown 50 per page.";
const FILTER_ERROR =
  "Full-dataset filters could not be loaded. Static pagination remains available.";

let cachedEventsUrl: string | undefined;
let cachedEventsPromise: Promise<ChangeEvent[]> | undefined;
let activePopstateHandler: ((event: PopStateEvent) => void) | undefined;
let paginationNavigationPending = false;

const isHttpUrl = (value: string) => {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
};

const isChangeEvent = (value: unknown): value is ChangeEvent => {
  if (typeof value !== "object" || value === null) return false;
  const event = value as Partial<ChangeEvent>;
  return (
    typeof event.event_id === "string" &&
    typeof event.contract_id === "string" &&
    typeof event.notice_id === "string" &&
    typeof event.detected_at === "string" &&
    typeof event.field_name === "string" &&
    typeof event.field_label === "string" &&
    typeof event.direction === "string" &&
    typeof event.summary === "string" &&
    typeof event.source_url === "string" &&
    isHttpUrl(event.source_url) &&
    typeof event.official_record_url === "string" &&
    isHttpUrl(event.official_record_url)
  );
};

const loadAllEvents = (url: string): Promise<ChangeEvent[]> => {
  if (cachedEventsUrl === url && cachedEventsPromise) return cachedEventsPromise;

  cachedEventsUrl = url;
  cachedEventsPromise = fetch(url, {
    headers: { Accept: "application/json" }
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`Dataset request returned ${response.status}`);
      const payload: unknown = await response.json();
      if (!Array.isArray(payload) || !payload.every(isChangeEvent)) {
        throw new Error("Dataset response did not match the published event schema");
      }
      return payload;
    })
    .catch((error: unknown) => {
      cachedEventsPromise = undefined;
      throw error;
    });

  return cachedEventsPromise;
};

const alignResults = () => {
  const target = document.getElementById("change-results");
  if (!target) return;

  const scrollBehaviour = document.documentElement.style.scrollBehavior;
  document.documentElement.style.scrollBehavior = "auto";
  const stickyOffset = Number.parseFloat(window.getComputedStyle(target).top) || 0;
  const targetTop = window.scrollY + target.getBoundingClientRect().top - stickyOffset;
  window.scrollTo({ top: targetTop, left: 0 });
  document.documentElement.style.scrollBehavior = scrollBehaviour;
};

document.addEventListener("astro:before-preparation", (event) => {
  paginationNavigationPending = Boolean(event.sourceElement?.closest(".change-pagination"));
});

document.addEventListener("astro:after-swap", () => {
  if (!paginationNavigationPending) return;
  alignResults();
  paginationNavigationPending = false;
});

const readFilters = (form: HTMLFormElement): Filters => {
  const values = new FormData(form);
  return {
    query: String(values.get("query") ?? "").trim(),
    agency: String(values.get("agency") ?? ""),
    field: String(values.get("field") ?? ""),
    direction: String(values.get("direction") ?? "")
  };
};

const hasActiveFilters = (filters: Filters) =>
  FILTER_NAMES.some((name) => filters[name].length > 0);

const searchableText = (event: ChangeEvent) => {
  const agency = event.agency_name?.trim() || "Agency not reported";
  const supplier = event.supplier_name?.trim() || "Supplier not reported";
  const description = event.description?.trim() || "Contract record";
  return [
    event.contract_id,
    event.notice_id,
    agency,
    supplier,
    description,
    event.field_label,
    event.summary
  ]
    .join(" ")
    .toLocaleLowerCase("en-AU");
};

const matchesFilters = (event: ChangeEvent, filters: Filters) => {
  const agency = event.agency_name?.trim() || "Agency not reported";
  const query = filters.query.toLocaleLowerCase("en-AU");
  return (
    (!query || searchableText(event).includes(query)) &&
    (!filters.agency || agency === filters.agency) &&
    (!filters.field || event.field_name === filters.field) &&
    (!filters.direction || event.direction === filters.direction)
  );
};

const directionForDisplay = (direction: string) => {
  const supported = ["increase", "decrease", "extension", "reduction", "changed"];
  return supported.includes(direction) ? direction : "changed";
};

const directionIcon = (direction: string) => {
  if (direction === "increase" || direction === "extension") return "↗";
  if (direction === "decrease" || direction === "reduction") return "↘";
  return "↔";
};

const setText = (root: ParentNode, selector: string, value: string) => {
  const element = root.querySelector<HTMLElement>(selector);
  if (element) element.textContent = value;
};

const renderChangeCard = (template: HTMLElement, event: ChangeEvent, base: string) => {
  const card = template.cloneNode(true) as HTMLElement;
  const agency = event.agency_name?.trim() || "Agency not reported";
  const supplier = event.supplier_name?.trim() || "Supplier not reported";
  const description = event.description?.trim() || "Contract record";
  const direction = directionForDisplay(event.direction);
  const contractUrl = `${base}contracts/${encodeURIComponent(event.contract_id)}/`;

  card.hidden = false;
  card.dataset.eventId = event.event_id;
  card.dataset.search = searchableText(event);
  card.dataset.agency = agency;
  card.dataset.field = event.field_name;
  card.dataset.direction = event.direction;

  const changeType = card.querySelector<HTMLElement>(".change-type");
  if (changeType) {
    const icon = document.createElement("span");
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = directionIcon(direction);
    changeType.className = `change-type change-type--${direction}`;
    changeType.replaceChildren(icon, document.createTextNode(event.field_label));
  }

  const time = card.querySelector<HTMLTimeElement>("time");
  if (time) {
    time.dateTime = event.detected_at;
    time.textContent = formatDate(event.detected_at);
  }

  const identity = card.querySelector<HTMLElement>(".change-card__identity");
  const identityLink = identity?.querySelector<HTMLAnchorElement>("a");
  if (identityLink) {
    identityLink.href = contractUrl;
    identityLink.textContent = event.contract_id;
  }
  if (identity?.children[2]) identity.children[2].textContent = event.notice_id;

  setText(card, "h3", description);
  setText(card, ".change-summary", event.summary);

  const beforeAfter = card.querySelector<HTMLElement>(".before-after");
  beforeAfter?.setAttribute("aria-label", `${event.field_label} before and after`);
  const comparedValues = beforeAfter?.querySelectorAll<HTMLElement>("strong");
  if (comparedValues?.[0]) {
    comparedValues[0].textContent = formatValue(event.old_value, event.field_name);
  }
  if (comparedValues?.[1]) {
    comparedValues[1].textContent = formatValue(event.new_value, event.field_name);
  }

  const parties = card.querySelectorAll<HTMLElement>(".change-card__parties dd");
  if (parties[0]) parties[0].textContent = agency;
  if (parties[1]) parties[1].textContent = supplier;

  const actions = card.querySelectorAll<HTMLAnchorElement>(".change-card__actions a");
  if (actions[0]) actions[0].href = contractUrl;
  if (actions[1]) actions[1].href = event.official_record_url;
  if (actions[2]) actions[2].href = event.source_url;

  return card;
};

const updateFilterParameters = (url: URL, filters: Filters, page: number) => {
  FILTER_NAMES.forEach((name) => {
    const value = filters[name];
    if (value) url.searchParams.set(name, value);
    else url.searchParams.delete(name);
  });

  if (hasActiveFilters(filters) && page > 1) {
    url.searchParams.set(FILTER_PAGE_PARAMETER, String(page));
  } else {
    url.searchParams.delete(FILTER_PAGE_PARAMETER);
  }
  url.hash = "change-results";
};

const filterPageHref = (filters: Filters, page: number) => {
  const url = new URL(window.location.href);
  updateFilterParameters(url, filters, page);
  return `${url.pathname}${url.search}${url.hash}`;
};

const updateHistory = (filters: Filters, page: number, mode: HistoryMode) => {
  if (mode === "none") return;
  const url = new URL(window.location.href);
  updateFilterParameters(url, filters, page);
  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  if (mode === "push") window.history.pushState({}, "", nextUrl);
  else window.history.replaceState({}, "", nextUrl);
};

const createStep = (
  filters: Filters,
  page: number | null,
  label: "Previous" | "Next"
) => {
  const step = document.createElement(page === null ? "span" : "a");
  step.className = "change-pagination__step";
  if (page === null) step.setAttribute("aria-disabled", "true");
  else {
    const link = step as HTMLAnchorElement;
    link.href = filterPageHref(filters, page);
    link.dataset.filterPage = String(page);
    link.rel = label === "Previous" ? "prev" : "next";
  }

  const arrow = document.createElement("span");
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = label === "Previous" ? "←" : "→";
  const text = document.createElement("span");
  text.className = "change-pagination__step-label";
  text.textContent = label;
  if (label === "Previous") step.append(arrow, text);
  else step.append(text, arrow);
  return step;
};

const renderPagination = (
  navigation: HTMLElement,
  filters: Filters,
  currentPage: number,
  totalPages: number
) => {
  const previous = createStep(
    filters,
    currentPage > 1 ? currentPage - 1 : null,
    "Previous"
  );
  const pages = document.createElement("ol");
  pages.className = "change-pagination__pages";

  getChangePaginationItems(currentPage, totalPages).forEach((page) => {
    const item = document.createElement("li");
    if (page === null) {
      item.className = "change-pagination__ellipsis";
      item.setAttribute("aria-hidden", "true");
      item.textContent = "…";
    } else if (page === currentPage) {
      item.className = "is-current";
      const current = document.createElement("span");
      current.setAttribute("aria-current", "page");
      const hidden = document.createElement("span");
      hidden.className = "visually-hidden";
      hidden.textContent = "Page ";
      current.append(hidden, document.createTextNode(String(page)));
      item.append(current);
    } else {
      const link = document.createElement("a");
      link.href = filterPageHref(filters, page);
      link.dataset.filterPage = String(page);
      link.setAttribute("aria-label", `Go to filtered page ${page}`);
      link.textContent = String(page);
      item.append(link);
    }
    pages.append(item);
  });

  const next = createStep(
    filters,
    currentPage < totalPages ? currentPage + 1 : null,
    "Next"
  );
  navigation.hidden = false;
  navigation.replaceChildren(previous, pages, next);
};

const setFormFromUrl = (form: HTMLFormElement) => {
  const parameters = new URL(window.location.href).searchParams;
  FILTER_NAMES.forEach((name) => {
    const control = form.elements.namedItem(name);
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) {
      control.value = parameters.get(name) ?? "";
    }
  });
};

const filteredPageFromUrl = () => {
  const value = Number.parseInt(
    new URL(window.location.href).searchParams.get(FILTER_PAGE_PARAMETER) ?? "1",
    10
  );
  return Number.isFinite(value) && value > 0 ? value : 1;
};

const downloadEvents = (events: ChangeEvent[]) => {
  const neutralise = (value: string) => (/^[=+\-@\t\r\n]/.test(value) ? `'${value}` : value);
  const escape = (value: string) => `"${neutralise(value).replaceAll('"', '""')}"`;
  const rows = [
    "contract_id,agency,field,direction,summary",
    ...events.map((event) =>
      [
        event.contract_id,
        event.agency_name ?? "Agency not reported",
        event.field_name,
        event.direction,
        event.summary
      ]
        .map(escape)
        .join(",")
    )
  ];
  const blob = new Blob([`${rows.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "contractdelta-filtered-changes.csv";
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url));
};

export const setupChangeFeed = () => {
  const feed = document.querySelector<HTMLElement>("[data-current-page]");
  if (!feed || feed.dataset.filterEnhanced === "true") return;

  const form = feed.querySelector<HTMLFormElement>("[data-filters]");
  const grid = feed.querySelector<HTMLElement>("[data-change-grid]");
  const count = feed.querySelector<HTMLElement>("[data-result-count]");
  const detail = feed.querySelector<HTMLElement>("[data-result-detail]");
  const empty = feed.querySelector<HTMLElement>("[data-empty]");
  const download = feed.querySelector<HTMLButtonElement>("[data-download-filtered]");
  const note = feed.querySelector<HTMLElement>("[data-filter-note]");
  const navigations = Array.from(
    feed.querySelectorAll<HTMLElement>(".change-pagination")
  );
  const initialCards = Array.from(feed.querySelectorAll<HTMLElement>("[data-event]"));
  const cardTemplate = initialCards[0]?.cloneNode(true) as HTMLElement | undefined;
  const eventsUrl = feed.dataset.eventsUrl;
  const base = feed.dataset.base;
  if (!form || !grid || !count || !detail || !empty || !download || !note) return;
  if (!cardTemplate || !eventsUrl || base === undefined) return;

  feed.dataset.filterEnhanced = "true";
  const initialDetail = detail.textContent ?? "";
  const initialNote = note.textContent ?? "";
  const initialNavigation = navigations.map((navigation) => ({
    navigation,
    children: Array.from(navigation.childNodes).map((node) => node.cloneNode(true))
  }));
  let filterRequest = 0;
  let inputTimer: number | undefined;
  let filteredEvents: ChangeEvent[] | undefined;

  const restoreStaticPage = () => {
    grid.replaceChildren(...initialCards.map((card) => card.cloneNode(true)));
    initialNavigation.forEach(({ navigation, children }) => {
      navigation.hidden = false;
      navigation.replaceChildren(...children.map((node) => node.cloneNode(true)));
    });
    count.textContent = String(initialCards.length);
    detail.textContent = initialDetail;
    empty.hidden = true;
    download.disabled = false;
    note.textContent = initialNote;
    note.classList.remove("is-error");
    feed.removeAttribute("aria-busy");
    filteredEvents = undefined;
  };

  const applyFilters = async (
    requestedPage: number,
    historyMode: HistoryMode,
    shouldAlign = false
  ) => {
    const filters = readFilters(form);
    if (!hasActiveFilters(filters)) {
      filterRequest += 1;
      restoreStaticPage();
      updateHistory(filters, 1, historyMode);
      return;
    }

    const request = ++filterRequest;
    feed.setAttribute("aria-busy", "true");
    count.textContent = "Loading";
    detail.textContent = " full-dataset matches.";
    download.disabled = true;
    note.textContent = FILTER_NOTE;
    note.classList.remove("is-error");

    try {
      const allEvents = await loadAllEvents(eventsUrl);
      if (request !== filterRequest || !feed.isConnected) return;
      filteredEvents = allEvents.filter((event) => matchesFilters(event, filters));
      const totalPages = getChangePageCount(filteredEvents.length);
      const currentPage = Math.min(Math.max(1, requestedPage), totalPages);
      const pageEvents = getChangePage(filteredEvents, currentPage);
      grid.replaceChildren(
        ...pageEvents.map((event) => renderChangeCard(cardTemplate, event, base))
      );

      count.textContent = String(filteredEvents.length);
      if (filteredEvents.length === 0) {
        detail.textContent = " matching changes across the full dataset.";
      } else {
        const first = (currentPage - 1) * CHANGE_PAGE_SIZE + 1;
        const last = first + pageEvents.length - 1;
        detail.textContent =
          ` matching changes across the full dataset. Showing ${first} to ${last}` +
          ` on filtered page ${currentPage} of ${totalPages}.`;
      }
      empty.hidden = filteredEvents.length !== 0;
      download.disabled = filteredEvents.length === 0;
      navigations.forEach((navigation) => {
        if (filteredEvents?.length) {
          renderPagination(navigation, filters, currentPage, totalPages);
        } else {
          navigation.hidden = true;
        }
      });
      note.textContent = FILTER_NOTE;
      note.classList.remove("is-error");
      feed.removeAttribute("aria-busy");
      updateHistory(filters, currentPage, historyMode);
      if (shouldAlign) alignResults();
    } catch {
      if (request !== filterRequest || !feed.isConnected) return;
      restoreStaticPage();
      download.disabled = true;
      note.textContent = FILTER_ERROR;
      note.classList.add("is-error");
    }
  };

  form.addEventListener("input", () => {
    window.clearTimeout(inputTimer);
    inputTimer = window.setTimeout(() => void applyFilters(1, "replace"), 120);
  });

  form.addEventListener("reset", () => {
    window.clearTimeout(inputTimer);
    window.setTimeout(() => void applyFilters(1, "replace"));
  });

  feed.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest<HTMLAnchorElement>("a[data-filter-page]");
    if (!link || !feed.contains(link)) return;
    event.preventDefault();
    const page = Number.parseInt(link.dataset.filterPage ?? "1", 10);
    if (Number.isFinite(page)) void applyFilters(page, "push", true);
  });

  download.addEventListener("click", async () => {
    download.disabled = true;
    try {
      const allEvents = await loadAllEvents(eventsUrl);
      const filters = readFilters(form);
      const events = hasActiveFilters(filters)
        ? (filteredEvents ?? allEvents.filter((event) => matchesFilters(event, filters)))
        : allEvents;
      if (events.length > 0) downloadEvents(events);
      download.disabled = events.length === 0;
    } catch {
      download.disabled = true;
      note.textContent = FILTER_ERROR;
      note.classList.add("is-error");
    }
  });

  if (activePopstateHandler) {
    window.removeEventListener("popstate", activePopstateHandler);
  }
  activePopstateHandler = () => {
    setFormFromUrl(form);
    void applyFilters(filteredPageFromUrl(), "none");
  };
  window.addEventListener("popstate", activePopstateHandler);

  setFormFromUrl(form);
  if (hasActiveFilters(readFilters(form))) {
    void applyFilters(filteredPageFromUrl(), "replace");
  }
};
