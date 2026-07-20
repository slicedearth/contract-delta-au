export const CHANGE_PAGE_SIZE = 50;

export const getChangePageCount = (eventCount: number): number =>
  Math.max(1, Math.ceil(eventCount / CHANGE_PAGE_SIZE));

export const getChangePage = <T>(items: T[], page: number): T[] => {
  const start = (page - 1) * CHANGE_PAGE_SIZE;
  return items.slice(start, start + CHANGE_PAGE_SIZE);
};

export const getChangePaginationItems = (
  currentPage: number,
  totalPages: number
): Array<number | null> => {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const includedPages = new Set([1, totalPages]);
  for (let page = currentPage - 2; page <= currentPage + 2; page += 1) {
    if (page > 1 && page < totalPages) includedPages.add(page);
  }

  const sortedPages = [...includedPages].sort((left, right) => left - right);
  const items: Array<number | null> = [];

  sortedPages.forEach((page, index) => {
    const previousPage = sortedPages[index - 1];
    if (previousPage !== undefined && page - previousPage > 1) items.push(null);
    items.push(page);
  });

  return items;
};
