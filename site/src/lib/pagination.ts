export const CHANGE_PAGE_SIZE = 50;

export const getChangePageCount = (eventCount: number): number =>
  Math.max(1, Math.ceil(eventCount / CHANGE_PAGE_SIZE));

export const getChangePage = <T>(items: T[], page: number): T[] => {
  const start = (page - 1) * CHANGE_PAGE_SIZE;
  return items.slice(start, start + CHANGE_PAGE_SIZE);
};
